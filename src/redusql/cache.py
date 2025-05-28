from src.redusql.outcome import Outcome


class Cache:
    """
    Simple cache implementation based on Zeller's original caching approach.
    
    The cache associates configurations (i.e., lists of elements) with their test
    outcomes, using a tree as the underlying data structure.
    """
    
    class _Entry:
        """
        This class holds test outcomes for configurations. This avoids running
        the same test twice.
        
        The outcome cache is implemented as a tree. Each node points to the
        outcome of the remaining list.
        
        Example: ([1, 2, 3], PASS), ([1, 2], FAIL), ([1, 4, 5], FAIL):
        
             (2, FAIL)--(3, PASS)
            /
        (1, None)
            \
             (4, None)--(5, FAIL)
        """
        
        def __init__(self):
            self.result = None  # Result so far
            self.tail = {}  # Points to outcome of tail
    
    def __init__(self, *, evict_after_fail=True):
        """
        Initialize the cache.
        
        :param evict_after_fail: When a configuration with a FAIL outcome is
            added to the cache, evict all larger configurations.
        """
        # NOTE: evict_after_fail=True should be safe as after a fail is found,
        # reduction continues from there, generating only even smaller test
        # cases, and larger tests are never re-tested again.
        self._evict_after_fail = evict_after_fail
        self._root = self._Entry()
    
    def _evict(self, p, length):
        """
        Evict all cached entries larger than the given length.
        
        :param p: Current cache entry node.
        :param length: Length threshold for eviction.
        """
        if length == 0:
            p.tail = {}
            return
        
        # Use iterative approach to avoid recursion depth issues
        stack = [(p, length)]
        while stack:
            current_p, current_length = stack.pop()
            if current_length == 0:
                current_p.tail = {}
            else:
                for e in current_p.tail.values():
                    stack.append((e, current_length - 1))
    
    def add(self, config, result):
        """
        Add a new configuration to the cache.
        
        :param config: The configuration to save.
        :param result: The outcome of the added configuration.
        """
        if result is Outcome.PASS:
            p = self._root
            for cs in config:
                if cs not in p.tail:
                    p.tail[cs] = self._Entry()
                p = p.tail[cs]
            p.result = result
        
        if result is Outcome.FAIL and self._evict_after_fail:
            self._evict(self._root, len(config))
    
    def lookup(self, config):
        """
        Cache lookup to find out the outcome of a given configuration.
        
        :param config: The configuration we are looking for.
        :return: PASS or FAIL if config is in the cache; None, otherwise.
        """
        p = self._root
        for cs in config:
            if cs not in p.tail:
                return None
            p = p.tail[cs]
        return p.result
    
    def clear(self):
        """Clear the cache."""
        self._root = self._Entry()
    
    def __str__(self):
        """Return string representation of the cache for debugging."""
        def _str(p):
            if p.result is not None:
                s.append(f'\t[{", ".join(repr(cs) for cs in config)}]: {p.result.name!r},\n')
            for cs, e in sorted(p.tail.items()):
                config.append(cs)
                _str(e)
                config.pop()
        
        config, s = [], []
        s.append('{\n')
        _str(self._root)
        s.append('}')
        return ''.join(s)
    