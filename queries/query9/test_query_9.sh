#!/bin/bash

# Check if TEST_CASE_LOCATION environment variable is set
if [ -z "$TEST_CASE_LOCATION" ]; then
    echo "Error: TEST_CASE_LOCATION environment variable is not set"
    exit 1
fi

SQL_FILE="$TEST_CASE_LOCATION"

# Check if SQL file exists
if [ ! -f "$SQL_FILE" ]; then
    echo "Error: SQL file not found: $SQL_FILE"
    exit 1
fi

# Function to check for segmentation fault in SQLite 3.26.0
check_segfault() {
    local sqlite_version="3.26.0"
    local sqlite_path="/usr/bin/sqlite3-$sqlite_version"
    
    echo "Checking for segmentation fault with SQLite $sqlite_version"
    
    if [ ! -f "$sqlite_path" ]; then
        echo "Warning: SQLite $sqlite_version not found at $sqlite_path"
        return 1
    fi
    
    # Run SQLite with the query and capture stderr
    output=$("$sqlite_path" < "$SQL_FILE" 2>&1)
    exit_code=$?
    
    echo "SQLite exit code: $exit_code"
    echo "SQLite output: $output"
    
    # Check if exit code is 139 (segmentation fault)
    if [ $exit_code -eq 139 ]; then
        echo "Segmentation fault detected! (exit code 139)"
        return 0  # Bug detected (segmentation fault occurred)
    fi
    
    echo "No segmentation fault detected"
    return 1  # No segmentation fault detected
}

# Main testing logic
echo "Testing SQL file: $SQL_FILE"
echo "Oracle type: SEGFAULT(3.26.0)"
echo "---"

if check_segfault; then
    echo "Result: Bug still occurs (segmentation fault in 3.26.0)"
    exit 0  # Bug still occurs
else
    echo "Result: Bug no longer occurs (no segmentation fault)"
    exit 1  # Bug no longer occurs
fi
