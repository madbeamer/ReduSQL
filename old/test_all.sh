#!/bin/bash
# Sample test script for ReduSQL
# This script checks if a SQL query still triggers a bug
# Usage: ./test.sh <path_to_sql_file>

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

# Get the directory containing the SQL file to look for oracle.txt
SQL_DIR="$(dirname "$SQL_FILE")"

# Read the oracle type from oracle.txt (if available)
# Look for oracle.txt in the same directory as the SQL file
ORACLE_FILE="$SQL_DIR/oracle.txt"

if [ -f "$ORACLE_FILE" ]; then
    ORACLE=$(cat "$ORACLE_FILE")
    echo "Found oracle file: $ORACLE_FILE"
    echo "Oracle type: $ORACLE"
else
    # Default to CRASH detection if no oracle file
    ORACLE="CRASH(3.26.0)"
    echo "No oracle file found, using default: $ORACLE"
fi

# Function to check for crash
check_crash() {
    local sqlite_version="$1"
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

# Function to check for differential behavior
check_diff() {
    local sqlite_old="/usr/bin/sqlite3-3.26.0"
    local sqlite_new="/usr/bin/sqlite3-3.39.4"
    
    echo "Checking differential behavior between SQLite versions"
    
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

# Main testing logic based on oracle type
echo "Testing SQL file: $SQL_FILE"
echo "Oracle type: $ORACLE"
echo "---"

case "$ORACLE" in
    CRASH\(3.26.0\))
        if check_crash "3.26.0"; then
            echo "Result: Bug still occurs (crash in 3.26.0)"
            exit 0  # Bug still occurs
        else
            echo "Result: Bug no longer occurs (no crash in 3.26.0)"
            exit 1  # Bug no longer occurs
        fi
        ;;
    CRASH\(3.39.4\))
        if check_crash "3.39.4"; then
            echo "Result: Bug still occurs (crash in 3.39.4)"
            exit 0  # Bug still occurs
        else
            echo "Result: Bug no longer occurs (no crash in 3.39.4)"
            exit 1  # Bug no longer occurs
        fi
        ;;
    DIFF)
        if check_diff; then
            echo "Result: Bug still occurs (differential behavior)"
            exit 0  # Bug still occurs
        else
            echo "Result: Bug no longer occurs (same behavior)"
            exit 1  # Bug no longer occurs
        fi
        ;;
    *)
        echo "Unknown oracle type: $ORACLE"
        exit 1
        ;;
esac
