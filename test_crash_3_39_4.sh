#!/bin/bash
# Test script for ReduSQL - CRASH(3.39.4) oracle
# This script checks if a SQL query crashes SQLite 3.39.4
# Usage: ./test_crash_3_39_4.sh <path_to_sql_file>

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

# Function to check for crash in SQLite 3.39.4
check_crash() {
    local sqlite_version="3.39.4"
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
    
    # Non-zero exit code typically indicates a crash
    if [ $exit_code -ne 0 ]; then
        echo "SQLite error output: $output"
        # Check for common crash indicators
        if echo "$output" | grep -qE "(Segmentation fault|core dumped|Assertion failed|runtime error)"; then
            echo "Crash detected!"
            return 0  # Bug detected (crash occurred)
        fi
    fi
    
    echo "No crash detected"
    return 1  # No bug detected
}

# Main testing logic
echo "Testing SQL file: $SQL_FILE"
echo "Oracle type: CRASH(3.39.4)"
echo "---"

if check_crash; then
    echo "Result: Bug still occurs (crash in 3.39.4)"
    exit 0  # Bug still occurs
else
    echo "Result: Bug no longer occurs (no crash in 3.39.4)"
    exit 1  # Bug no longer occurs
fi
