#!/bin/bash

# Path to SQLite executable and database
SQLITE_BIN="/home/test/sqlite/sqlite3-3.26.0"
DB_PATH="/app/databases/test.db"

# Use the file that Perses is currently testing
# Perses sets PERSES_TARGET_FILE environment variable
QUERY_FILE="${PERSES_TARGET_FILE:-/app/databases/original_query.sqlite}"

# Check if SQLite binary exists
if [ ! -x "$SQLITE_BIN" ]; then
  echo "Error: SQLite binary not found or not executable at $SQLITE_BIN" >&2
  exit 2
fi

# Check if database file exists
if [ ! -f "$DB_PATH" ]; then
  echo "Error: Database file not found at $DB_PATH" >&2
  exit 2
fi

# Check if query file exists and is not empty
if [ ! -s "$QUERY_FILE" ]; then
  echo "Error: Query file is empty" >&2
  exit 2  # Different error code for empty file
fi

# Execute SQLite with the specified database and query file
OUTPUT=$("$SQLITE_BIN" "$DB_PATH" < "$QUERY_FILE" 2>&1)
RETURN_CODE=$?

# If return code is 1 AND output contains a specific error message
# (adjust the grep pattern to match your expected error)
if [ "$RETURN_CODE" -eq 1 ]; then
  # You can add additional checks here if needed
  # For example: if echo "$OUTPUT" | grep -q "expected error pattern"; then
  echo "SQLite returned 1, success for Perses" >&2
  exit 0
else
  echo "SQLite returned $RETURN_CODE but expected 1" >&2
  exit 1  # Fail the test
fi
