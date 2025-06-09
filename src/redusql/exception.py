class ReductionException(Exception):
    def __init__(self, *args, result=None):
        super().__init__(*args)
        self.result = result


class ReductionStopped(ReductionException):
    pass


class ReductionError(ReductionException):
    pass
