class TestBuilder:
    def __init__(self, items, mode='token', detokenizer=None):
        self.items = items
        self.mode = mode  
        self.detokenizer = detokenizer
        
        if mode == 'token' and detokenizer is None:
            # Default detokenizer for line mode or fallback
            self.detokenizer = lambda tokens: ' '.join(tokens)
    
    def __call__(self, config):
        """
        Build test content for a given configuration.
        """
        if not config:
            return ""
        
        # Get the selected items
        selected_items = [self.items[i] for i in config if 0 <= i < len(self.items)]
        
        if not selected_items:
            return ""
        
        if self.mode == 'line':
            # For line mode, just join the lines
            return ''.join(selected_items)
        else:
            # For token mode, use the detokenizer
            return self.detokenizer(selected_items)
        