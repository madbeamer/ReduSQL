from enum import Enum


class Outcome(Enum):
    """Enumeration of possible test outcomes."""
    
    PASS = 'PASS'  # Test passed (bug not triggered)
    FAIL = 'FAIL'  # Test failed (bug triggered)
    
    def __repr__(self):
        return f'<{self.__class__.__name__}.{self.name}>'
    