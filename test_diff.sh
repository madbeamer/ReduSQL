#!/bin/bash
# Test script for ReduSQL - DIFF oracle
# This script checks if a SQL query produces different behavior between SQLite versions
# Usage: ./test_diff.sh <path_to_sql_file>

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

# Function to check for differential behavior
check_diff() {
    local sqlite_old="/usr/bin/sqlite3-3.26.0"
    local sqlite_new="/usr/bin/sqlite3-3.39.4"
    
    echo "Checking differential behavior between SQLite versions"
    
    # Check if both SQLite versions exist
    if [ ! -f "$sqlite_old" ]; then
        echo "Warning: SQLite 3.26.0 not found at $sqlite_old"
        return 1
    fi
    
    if [ ! -f "$sqlite_new" ]; then
        echo "Warning: SQLite 3.39.4 not found at $sqlite_new"
        return 1
    fi
    
    # Run query on both versions and capture output
    echo "Running on SQLite 3.26.0..."
    output_old=$("$sqlite_old" < "$SQL_FILE" 2>&1)
    exit_old=$?
    
    echo "Running on SQLite 3.39.4..."
    output_new=$("$sqlite_new" < "$SQL_FILE" 2>&1)
    exit_new=$?
    
    echo "Old version exit code: $exit_old"
    echo "New version exit code: $exit_new"
    
    # Check for invalid errors in both outputs
    if has_invalid_errors "$output_old"; then
        echo "SQLite 3.26.0 output contains invalid errors - test invalid"
        echo "Old output: $output_old"
        return 1  # Test invalid
    fi
    
    if has_invalid_errors "$output_new"; then
        echo "SQLite 3.39.4 output contains invalid errors - test invalid"  
        echo "New output: $output_new"
        return 1  # Test invalid
    fi
    
    # Check if outputs differ (only if both are valid)
    if [ "$output_old" != "$output_new" ] || [ $exit_old -ne $exit_new ]; then
        echo "Different behavior detected!"
        echo "Old output: $output_old"
        echo "New output: $output_new"
        return 0  # Bug detected (different behavior)
    fi
    
    echo "No differential behavior detected"
    return 1  # No bug detected
}

# Main testing logic
echo "Testing SQL file: $SQL_FILE"
echo "Oracle type: DIFF"
echo "---"

if check_diff; then
    echo "Result: Bug still occurs (differential behavior)"
    exit 0  # Bug still occurs
else
    echo "Result: Bug no longer occurs (same behavior or invalid)"
    exit 1  # Bug no longer occurs or test is invalid
fi
