import subprocess
import os
import tempfile
import re
from pathlib import Path


class SQLTokenizer:
    """Tokenizes SQL queries according to SQL token rules."""
    
    @staticmethod
    def tokenize(sql_text):
        """
        Tokenize SQL text into tokens.
        
        Args:
            sql_text: The SQL query text to tokenize
            
        Returns:
            list: List of tokens
        """
        tokens = []
        i = 0
        sql_text = sql_text.strip()
        
        while i < len(sql_text):
            # Skip whitespace but preserve it as tokens for reconstruction
            if sql_text[i].isspace():
                start = i
                while i < len(sql_text) and sql_text[i].isspace():
                    i += 1
                tokens.append(sql_text[start:i])
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
        Reconstruct SQL text from tokens.
        
        Args:
            tokens: List of tokens
            
        Returns:
            str: Reconstructed SQL text
        """
        return ''.join(tokens)


class DeltaDebugger:
    """Delta debugging algorithm for reducing token sequences."""
    
    def __init__(self, test_function, verbose=False):
        """
        Initialize delta debugger.
        
        Args:
            test_function: Function that takes a list of tokens and returns True if bug occurs
            verbose: Enable verbose output
        """
        self.test_function = test_function
        self.test_count = 0
        self.verbose = verbose
    
    def _log(self, message):
        """Log message if verbose is enabled."""
        if self.verbose:
            print(f"  DEBUG: {message}")
    
    def reduce(self, tokens):
        """
        Apply delta debugging to reduce tokens.
        
        Args:
            tokens: List of tokens to reduce
            
        Returns:
            list: Minimal set of tokens that still triggers the bug
        """
        print(f"Starting delta debugging with {len(tokens)} tokens")
        
        # Start with the full set
        current_tokens = tokens[:]
        
        # Delta debugging algorithm
        n = 2  # Initial granularity
        max_iterations = 100  # Prevent infinite loops
        iteration = 0
        
        while len(current_tokens) > 1 and n <= len(current_tokens) and iteration < max_iterations:
            iteration += 1
            chunk_size = max(1, len(current_tokens) // n)
            progress_made = False
            
            print(f"Iteration {iteration}: Trying granularity {n} (chunk size: {chunk_size})")
            self._log(f"Current tokens: {len(current_tokens)}")
            
            # Try removing each chunk
            for i in range(n):
                start_idx = i * chunk_size
                if i == n - 1:  # Last chunk gets remainder
                    end_idx = len(current_tokens)
                else:
                    end_idx = min((i + 1) * chunk_size, len(current_tokens))
                
                if start_idx >= end_idx:
                    continue
                
                # Create subset without this chunk
                subset = current_tokens[:start_idx] + current_tokens[end_idx:]
                
                if len(subset) == 0:
                    self._log(f"Skipping empty subset for chunk {i+1}")
                    continue
                
                print(f"  Testing removal of chunk {i+1}/{n} (tokens {start_idx}-{end_idx-1})")
                self._log(f"Subset size: {len(subset)} tokens")
                
                self.test_count += 1
                if self.test_function(subset):
                    print(f"  ✓ Chunk {i+1} can be removed! Reduced from {len(current_tokens)} to {len(subset)} tokens")
                    current_tokens = subset
                    progress_made = True
                    n = max(2, n - 1)  # Reduce granularity when successful
                    break
                else:
                    print(f"  ✗ Chunk {i+1} is necessary")
            
            if not progress_made:
                # Try smaller chunks
                if n < len(current_tokens):
                    n = min(n * 2, len(current_tokens))
                    self._log(f"Increasing granularity to {n}")
                else:
                    # No more progress possible
                    print("  No more reductions possible at current granularity")
                    break
        
        if iteration >= max_iterations:
            print(f"  Warning: Stopped after {max_iterations} iterations to prevent infinite loop")
        
        print(f"Delta debugging completed. Reduced to {len(current_tokens)} tokens ({self.test_count} tests)")
        return current_tokens


class SQLReducer:
    """Main class for SQL query reduction using delta debugging."""
    
    def __init__(self, query_file, test_script, verbose=False):
        """
        Initialize the SQL reducer.
        
        Args:
            query_file: Path to the SQL query file to reduce
            test_script: Path to the test script that validates reductions
            verbose: Enable verbose output
        """
        self.query_file = Path(query_file)
        self.test_script = Path(test_script)
        self.verbose = verbose
        
        # Validate inputs
        if not self.query_file.exists():
            raise FileNotFoundError(f"Query file not found: {query_file}")
        if not self.test_script.exists():
            raise FileNotFoundError(f"Test script not found: {test_script}")
        if not os.access(self.test_script, os.X_OK):
            raise PermissionError(f"Test script is not executable: {test_script}")
        
        # Read original query and tokenize it
        self.original_query = self.query_file.read_text()
        self.original_tokens = SQLTokenizer.tokenize(self.original_query)
        self.current_tokens = self.original_tokens[:]
        
        print(f"Loaded query with {len(self.original_tokens)} tokens")
        if self.verbose:
            print("Sample tokens:", [repr(t) for t in self.original_tokens[:10]], "...")
        
    def run_test(self, tokens):
        """
        Run the test script with the given tokens.
        
        Args:
            tokens: List of SQL tokens to test
            
        Returns:
            bool: True if the bug still occurs (exit code 0), False otherwise
        """
        # Convert tokens back to SQL text
        query_content = SQLTokenizer.detokenize(tokens)
        
        # Create a temporary file with the query content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as tmp_file:
            tmp_file.write(query_content)
            tmp_file_path = tmp_file.name
        
        try:
            if self.verbose:
                # In verbose mode, show all output from test script
                print(f"    Running test script: {self.test_script} {tmp_file_path}")
                result = subprocess.run(
                    [str(self.test_script), tmp_file_path],
                    cwd=str(self.test_script.parent),
                    timeout=30,
                    text=True
                )
            else:
                # In non-verbose mode, capture output but still show errors
                result = subprocess.run(
                    [str(self.test_script), tmp_file_path],
                    capture_output=True,
                    text=True,
                    cwd=str(self.test_script.parent),
                    timeout=30
                )
                
                # Show stderr if there are errors
                if result.stderr and result.stderr.strip():
                    print(f"    Test script stderr: {result.stderr.strip()}")
            
            # Exit code 0 means the bug still occurs
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            print("Warning: Test script timed out (assuming bug still occurs)")
            return True
        except Exception as e:
            if self.verbose:
                print(f"Error running test script: {e}")
            return False
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_file_path)
            except:
                pass
    
    def delta_debug_reduce(self):
        """
        Apply delta debugging to reduce the SQL query.
        
        Returns:
            list: Reduced list of tokens
        """
        def test_wrapper(tokens):
            """Wrapper function for delta debugger."""
            return self.run_test(tokens)
        
        debugger = DeltaDebugger(test_wrapper, verbose=self.verbose)
        return debugger.reduce(self.current_tokens)
    
    def reduce(self):
        """
        Main reduction loop using delta debugging.
        """
        print(f"Starting reduction of {self.query_file}")
        print(f"Original query has {len(self.original_tokens)} tokens")
        print(f"Using test script: {self.test_script}")
        print("-" * 60)
        
        # First, verify that the original query triggers the bug
        print("Verifying original query triggers the bug...")
        if not self.run_test(self.current_tokens):
            print("ERROR: Original query does not trigger the bug!")
            print("Test script returned exit code 1 for the original query.")
            print("Please check your test script and query file.")
            return None
        
        print("✓ Original query triggers the bug")
        print("-" * 60)
        
        # Apply delta debugging reduction
        print("Applying delta debugging reduction...")
        reduced_tokens = self.delta_debug_reduce()
        
        if reduced_tokens:
            print("✓ Delta debugging completed successfully")
            self.current_tokens = reduced_tokens
        else:
            print("✗ Delta debugging failed - keeping original query")
        
        print("-" * 60)
        print(f"Final query has {len(self.current_tokens)} tokens")
        print(f"Reduction: {len(self.original_tokens) - len(self.current_tokens)} tokens")
        if len(self.original_tokens) > 0:
            print(f"Reduction percentage: {(1 - len(self.current_tokens) / len(self.original_tokens)) * 100:.2f}%")
        
        # Convert back to query text
        reduced_query = SQLTokenizer.detokenize(self.current_tokens)
        return reduced_query
    
    def save_reduced_query(self, output_file=None):
        """
        Save the reduced query to a file.
        
        Args:
            output_file: Path to save the reduced query (optional)
        """
        if output_file is None:
            # Try to determine the query directory name from the input path
            query_dir = self.query_file.parent.name
            if query_dir == "queries":
                # If query is directly in queries/, use the filename as directory
                query_name = self.query_file.stem
            else:
                # If query is in a subdirectory, use that subdirectory name
                query_name = query_dir
            
            # Create output path with query-specific directory
            output_file = Path("/output") / query_name / "reduced_query.sql"
        
        output_path = Path(output_file)
        # Ensure the output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert current tokens to query text
        current_query = SQLTokenizer.detokenize(self.current_tokens)
        
        output_path.write_text(current_query)
        print(f"\nReduced query saved to: {output_file}")
        
        # Also save token information for debugging
        token_info_file = output_path.parent / f"{output_path.stem}_tokens.txt"
        with open(token_info_file, 'w') as f:
            f.write(f"Original tokens: {len(self.original_tokens)}\n")
            f.write(f"Reduced tokens: {len(self.current_tokens)}\n")
            f.write(f"Reduction: {len(self.original_tokens) - len(self.current_tokens)} tokens\n")
            if len(self.original_tokens) > 0:
                f.write(f"Percentage: {(1 - len(self.current_tokens) / len(self.original_tokens)) * 100:.2f}%\n")
            f.write("\nReduced tokens:\n")
            for i, token in enumerate(self.current_tokens):
                f.write(f"{i:3d}: {repr(token)}\n")
        
        print(f"Token information saved to: {token_info_file}")
        