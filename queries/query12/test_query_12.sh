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

# Function to check for differential output behavior
check_output_diff() {
    local sqlite_old="/usr/bin/sqlite3-3.26.0"
    local sqlite_new="/usr/bin/sqlite3-3.39.4"
    
    echo "Checking differential output between SQLite versions"
    
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
    echo "$output_old Exit code: $exit_old"
    
    echo "3.39.4"
    echo "$output_new Exit code: $exit_new"
    
    # Check for the specific differential pattern we're interested in:
    # Both versions should have exit code 0 (success)
    # But their outputs should be different
    
    if [ $exit_old -eq 0 ] && [ $exit_new -eq 0 ] && [ "$output_old" != "$output_new" ]; then
        echo "Target differential behavior detected: Both succeed but produce different outputs"
        return 0
    fi
    
    # All other cases are not the differential pattern we're looking for
    echo "Target differential behavior not detected"
    if [ $exit_old -ne 0 ]; then
        echo "  - 3.26.0 did not succeed (exit code: $exit_old)"
    fi
    if [ $exit_new -ne 0 ]; then
        echo "  - 3.39.4 did not succeed (exit code: $exit_new)"
    fi
    if [ $exit_old -eq 0 ] && [ $exit_new -eq 0 ] && [ "$output_old" = "$output_new" ]; then
        echo "  - Both versions succeeded but produced identical outputs"
    fi
    
    return 1
}

# Main testing logic
echo "Testing SQL file: $SQL_FILE"
echo "Oracle type: DIFF"
echo "---"

if check_output_diff; then
    echo "Result: Target differential behavior found (both succeed, different outputs)"
    exit 0  # Target differential bug detected
else
    echo "Result: Target differential behavior not found"
    exit 1  # Not the specific differential pattern we're looking for
fi
