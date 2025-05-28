class ReductionException(Exception):
    """
    Base class of reduction-related exceptions. In addition to signal the
    premature termination of a reduction process, exception instances contain
    the intermediate result of the reduction.
    
    :ivar result: A representation of the smallest, potentially non-minimal, but
        failing test case found during reduction.
    """
    
    def __init__(self, *args, result=None):
        super().__init__(*args)
        self.result = result


class ReductionStopped(ReductionException):
    """
    Exception to signal that reduction has been stopped, e.g., because some time
    limit or test count limit has been reached.
    """
    pass


class ReductionError(ReductionException):
    """
    Exception to signal that an unexpected error occurred during reduction.
    """
    pass
