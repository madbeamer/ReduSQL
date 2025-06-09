import logging
from antlr4 import InputStream, CommonTokenStream, Token
from src.redusql.antlr4.SQLiteLexer import SQLiteLexer
from src.redusql.antlr4.SQLiteParser import SQLiteParser

logger = logging.getLogger(__name__)


class SQLTokenizer:
    @staticmethod
    def tokenize(sql_text: str):
        """
        Tokenize SQL text using ANTLR SQLite lexer.
        """
        try:
            input_stream = InputStream(sql_text)

            lexer = SQLiteLexer(input_stream)
            token_stream = CommonTokenStream(lexer)

            token_stream.fill()
            
            # Extract token texts (excluding EOF and whitespace tokens)
            tokens = []
            for token in token_stream.tokens:
                # Skip EOF tokens and whitespace-only tokens
                if (token.type != Token.EOF and 
                    token.text.strip() and 
                    token.channel == 0):
                    tokens.append(token.text)
            
            return tokens
            
        except Exception as e:
            logger.error(f"Failed to tokenize SQL: {e}")
            # Fallback to line-based tokenization
            return sql_text.splitlines(True)
    
    
    @staticmethod
    def detokenize(tokens):
        """
        Convert tokens back to SQL text.
        """
        if not tokens:
            return ""

        # Simple concatenation with spaces between tokens
        result = ""
        for i, token in enumerate(tokens):
            # Check if we should add a space before this token
            if i > 0 and not result.endswith('\n'):
                # Add space between tokens, except for certain punctuation
                prev_token = tokens[i-1]
                if (not token.startswith(('(', ')', ';', ',', '.')) and 
                    not prev_token.endswith(('(', '.')) and
                    prev_token not in ('(', '.')):
                    result += " "
            result += token

            # Add newline after semicolon
            if token == ';':
                result += "\n"

        return result
    
    @staticmethod
    def validate_sql(sql_text: str) -> bool:
        """
        Validate that SQL text can be parsed successfully.
        """
        try:
            input_stream = InputStream(sql_text)
            lexer = SQLiteLexer(input_stream)
            token_stream = CommonTokenStream(lexer)
            parser = SQLiteParser(token_stream)
            
            # Try to parse
            parse_tree = parser.parse()
            return True
            
        except Exception:
            return False
        