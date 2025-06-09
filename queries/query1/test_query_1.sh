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

# Function to check if process crashed (non-zero exit code)
has_crashed() {
    local exit_code="$1"
    
    if [ $exit_code -ne 0 ]; then
        return 0  # True - it crashed
    else
        return 1  # False - it succeeded
    fi
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
    
    echo "3.26.0"
    if [ $exit_old -eq 0 ]; then
        echo "Exit code: 0"
    else
        echo "$output_old Exit code: $exit_old"
    fi
    
    echo "3.39.4"
    if [ $exit_new -eq 0 ]; then
        echo "Exit code: 0"
    else
        echo "$output_new Exit code: $exit_new"
    fi
    
    # Check for the specific differential pattern we're interested in:
    # 3.26.0 should have exit code 0 (success)
    # 3.39.4 should crash (non-zero exit code)
    
    if [ $exit_old -eq 0 ] && has_crashed $exit_new; then
        echo "Target differential behavior detected: 3.26.0 succeeds, 3.39.4 crashes"
        return 0
    fi
    
    # All other cases are not the differential pattern we're looking for
    echo "Target differential behavior not detected"
    if [ $exit_old -ne 0 ]; then
        echo "  - 3.26.0 did not succeed (exit code: $exit_old)"
    fi
    if ! has_crashed $exit_new; then
        echo "  - 3.39.4 did not crash (exit code: $exit_new)"
    fi
    
    return 1
}

# Main testing logic
echo "Testing SQL file: $SQL_FILE"
echo "Oracle type: DIFF"
echo "---"

if check_diff; then
    echo "Result: Target differential behavior found (3.26.0 succeeds, 3.39.4 crashes)"
    exit 0  # Target differential bug detected
else
    echo "Result: Target differential behavior not found"
    exit 1  # Not the specific differential pattern we're looking for
fi
