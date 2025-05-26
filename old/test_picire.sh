#! /bin/bash
if [ -z "$1" ]; then
  echo "Usage: $0 <query_file>"
  exit 1
fi

output=$(timeout --foreground 10 /home/test/sqlite/sqlite3-3.26.0 /app/src/test_athena.db < "$1" 2>&1)
echo "$output"
echo "$output" | grep -q "database disk image is malformed"
exit_code=$?
exit $exit_code
