import itertools
import logging

from src.redusql.cache import Cache
from src.redusql.exception import ReductionError, ReductionStopped
from src.redusql.iterator import CombinedIterator
from src.redusql.outcome import Outcome
from src.redusql.splitter import Splitter

logger = logging.getLogger(__name__)


class DD:
    """
    Single process version of the Delta Debugging algorithm.
    """
    
    def __init__(self, test, *, id_prefix=None,
                 config_iterator=None):
        """
        Initialize a DD object.
        
        :param test: A callable tester object.
        :param id_prefix: Tuple to prepend to config IDs during tests.
        :param config_iterator: Reference to a generator function that provides
            config indices in an arbitrary order.
        """
        self._test = test
        self._split = Splitter()
        self._cache = Cache()
        self._id_prefix = id_prefix or ()
        self._iteration_prefix = ()
        self._config_iterator = config_iterator or CombinedIterator()
    
    def __call__(self, config):
        """
        Return a 1-minimal failing subset of the initial configuration.
        
        :param config: The initial configuration that will be reduced.
        :return: 1-minimal failing configuration.
        :raises ReductionException: If reduction could not run until completion.
            The ``result`` attribute of the exception contains the smallest,
            potentially non-minimal, but failing configuration found during
            reduction.
        """
        for iter_cnt in itertools.count():
            logger.info('Iteration #%d', iter_cnt)
            self._iteration_prefix = self._id_prefix + (f'i{iter_cnt}',)
            changed = False
            subsets = [config]
            complement_offset = 0
            
            for run in itertools.count():
                logger.info('Run #%d', run)
                logger.info('\tConfig size: %d', len(config))
                assert self._test_config(config, (f'r{run}', 'assert')) is Outcome.FAIL
                
                # Minimization ends if the configuration is already reduced to a single unit.
                if len(config) < 2:
                    logger.info('\tGranularity: %d', len(subsets))
                    break
                
                if len(subsets) < 2:
                    assert len(subsets) == 1
                    subsets = self._split(subsets)
                
                logger.info('\tGranularity: %d', len(subsets))
                
                try:
                    next_subsets, complement_offset = self._reduce_config(run, subsets, complement_offset)
                except ReductionStopped as e:
                    logger.info('\tStopped')
                    e.result = config
                    raise
                except Exception as e:
                    logger.info('\tErrored')
                    raise ReductionError(str(e), result=config) from e
                
                if next_subsets is not None:
                    changed = True
                    # Interesting configuration is found, continue reduction with this configuration.
                    subsets = next_subsets
                    config = [c for s in subsets for c in s]
                    
                    logger.info('\tReduced')
                
                elif len(subsets) < len(config):
                    # No interesting configuration is found but it is still not the finest splitting, start new iteration.
                    next_subsets = self._split(subsets)
                    complement_offset = (complement_offset * len(next_subsets)) // len(subsets)
                    subsets = next_subsets
                    
                    logger.info('\tIncreased granularity')
                
                else:
                    # Current iteration ends if no interesting configuration was found by the finest splitting.
                    break
            
            if not changed:
                break
        
        logger.info('\tDone')
        return config
    
    def _reduce_config(self, run, subsets, complement_offset):
        """
        Perform the reduce task of ddmin.
        
        :param run: The index of the current iteration.
        :param subsets: List of sets that the current configuration is split to.
        :param complement_offset: A compensation offset needed to calculate the
            index of the first unchecked complement (optimization purpose only).
        :return: Tuple: (list of subsets composing the failing config or None,
            next complement_offset).
        """
        n = len(subsets)
        fvalue = n
        for i in self._config_iterator(n):
            if i >= 0:
                config_id = (f'r{run}', f's{i}')
                config_set = subsets[i]
            else:
                i = (-i - 1 + complement_offset) % n
                config_id = (f'r{run}', f'c{i}')
                config_set = [c for si, s in enumerate(subsets) for c in s if si != i]
                i = -i - 1
            
            # Get the outcome either from cache or by testing it.
            outcome = self._lookup_cache(config_set, config_id)
            if outcome is None:
                outcome = self._test_config(config_set, config_id)
            if outcome is Outcome.FAIL:
                fvalue = i
                break
        
        # fvalue contains the index of the cycle in the previous loop
        # which was found interesting. Otherwise it's n.
        if fvalue < 0:
            # Interesting complement is found.
            # In next run, start removing the following subset
            fvalue = -fvalue - 1
            return subsets[:fvalue] + subsets[fvalue + 1:], fvalue
        if fvalue < n:
            # Interesting subset is found.
            return [subsets[fvalue]], 0
        
        return None, complement_offset
    
    def _lookup_cache(self, config, config_id):
        """
        Perform a cache lookup if caching is enabled.
        
        :param config: The configuration we are looking for.
        :param config_id: The ID describing the configuration (only for debug
            message).
        :return: None if outcome is not found for config in cache or if caching
            is disabled, PASS or FAIL otherwise.
        """
        cached_result = self._cache.lookup(config)
        
        return cached_result
    
    def _test_config(self, config, config_id):
        """
        Test a single configuration and save the result in cache.
        
        :param config: The current configuration to test.
        :param config_id: Unique ID that will be used to save tests to easily
            identifiable directories.
        :return: PASS or FAIL
        """
        config_id = self._iteration_prefix + config_id
        
        outcome = self._test(config, config_id)
        
        if 'assert' not in config_id:
            self._cache.add(config, outcome)
        
        return outcome
    