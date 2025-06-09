class Splitter:
    """
    Zeller's splitting algorithm.
    """
    
    def __init__(self, n=2):
        self._n = n
    
    def __call__(self, subsets):
        """
        Split the given subsets using Zeller's algorithm.
        """
        config = [c for s in subsets for c in s]
        length = len(config)
        n = min(length, len(subsets) * self._n)
        next_subsets = []
        start = 0
        
        for i in range(n):
            stop = start + (length - start) // (n - i)
            next_subsets.append(config[start:stop])
            start = stop
            
        return next_subsets
    