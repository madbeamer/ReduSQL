#!/bin/bash
# Test script for ReduSQL - CRASH(3.26.0) oracle
# This script checks if a SQL query crashes SQLite 3.26.0
# Usage: ./test_crash_3_26_0.sh <path_to_sql_file>

# Check if SQL file path is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <path_to_sql_file>"
    exit 1
fi

SQL_FILE="$1"

# Check if SQL file exists
if [ ! -f "$SQL_FILE" ]; then
    echo "Error: SQL file not found: $SQL_FILE"
    exit 1
fi

# Function to check if output contains invalid error patterns
has_invalid_errors() {
    local output="$1"
    
    # Check for common invalid error patterns (case-insensitive)
    if echo "$output" | grep -qi "not currently supported" || \
       echo "$output" | grep -qi "syntax error" || \
       echo "$output" | grep -qi "no such" || \
       echo "$output" | grep -qi "parse error" || \
       echo "$output" | grep -qi "no query solution" || \
       echo "$output" | grep -qi "has no column named" || \
       echo "$output" | grep -qi "incomplete input" || \
       echo "$output" | grep -qi "unrecognized token" || \
       echo "$output" | grep -qi "malformed" || \
       echo "$output" | grep -qi "expected.*but got" || \
       echo "$output" | grep -qi "unexpected token" || \
       echo "$output" | grep -qi "missing" || \
       echo "$output" | grep -qi "invalid syntax" || \
       echo "$output" | grep -qi "near.*syntax error" || \
       echo "$output" | grep -qi "incomplete SQL" || \
       echo "$output" | grep -qi "unbalanced" || \
       echo "$output" | grep -qi "unterminated"; then
       return 0  # Has invalid errors
    fi
    
    return 1  # No invalid errors found
}

# Function to check for crash in SQLite 3.26.0
check_crash() {
    local sqlite_version="3.26.0"
    local sqlite_path="/usr/bin/sqlite3-$sqlite_version"
    
    echo "Checking for crash with SQLite $sqlite_version"
    
    if [ ! -f "$sqlite_path" ]; then
        echo "Warning: SQLite $sqlite_version not found at $sqlite_path"
        return 1
    fi
    
    # Run SQLite with the query and check if it crashes
    # Redirect stderr to stdout to capture crash messages
    output=$("$sqlite_path" < "$SQL_FILE" 2>&1)
    exit_code=$?
    
    echo "SQLite exit code: $exit_code"
    
    # First check for invalid errors that should disqualify the test
    if has_invalid_errors "$output"; then
        echo "SQLite output contains invalid errors - test invalid"
        echo "SQLite output: $output"
        return 1  # Test invalid
    fi
    
    # Non-zero exit code typically indicates a crash (but only if no invalid errors)
    if [ $exit_code -ne 0 ]; then
        echo "SQLite error output: $output"
        echo "Crash detected! (non-zero exit code)"
        return 0  # Bug detected (crash occurred)
    fi
    
    echo "No crash detected"
    return 1  # No bug detected
}

# Main testing logic
echo "Testing SQL file: $SQL_FILE"
echo "Oracle type: CRASH(3.26.0)"
echo "---"

if check_crash; then
    echo "Result: Bug still occurs (crash in 3.26.0)"
    exit 0  # Bug still occurs
else
    echo "Result: Bug no longer occurs (no crash or invalid test)"
    exit 1  # Bug no longer occurs or test is invalid
fi
