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
    
    # Check if outputs differ
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
    echo "Result: Bug no longer occurs (same behavior)"
    exit 1  # Bug no longer occurs
fi
