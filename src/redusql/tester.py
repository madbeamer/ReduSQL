import os
import subprocess
import tempfile
from pathlib import Path

from src.redusql.outcome import Outcome
from src.redusql.tokenizer import SQLTokenizer


class SubprocessTest:
    """
    Test class that executes a test script as a subprocess.
    """
    
    def __init__(self, *, test_builder, command_pattern, filename, timeout=30, verbose=False):
        """
        Initialize subprocess test.
        
        :param test_builder: Callable that builds test content from config.
        :param command_pattern: Command pattern for test script execution.
        :param filename: Base filename for test files.
        :param timeout: Timeout for subprocess execution.
        :param verbose: Enable verbose output.
        """
        self._test_builder = test_builder
        self._command_pattern = command_pattern
        self._filename = filename
        self._timeout = timeout
        self._verbose = verbose
    
    def __call__(self, config, config_id):
        """
        Execute test for a given configuration.
        
        :param config: Configuration (list of token indices).
        :param config_id: Unique identifier for this test.
        :return: Outcome.PASS or Outcome.FAIL
        """
        # Build test content from configuration
        test_content = self._test_builder(config)
        
        # Create temporary file instead of using work directory
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', 
                                         encoding='utf-8', delete=False) as tmp_file:
            tmp_file.write(test_content)
            test_file_path = tmp_file.name
        
        try:
            # Set up environment with TEST_CASE_LOCATION
            env = os.environ.copy()
            env['TEST_CASE_LOCATION'] = test_file_path
            
            # Build command (no file argument needed since we use environment variable)
            command = self._command_pattern
            
            try:
                if self._verbose:
                    # In verbose mode, show the command and don't capture output
                    print(f"    Running test script: {' '.join(command)}")
                    print(f"    TEST_CASE_LOCATION={test_file_path}")
                    result = subprocess.run(
                        command,
                        text=True,
                        timeout=self._timeout,
                        env=env
                    )
                else:
                    # In non-verbose mode, capture output
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=self._timeout,
                        env=env
                    )
                
                # Exit code 0 means bug is triggered (FAIL)
                # Exit code != 0 means bug is not triggered (PASS)
                outcome = Outcome.FAIL if result.returncode == 0 else Outcome.PASS
                
            except subprocess.TimeoutExpired:
                # Timeout usually means the bug is triggered
                outcome = Outcome.FAIL
            except Exception:
                # Any other exception means we can't determine outcome
                outcome = Outcome.PASS
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(test_file_path)
            except:
                pass
        
        return outcome


class SQLTester:
    """
    High-level SQL tester that wraps SubprocessTest with SQL-specific logic.
    """
    
    def __init__(self, test_script, filename='query.sql', timeout=30, verbose=False):
        """
        Initialize SQL tester.
        
        :param test_script: Path to the test script.
        :param filename: Base filename for SQL test files.
        :param timeout: Timeout for test execution.
        :param verbose: Enable verbose output.
        """
        self._test_script = Path(test_script)
        self._filename = filename
        self._timeout = timeout
        self._verbose = verbose
        
        # Validate test script
        if not self._test_script.exists():
            raise FileNotFoundError(f"Test script not found: {test_script}")
        if not os.access(self._test_script, os.X_OK):
            raise PermissionError(f"Test script is not executable: {test_script}")
    
    def create_subprocess_test(self, test_builder, **kwargs):
        """
        Create a SubprocessTest instance with the given test builder.
        
        :param test_builder: Test builder for creating test content.
        :param kwargs: Additional arguments passed to SubprocessTest.
        :return: SubprocessTest instance.
        """
        # Use verbose from kwargs if provided, otherwise use self._verbose
        verbose = kwargs.get('verbose', self._verbose)
        
        return SubprocessTest(
            test_builder=test_builder,
            command_pattern=[str(self._test_script)],  # No '%s' placeholder needed
            filename=self._filename,
            timeout=self._timeout,
            verbose=verbose
        )
    
    def test_tokens_directly(self, tokens):
        """
        Test tokens directly without using the DD framework.
        Useful for validation and debugging.
        
        :param tokens: List of SQL tokens to test.
        :return: True if bug is triggered, False otherwise.
        """
        
        sql_content = SQLTokenizer.detokenize(tokens)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', 
                                         encoding='utf-8', delete=False) as tmp_file:
            tmp_file.write(sql_content)
            tmp_file_path = tmp_file.name
        
        try:
            if self._verbose:
                print(f"    Running test script: {self._test_script}")
                print(f"    TEST_CASE_LOCATION={tmp_file_path}")
            
            # Set up environment with TEST_CASE_LOCATION
            env = os.environ.copy()
            env['TEST_CASE_LOCATION'] = tmp_file_path
            
            result = subprocess.run(
                [str(self._test_script)],  # No file argument
                capture_output=not self._verbose,
                text=True,
                cwd=str(self._test_script.parent),
                timeout=self._timeout,
                env=env
            )
            
            if not self._verbose and result.stderr and result.stderr.strip():
                print(f"    Test script stderr: {result.stderr.strip()}")
            
            # Exit code 0 means the bug still occurs
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            if self._verbose:
                print("Warning: Test script timed out (assuming bug still occurs)")
            return True
        except Exception as e:
            if self._verbose:
                print(f"Error running test script: {e}")
            return False
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_file_path)
            except:
                pass
