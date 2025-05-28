class Splitter:
    """
    Simple splitter that implements Zeller's splitting algorithm.
    
    Splits up the input config into n pieces as used by Zeller in the original
    reference implementation. The approach works iteratively in n steps, first
    slicing off a chunk sized 1/n-th of the original config, then slicing off
    1/(n-1)-th of the remainder, and so on, until the last piece is halved
    (always using integer division).
    """
    
    def __init__(self, n=2):
        """
        Initialize the splitter.
        
        :param n: The split ratio used to determine how many parts (subsets) the
            config to split to (both initially and later on whenever config
            subsets needs to be re-split).
        """
        self._n = n
    
    def __call__(self, subsets):
        """
        Split the given subsets using Zeller's algorithm.
        
        :param subsets: List of sets that the current configuration is split to.
        :return: List of newly split sets.
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
    
    def __str__(self):
        cls = self.__class__
        return f'{cls.__module__}.{cls.__name__}(n={self._n})'
    