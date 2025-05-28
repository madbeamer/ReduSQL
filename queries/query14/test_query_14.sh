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

# Function to check for "database disk image is malformed fault" in SQLite 3.26.0
check_disk_image_malformed() {
    local sqlite_version="3.26.0"
    local sqlite_path="/usr/bin/sqlite3-$sqlite_version"

    echo "Checking for database disk image is malformed fault with SQLite $sqlite_version"

    if [ ! -f "$sqlite_path" ]; then
        echo "Warning: SQLite $sqlite_version not found at $sqlite_path"
        return 1
    fi

    # Run SQLite with the query and capture stderr
    output=$("$sqlite_path" < "$SQL_FILE" 2>&1)
    exit_code=$?

    echo "SQLite exit code: $exit_code"
    echo "SQLite output: $output"

    # Check if output contains "database disk image is malformed"
    if echo "$output" | grep -q "database disk image is malformed"; then
        echo "Database disk image is malformed error detected!"
        return 0  # Bug detected (database disk image is malformed fault occurred)
    fi

    echo "Error not found: Database disk image is not malformed"
    return 1  # Database disk image is not malformed
}

# Main testing logic
echo "Testing SQL file: $SQL_FILE"
echo "Oracle type: CRASH(3.26.0)"
echo "---"

if check_disk_image_malformed; then
    echo "Result: Bug still occurs (database disk image is malformed in 3.26.0)"
    exit 0  # Bug still occurs
else
    echo "Result: Bug no longer occurs (database disk image is not malformed)"
    exit 1  # Bug no longer occurs
fi
