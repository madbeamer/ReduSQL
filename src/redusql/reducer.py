import logging
import time
from pathlib import Path
from textwrap import indent
from multiprocessing import cpu_count

from src.redusql.cache import Cache
from src.redusql.dd import DD
from src.redusql.exception import ReductionException, ReductionStopped
from src.redusql.iterator import CombinedIterator, IteratorRegistry
from src.redusql.parallel_dd import ParallelDD
from src.redusql.splitter import Splitter
from src.redusql.tester import SQLTester
from src.redusql.tokenizer import SQLTokenizer, TestBuilder

logger = logging.getLogger(__name__)


def pretty_str(obj):
    """
    Return the "pretty-string" representation of a data structure. Explicitly
    handles dicts and lists arbitrarily nested in each other, and objects with
    ``__name__`` (typically functions and classes). Everything else is handled
    with :func:`str` as a fallback. The output is YAML-like, but with no intent
    to be conforming. The goal is to be informative when logging.
    """
    def _pretty_str(obj):
        if not obj:
            return repr(obj)
        if isinstance(obj, dict):
            log = []
            for k, v in sorted(obj.items()):
                k_log = _pretty_str(k)
                v_log = _pretty_str(v)
                if isinstance(v_log, list):
                    log += [f'{k_log}:']
                    for line in v_log:
                        log += [f'\t{line}']
                else:
                    log += [f'{k_log}: {v_log}']
            return log if len(log) > 1 else log[0]
        if isinstance(obj, list):
            v_logs = [_pretty_str(v) for v in obj]
            if any(isinstance(v_log, list) for v_log in v_logs):
                log = []
                for v_log in v_logs:
                    if not isinstance(v_log, list):
                        v_log = [v_log]
                    for i, line in enumerate(v_log):
                        log += [f'{"-" if i == 0 else " "} {line}']
            else:
                log = ', '.join(v_log for v_log in v_logs)
            return log
        if hasattr(obj, '__name__'):
            return '.'.join(([obj.__module__] if hasattr(obj, '__module__') else []) + [obj.__name__])
        return str(obj)
    return '\n'.join(_pretty_str(obj))


def reduce(src, *,
           reduce_class, reduce_config,
           tester_class, tester_config,
           atom='line', cache_config=None):
    """
    Execute ReduSQL reduction.
    
    :param src: Contents of the SQL query to reduce.
    :param reduce_class: Reference to the reducer class (DD or ParallelDD).
    :param reduce_config: Dictionary containing information to initialize the
        reduce_class.
    :param tester_class: Reference to a runnable class that can decide about the
        interestingness of a test case.
    :param tester_config: Dictionary containing information to initialize the
        tester_class.
    :param atom: Input granularity to work with during reduce ('token' for SQL tokens).
    :param cache_config: Dictionary containing information to initialize the
        cache_class.
    :return: The contents of the minimal SQL query.
    :raises ReductionException: If reduction could not run until completion.
    """
    
    # Get the parameters in a dictionary so that they can be pretty-printed
    # (minus src, as that parameter can be arbitrarily large)
    args = locals().copy()
    del args['src']
    if logger.isEnabledFor(logging.INFO):
        logger.info('Reduce session starts\n%s', indent(pretty_str(args), '\t'))
    
    cache = Cache(**cache_config)
    
    # Tokenize the SQL source
    if atom == 'token':
        src = SQLTokenizer.tokenize(src)
    elif atom == 'line':
        src = src.splitlines(True)
    elif atom == 'both':
        # First do line-based, then token-based
        pass  # FIXME: Implement this 
    else:
        raise ValueError(f"Unsupported atom type: {atom}")
    
    logger.info('Initial test contains %d %ss', len(src), atom)
    
    test_builder = TestBuilder(src, 'line')
    if atom == 'line':
        test_builder = TestBuilder(src, 'line')
    else:
        test_builder = TestBuilder(src, 'token')

    if cache:
        cache.clear()
        cache.set_test_builder(test_builder)
    
    dd = reduce_class(tester_class(test_builder=test_builder, **tester_config),
                      cache=cache,
                      id_prefix=('a0',),
                      **reduce_config)
    try:
        min_set = dd(list(range(len(src))))
        src = test_builder(min_set)
        
    except ReductionException as e:
        logger.warning('Reduction stopped prematurely, the output may not be minimal: %s', e, 
                      exc_info=None if isinstance(e, ReductionStopped) else e)
        
        e.result = test_builder(e.result)
        raise
    
    return src


class SQLReducer:
    """
    Main class for SQL query reduction using delta debugging.
    Integrates all ReduSQL components to provide a high-level interface.
    """
    
    def __init__(self, query_file, test_script, verbose=False):
        """
        Initialize the SQL reducer.
        
        Args:
            query_file: Path to the SQL query file to reduce
            test_script: Path to the test script that validates reductions
            verbose: Enable verbose output
        """
        self.query_file = Path(query_file)
        self.test_script = Path(test_script)
        self.verbose = verbose
        
        # Validate inputs
        if not self.query_file.exists():
            raise FileNotFoundError(f"Query file not found: {query_file}")
        if not self.test_script.exists():
            raise FileNotFoundError(f"Test script not found: {test_script}")
        
        # Read original query and tokenize it
        self.original_query = self.query_file.read_text()
        self.original_tokens = SQLTokenizer.tokenize(self.original_query)
        self.current_tokens = self.original_tokens[:]
        
        print(f"Loaded query with {len(self.original_tokens)} tokens")
        if self.verbose:
            print("Sample tokens:", [repr(t) for t in self.original_tokens[:10]], "...")
    
    def reduce(self, parallel=False, 
            subset_first=True, subset_iterator='forward', complement_iterator='forward',
            atom='line'):
        """
        Main reduction method using delta debugging.
        
        :param parallel: Use parallel delta debugging.
        :param subset_first: Check subsets before complements.
        :param subset_iterator: Iterator strategy for subsets.
        :param complement_iterator: Iterator strategy for complements.
        :param atom: Granularity of reduction ('token' or 'line').
        :return: Reduced SQL query text or None if failed.
        """
        print(f"Starting reduction of {self.query_file}")
        print(f"Original query has {len(self.original_tokens)} tokens")
        print(f"Using test script: {self.test_script}")
        print("-" * 60)
        
        # Setup tester
        sql_tester = SQLTester(
            test_script=self.test_script,
            filename=self.query_file.name,
            verbose=self.verbose
        )
        
        # First, verify that the original query triggers the bug
        print("Verifying original query triggers the bug...")
        if not sql_tester.test_tokens_directly(self.current_tokens):
            print("ERROR: Original query does not trigger the bug!")
            print("Test script returned exit code 1 for the original query.")
            print("Please check your test script and query file.")
            return None
        
        print("✓ Original query triggers the bug")
        print("-" * 60)
        
        # Start timing the reduction process
        start_time = time.time()
        
        # Configure reduction with default settings
        reduce_config = {
            'config_iterator': CombinedIterator(
                subset_first,
                IteratorRegistry.registry[subset_iterator],  # ← No () - pass the function
                IteratorRegistry.registry[complement_iterator]  # ← No () - pass the function
            ),
            'split': Splitter(n=2),
        }
        
        if parallel:
            reduce_class = ParallelDD
            reduce_config['proc_num'] = cpu_count()  # Use all available CPUs
        else:
            reduce_class = DD
        
        # Configure cache with default settings
        cache_config = {
            'evict_after_fail': True  # Evict larger configs after finding failure
        }
        
        # Configure tester
        tester_class = sql_tester.create_subprocess_test
        tester_config = {'verbose': self.verbose}
        
        print("Applying delta debugging reduction...")
        try:
            reduced_query = reduce(
            self.original_query,
            reduce_class=reduce_class,
            reduce_config=reduce_config,
            tester_class=tester_class,
            tester_config=tester_config,
            atom=atom,
            cache_config=cache_config
        )
            
            print("✓ Delta debugging completed successfully")
            self.current_tokens = SQLTokenizer.tokenize(reduced_query)
            
        except ReductionException as e:
            print("⚠ Delta debugging stopped prematurely")
            if e.result:
                reduced_query = e.result
                self.current_tokens = SQLTokenizer.tokenize(reduced_query)
            else:
                print("✗ Delta debugging failed - keeping original query")
                reduced_query = self.original_query
        
        # Calculate reduction time
        end_time = time.time()
        reduction_time = end_time - start_time
        
        print("-" * 60)
        print(f"Final query has {len(self.current_tokens)} tokens")
        print(f"Reduction: {len(self.original_tokens) - len(self.current_tokens)} tokens")
        if len(self.original_tokens) > 0:
            percentage = (1 - len(self.current_tokens) / len(self.original_tokens)) * 100
            print(f"Reduction percentage: {percentage:.2f}%")
        
        # Format and display the time taken
        if reduction_time < 60:
            print(f"Time taken: {reduction_time:.2f} seconds")
        elif reduction_time < 3600:
            minutes = int(reduction_time // 60)
            seconds = reduction_time % 60
            print(f"Time taken: {minutes}m {seconds:.2f}s")
        else:
            hours = int(reduction_time // 3600)
            minutes = int((reduction_time % 3600) // 60)
            seconds = reduction_time % 60
            print(f"Time taken: {hours}h {minutes}m {seconds:.2f}s")
        
        return reduced_query
    
    def save_reduced_query(self, output_file=None):
        """
        Save the reduced query to a file.
        
        Args:
            output_file: Path to save the reduced query (optional)
        """
        if output_file is None:
            # Try to determine the query directory name from the input path
            query_dir = self.query_file.parent.name
            if query_dir == "queries":
                # If query is directly in queries/, use the filename as directory
                query_name = self.query_file.stem
            else:
                # If query is in a subdirectory, use that subdirectory name
                query_name = query_dir
            
            # Create output path with query-specific directory
            output_file = Path("output") / query_name / "reduced_query.sql"
        
        output_path = Path(output_file)
        # Ensure the output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert current tokens to query text
        current_query = SQLTokenizer.detokenize(self.current_tokens)
        
        output_path.write_text(current_query)
        print(f"\nReduced query saved to: {output_file}")
        
        # Also save token information for debugging
        token_info_file = output_path.parent / f"{output_path.stem}_tokens.txt"
        with open(token_info_file, 'w') as f:
            f.write(f"Original tokens: {len(self.original_tokens)}\n")
            f.write(f"Reduced tokens: {len(self.current_tokens)}\n")
            f.write(f"Reduction: {len(self.original_tokens) - len(self.current_tokens)} tokens\n")
            if len(self.original_tokens) > 0:
                f.write(f"Percentage: {(1 - len(self.current_tokens) / len(self.original_tokens)) * 100:.2f}%\n")
            f.write("\nReduced tokens:\n")
            for i, token in enumerate(self.current_tokens):
                f.write(f"{i:3d}: {repr(token)}\n")
        
        print(f"Token information saved to: {token_info_file}")
        