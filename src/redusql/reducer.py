import logging
import time
import os
from pathlib import Path
from multiprocessing import cpu_count

from src.redusql.cache import Cache
from src.redusql.dd import DD
from src.redusql.exception import ReductionException, ReductionStopped
from src.redusql.iterator import CombinedIterator, IteratorRegistry
from src.redusql.parallel_dd import ParallelDD
from src.redusql.tester import SQLTester
from src.redusql.test_builder import TestBuilder
from src.redusql.tokenizer import SQLTokenizer
from src.redusql.postprocessing import apply_complete_postprocessing

from src.redusql.hdd_optimized import apply_optimized_hdd
from src.redusql.hdd_star import apply_hdd_star

logger = logging.getLogger(__name__)


def reduce(src, *,
           reduce_class, reduce_config,
           tester_class, tester_config,
           atom='token', cache_config=None):
    """
    Execute ReduSQL reduction.
    """
    
    cache = Cache(**cache_config)
    
    # Tokenize the SQL source using ANTLR
    if atom == 'token':
        src = SQLTokenizer.tokenize(src)
    elif atom == 'line':
        src = src.splitlines(True)
    else:
        raise ValueError(f"Unsupported atom type: {atom}")
    
    logger.info('Initial test contains %d %ss', len(src), atom)
    
    # Use ANTLR-based test builder
    if atom == 'token':
        test_builder = TestBuilder(src, 'token', detokenizer=SQLTokenizer.detokenize)
    else:
        test_builder = TestBuilder(src, 'line')

    if cache:
        cache.clear()
    
    dd = reduce_class(tester_class(test_builder=test_builder, **tester_config),
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
    def __init__(self, query_file, test_script, verbose=False):
        self.query_file = Path(query_file)
        self.test_script = Path(test_script)
        self.verbose = verbose
        
        # Validate inputs
        if not self.query_file.exists():
            raise FileNotFoundError(f"Query file not found: {query_file}")
        if not self.test_script.exists():
            raise FileNotFoundError(f"Test script not found: {test_script}")
        
        # Read original query and tokenize it using ANTLR
        self.original_query = self.query_file.read_text()
        self.original_tokens = SQLTokenizer.tokenize(self.original_query)
        self.current_tokens = self.original_tokens[:]
        
        print(f"Loaded query with {len(self.original_tokens)} tokens")
        if self.verbose:
            print("Sample tokens:", [repr(t) for t in self.original_tokens[:10]], "...")
        
        # Setup logging
        if self.verbose:
            logging.basicConfig(level=logging.DEBUG, format='%(message)s')
        else:
            logging.basicConfig(level=logging.INFO, format='%(message)s')

        self.reduction_time = 0
    
    def reduce(self, algorithm='DD', parallel=False, 
        subset_first=True, subset_iterator='forward', complement_iterator='forward',
        atom='line', use_fixpoint=False):

        print(f"Starting reduction of {self.query_file}")
        print(f"Algorithm: {algorithm}")
        
        if algorithm == 'HDD':
            desc = 'Standard Optimized'
            if use_fixpoint:
                desc += " with Fixpoint (HDD*)"
            print(f"HDD Variant: {desc}")
            if use_fixpoint:
                print("Minimality: 1-minimal")
            else:
                print("Minimality: 1-tree-minimal per level")
        elif algorithm == 'DDHDD':
            print(f"Phase 1: Delta Debugging (DD) with {atom} granularity.")
            print("Phase 2: Hierarchical Delta Debugging (HDD)")
            desc = 'Standard Optimized'
            if use_fixpoint:
                desc += " with Fixpoint (HDD*)"
            print(f"HDD Variant for Phase 2: {desc}")
            if use_fixpoint:
                print("Minimality: 1-minimal")
            else:
                print("Minimality: 1-tree-minimal per level")
        
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
        # Test the original file directly instead of tokenizing/detokenizing
        print("Verifying original query triggers the bug...")
        if not sql_tester.test_original_file_directly(self.query_file):
            print("ERROR: Original query does not trigger the bug!")
            print("Test script returned exit code 1 for the original query.")
            print("Please check your test script and query file.")
            return None
        
        print("✓ Original query triggers the bug")
        print("-" * 60)
        
        # Start timing the reduction process
        start_time = time.time()
        
        # Variable to track the current working query (starts with original)
        working_query = self.original_query
        
        # Choose algorithm
        if algorithm == 'DDHDD':
            # Phase 1: Apply Delta Debugging first
            print("=" * 60)
            print("PHASE 1: DELTA DEBUGGING")
            print("=" * 60)
            
            # Configure reduction with default settings
            reduce_config = {
                'config_iterator': CombinedIterator(
                    subset_first,
                    IteratorRegistry.registry[subset_iterator],
                    IteratorRegistry.registry[complement_iterator]
                ),
            }
            
            if parallel:
                reduce_class = ParallelDD
                reduce_config['proc_num'] = cpu_count()
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
                dd_reduced_query = reduce(
                    working_query,
                    reduce_class=reduce_class,
                    reduce_config=reduce_config,
                    tester_class=tester_class,
                    tester_config=tester_config,
                    atom=atom,
                    cache_config=cache_config
                )
                
                print("✓ Phase 1 (DD) completed successfully")
                dd_tokens = SQLTokenizer.tokenize(dd_reduced_query)
                dd_reduction = len(self.original_tokens) - len(dd_tokens)
                if len(self.original_tokens) > 0:
                    dd_percentage = (dd_reduction / len(self.original_tokens)) * 100
                    print(f"Phase 1 reduction: {dd_reduction} tokens ({dd_percentage:.2f}%)")
                
                # Use DD result as input for HDD
                working_query = dd_reduced_query
                
            except ReductionException as e:
                print("⚠ Phase 1 (DD) stopped prematurely")
                if e.result:
                    dd_reduced_query = e.result
                    print("Using partial DD result for Phase 2")
                    working_query = dd_reduced_query
                else:
                    print("DD failed completely, using original query for Phase 2")
                    working_query = self.original_query
            
            # Phase 2: Apply HDD to the DD-reduced query
            print("\n" + "=" * 60)
            print("PHASE 2: HIERARCHICAL DELTA DEBUGGING")
            print("=" * 60)
            
            # Setup HDD tester function
            def hdd_tester(sql_text, config_id):
                return sql_tester.test_sql_directly(sql_text)
            
            try:
                if use_fixpoint:
                    print("Applying Optimized HDD with Fixpoint (Optimized HDD*)...")
                    reduced_query = apply_hdd_star(apply_optimized_hdd, working_query, hdd_tester, self.verbose)
                else:
                    print("Applying Optimized Hierarchical Delta Debugging (HDD)...")
                    reduced_query = apply_optimized_hdd(working_query, hdd_tester, self.verbose)

                print("✓ Phase 2 (HDD) completed successfully")
                
                # Calculate HDD-specific reduction
                working_tokens = SQLTokenizer.tokenize(working_query)
                final_tokens = SQLTokenizer.tokenize(reduced_query)
                hdd_reduction = len(working_tokens) - len(final_tokens)
                if len(working_tokens) > 0:
                    hdd_percentage = (hdd_reduction / len(working_tokens)) * 100
                    print(f"Phase 2 reduction: {hdd_reduction} tokens ({hdd_percentage:.2f}%)")
                
            except Exception as e:
                print(f"⚠ Phase 2 (HDD) failed: {e}")
                if self.verbose:
                    import traceback
                    traceback.print_exc()
                print("✗ HDD failed - using DD result")
                reduced_query = working_query
            
            # Apply post-processing
            if self.verbose:
                print("Applying semicolon post-processing...")
                
            pre_cleanup_length = len(reduced_query)
            reduced_query = apply_complete_postprocessing(reduced_query, self.verbose)
            post_cleanup_length = len(reduced_query)
            
            cleanup_reduction = pre_cleanup_length - post_cleanup_length
            if cleanup_reduction > 0:
                print(f"✓ Post-processing removed {cleanup_reduction} characters")
            elif self.verbose:
                print("✓ No consecutive semicolons found")
            
            print(f"✓ DDHDD completed successfully")
            self.current_tokens = SQLTokenizer.tokenize(reduced_query)
        
        elif algorithm == 'HDD':
            # Use Hierarchical Delta Debugging only
            def hdd_tester(sql_text, config_id):
                return sql_tester.test_sql_directly(sql_text)
            
            try:
                if use_fixpoint:
                    print("Applying Optimized HDD with Fixpoint (Optimized HDD*)...")
                    reduced_query = apply_hdd_star(apply_optimized_hdd, self.original_query, hdd_tester, self.verbose)

                else:
                    print("Applying Optimized Hierarchical Delta Debugging (HDD)...")
                    reduced_query = apply_optimized_hdd(self.original_query, hdd_tester, self.verbose)

                if self.verbose:
                    print("Applying semicolon post-processing...")
                    
                pre_cleanup_length = len(reduced_query)
                reduced_query = apply_complete_postprocessing(reduced_query, self.verbose)
                post_cleanup_length = len(reduced_query)
                
                cleanup_reduction = pre_cleanup_length - post_cleanup_length
                if cleanup_reduction > 0:
                    print(f"✓ Post-processing removed {cleanup_reduction} characters")
                elif self.verbose:
                    print("✓ No consecutive semicolons found")
                
                variant_name = "Standard Optimized "
                if use_fixpoint:
                    variant_name += "*"
                
                print(f"✓ HDD ({variant_name}) completed successfully")
                self.current_tokens = SQLTokenizer.tokenize(reduced_query)
                
            except Exception as e:
                print(f"⚠ Hierarchical Delta Debugging failed: {e}")
                if self.verbose:
                    import traceback
                    traceback.print_exc()
                print("✗ HDD failed - keeping original query")
                reduced_query = self.original_query
        
        else:
            # Use traditional Delta Debugging only
            # Configure reduction with default settings
            reduce_config = {
                'config_iterator': CombinedIterator(
                    subset_first,
                    IteratorRegistry.registry[subset_iterator],
                    IteratorRegistry.registry[complement_iterator]
                ),
            }
            
            if parallel:
                reduce_class = ParallelDD
                reduce_config['proc_num'] = cpu_count()
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
        self.reduction_time = end_time - start_time
        
        print("-" * 60)
        print(f"Final query has {len(self.current_tokens)} tokens")
        print(f"Total reduction: {len(self.original_tokens) - len(self.current_tokens)} tokens")
        
        # Check if reduction actually made things worse
        if len(self.current_tokens) > len(self.original_tokens):
            reduced_query = self.original_query
            self.current_tokens = self.original_tokens[:]
            percentage = 0.0
        else:
            if len(self.original_tokens) > 0:
                percentage = (1 - len(self.current_tokens) / len(self.original_tokens)) * 100
            else:
                percentage = 0.0
        
        print(f"Total reduction percentage: {percentage:.2f}%")
        
        # Format and display the time taken
        if self.reduction_time < 60:
            print(f"Time taken: {self.reduction_time:.2f} seconds")
        elif self.reduction_time < 3600:
            minutes = int(self.reduction_time // 60)
            seconds = self.reduction_time % 60
            print(f"Time taken: {minutes}m {seconds:.2f}s")
        else:
            hours = int(self.reduction_time // 3600)
            minutes = int((self.reduction_time % 3600) // 60)
            seconds = self.reduction_time % 60
            print(f"Time taken: {hours}h {minutes}m {seconds:.2f}s")
        
        return reduced_query
    
    def save_reduced_query(self, output_file=None):
        if output_file is None:
            # Check if TEST_CASE_LOCATION is set in environment
            test_case_location = os.environ.get('TEST_CASE_LOCATION')
            if test_case_location:
                # Create reduced filename based on TEST_CASE_LOCATION
                original_path = Path(test_case_location)
                output_file = original_path.parent / "output" / f"{original_path.stem}_reduced.sql"
            else:
                output_file = Path("output") / 'query_reduced.sql'
        else:
            # If output_file is provided, ensure it's in the output directory
            output_file = Path("output") / Path(output_file).name

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert current tokens to query text using ANTLR detokenizer
        current_query = SQLTokenizer.detokenize(self.current_tokens)

        output_path.write_text(current_query)
        print(f"\nReduced query saved to: {output_file}")

        # Also save token information for debugging (with a different name to avoid overwriting)
        token_info_file = output_path.parent / f"{output_path.stem}_info.txt"
        with open(token_info_file, 'w') as f:
            f.write(f"Original tokens: {len(self.original_tokens)}\n")
            f.write(f"Reduced tokens: {len(self.current_tokens)}\n")
            f.write(f"Reduction: {len(self.original_tokens) - len(self.current_tokens)} tokens\n")
            if len(self.original_tokens) > 0:
                f.write(f"Percentage: {(1 - len(self.current_tokens) / len(self.original_tokens)) * 100:.2f}%")
            if self.reduction_time < 60:
                f.write(f"\nTime taken: {self.reduction_time:.2f} seconds\n")
            elif self.reduction_time < 3600:
                minutes = int(self.reduction_time // 60)
                seconds = self.reduction_time % 60
                f.write(f"\nTime taken: {minutes}m {seconds:.2f}s\n")
            else:
                hours = int(self.reduction_time // 3600)
                minutes = int((self.reduction_time % 3600) // 60)
                seconds = self.reduction_time % 60
                f.write(f"\nTime taken: {hours}h {minutes}m {seconds:.2f}s\n")
            f.write("\nReduced tokens:\n")
            for i, token in enumerate(self.current_tokens):
                f.write(f"{i:3d}: {repr(token)}\n")

        print(f"Token information saved to: {token_info_file}")
        