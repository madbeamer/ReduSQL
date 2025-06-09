import logging
from concurrent.futures import ALL_COMPLETED, FIRST_COMPLETED, ThreadPoolExecutor, wait
from os import cpu_count
from threading import Lock

from src.redusql.dd import DD
from src.redusql.outcome import Outcome

logger = logging.getLogger(__name__)


class SharedCache:
    def __init__(self, cache):
        self._cache = cache
        self._lock = Lock()
    
    def add(self, config, result):
        with self._lock:
            self._cache.add(config, result)
    
    def lookup(self, config):
        with self._lock:
            return self._cache.lookup(config)
    
    def clear(self):
        with self._lock:
            self._cache.clear()
    
    def __str__(self):
        with self._lock:
            return self._cache.__str__()


class ParallelDD(DD):
    """
    Parallel version of the Delta Debugging algorithm.
    """
    
    def __init__(self, test, *, id_prefix=None,
                 config_iterator=None, proc_num=None):
        super().__init__(test=test, id_prefix=id_prefix, 
                         config_iterator=config_iterator)
        self._cache = SharedCache(self._cache)
        
        self._proc_num = proc_num or cpu_count()
    
    def _reduce_config(self, run, subsets, complement_offset):
        """
        Perform the reduce task using multiple processes. Subset and complement
        set tests are mixed and don't wait for each other.
        """
        n = len(subsets)
        fvalue = n
        tests = set()
        
        with ThreadPoolExecutor(self._proc_num) as pool:
            for i in self._config_iterator(n):
                results, tests = wait(tests, timeout=0 if len(tests) < self._proc_num else None, 
                                     return_when=FIRST_COMPLETED)
                for result in results:
                    index, outcome = result.result()
                    if outcome is Outcome.FAIL:
                        fvalue = index
                        break
                if fvalue < n:
                    break
                
                if i >= 0:
                    config_id = (f'r{run}', f's{i}')
                    config_set = subsets[i]
                else:
                    i = (-i - 1 + complement_offset) % n
                    config_id = (f'r{run}', f'c{i}')
                    config_set = [c for si, s in enumerate(subsets) for c in s if si != i]
                    i = -i - 1
                
                # If we checked this test before, return its result
                outcome = self._lookup_cache(config_set, config_id)
                if outcome is Outcome.PASS:
                    continue
                if outcome is Outcome.FAIL:
                    fvalue = i
                    break
                
                tests.add(pool.submit(self._test_config_with_index, i, config_set, config_id))
            
            results, _ = wait(tests, return_when=ALL_COMPLETED)
            if fvalue == n:
                for result in results:
                    index, outcome = result.result()
                    if outcome is Outcome.FAIL:
                        fvalue = index
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
    
    def _test_config_with_index(self, index, config, config_id):
        return index, self._test_config(config, config_id)
    