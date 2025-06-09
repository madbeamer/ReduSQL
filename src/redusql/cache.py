from src.redusql.outcome import Outcome


class Cache:
    class _Entry:
        def __init__(self):
            self.result = None
            self.tail = {}
    
    def __init__(self, *, evict_after_fail=True):
        self._evict_after_fail = evict_after_fail
        self._root = self._Entry()
    
    def _evict(self, p, length):
        """
        Evict all cached entries larger than the given length.
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
        """
        p = self._root
        for cs in config:
            if cs not in p.tail:
                return None
            p = p.tail[cs]
        return p.result
    
    def clear(self):
        self._root = self._Entry()
    