class SQLTokenizer:
    """Tokenizes SQL queries according to SQL token rules."""
    
    @staticmethod
    def tokenize(sql_text):
        """
        Tokenize SQL text into tokens, skipping whitespace.
        
        Args:
            sql_text: The SQL query text to tokenize
            
        Returns:
            list: List of tokens (whitespace excluded)
        """
        tokens = []
        i = 0
        sql_text = sql_text.strip()
        
        while i < len(sql_text):
            # Skip whitespace completely
            if sql_text[i].isspace():
                while i < len(sql_text) and sql_text[i].isspace():
                    i += 1
                continue
            
            # Handle comments
            if i < len(sql_text) - 1:
                # SQL line comments --
                if sql_text[i:i+2] == '--':
                    start = i
                    while i < len(sql_text) and sql_text[i] != '\n':
                        i += 1
                    tokens.append(sql_text[start:i])
                    continue
                
                # SQL block comments /* */
                elif sql_text[i:i+2] == '/*':
                    start = i
                    i += 2
                    while i < len(sql_text) - 1:
                        if sql_text[i:i+2] == '*/':
                            i += 2
                            break
                        i += 1
                    tokens.append(sql_text[start:i])
                    continue
            
            # Handle string constants (single quotes)
            if sql_text[i] == "'":
                start = i
                i += 1
                while i < len(sql_text):
                    if sql_text[i] == "'":
                        if i + 1 < len(sql_text) and sql_text[i + 1] == "'":
                            # Escaped quote
                            i += 2
                        else:
                            i += 1
                            break
                    else:
                        i += 1
                tokens.append(sql_text[start:i])
                continue
            
            # Handle delimited identifiers (double quotes)
            if sql_text[i] == '"':
                start = i
                i += 1
                while i < len(sql_text):
                    if sql_text[i] == '"':
                        if i + 1 < len(sql_text) and sql_text[i + 1] == '"':
                            # Escaped quote
                            i += 2
                        else:
                            i += 1
                            break
                    else:
                        i += 1
                tokens.append(sql_text[start:i])
                continue
            
            # Handle operators and special characters
            special_chars = "()[]{},.;:+-*/=<>!|&^%~?"
            if sql_text[i] in special_chars:
                # Check for multi-character operators
                if i < len(sql_text) - 1:
                    two_char = sql_text[i:i+2]
                    if two_char in ['<=', '>=', '<>', '!=', '||', '&&', '<<', '>>', '+=', '-=', '*=', '/=', '%=']:
                        tokens.append(two_char)
                        i += 2
                        continue
                
                tokens.append(sql_text[i])
                i += 1
                continue
            
            # Handle numeric constants
            if sql_text[i].isdigit() or sql_text[i] == '.':
                start = i
                has_dot = False
                has_e = False
                
                while i < len(sql_text):
                    if sql_text[i].isdigit():
                        i += 1
                    elif sql_text[i] == '.' and not has_dot:
                        has_dot = True
                        i += 1
                    elif sql_text[i].lower() == 'e' and not has_e:
                        has_e = True
                        i += 1
                        if i < len(sql_text) and sql_text[i] in '+-':
                            i += 1
                    else:
                        break
                
                tokens.append(sql_text[start:i])
                continue
            
            # Handle identifiers and keywords
            if sql_text[i].isalpha() or sql_text[i] == '_':
                start = i
                while i < len(sql_text) and (sql_text[i].isalnum() or sql_text[i] == '_'):
                    i += 1
                tokens.append(sql_text[start:i])
                continue
            
            # Handle any other character as individual token
            tokens.append(sql_text[i])
            i += 1
        
        return tokens
    
    @staticmethod
    def detokenize(tokens):
        """
        Reconstruct SQL text from tokens by adding appropriate spacing.
        
        Args:
            tokens: List of tokens
            
        Returns:
            str: Reconstructed SQL text with proper spacing
        """
        if not tokens:
            return ""
        
        result = []
        
        for i, token in enumerate(tokens):
            # Add the current token
            result.append(token)
            
            # Add space after token if needed (but not after the last token)
            if i < len(tokens) - 1:
                next_token = tokens[i + 1]
                
                # Don't add space in these cases:
                if (
                    # Before or after parentheses, brackets, commas, semicolons
                    token in '([{' or next_token in ')]},.;' or
                    # Around operators (they're often written without spaces)
                    token in '+-*/=<>!|&^%~' or next_token in '+-*/=<>!|&^%~' or
                    # Before/after multi-character operators
                    token in ['<=', '>=', '<>', '!=', '||', '&&'] or 
                    next_token in ['<=', '>=', '<>', '!=', '||', '&&'] or
                    # Don't space around dots in numbers
                    token == '.' or next_token == '.' or
                    # Comments already include their spacing
                    token.startswith('--') or token.startswith('/*')
                ):
                    continue
                else:
                    # Add space between most other tokens
                    result.append(' ')
        
        return ''.join(result)


class TestBuilder:
    """
    Builds test content from configurations.
    """
    
    def __init__(self, atoms, atom_type='token'):
        """
        Initialize test builder.
        
        :param atoms: List of atoms (tokens or lines).
        :param atom_type: Type of atoms ('token' or 'line').
        """
        self._atoms = atoms
        self._atom_type = atom_type
    
    def __call__(self, config):
        """
        Build test content from a configuration.
        
        :param config: List of atom indices to include.
        :return: SQL text built from the selected atoms.
        """
        selected_atoms = [self._atoms[i] for i in config]
        if self._atom_type == 'line':
            return ''.join(selected_atoms)  # Lines already have newlines
        else:  # token
            return SQLTokenizer.detokenize(selected_atoms)
        