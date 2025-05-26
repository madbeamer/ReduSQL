# ReduSQL with Docker Compose

This guide explains how to use ReduSQL with Docker Compose for reducing SQL queries.

## Prerequisites

-   Docker and Docker Compose installed on your system
-   Your SQL queries ready in the proper directory structure

## Directory Structure

```
your-project/
├── docker-compose.yaml     # Docker Compose configuration
├── Dockerfile             # ReduSQL Docker image definition
├── reducer.py             # The reducer script
├── test.sh                # Shared test script (copied to container)
├── queries/               # Your input queries (mounted volume)
│   ├── query1/
│   │   ├── original_query.sql
│   │   └── oracle.txt
│   ├── query2/
│   │   ├── original_query.sql
│   │   └── oracle.txt
│   └── ...
└── output/                # Reduced queries will be saved here
    ├── query1/
    │   └── reduced_query.sql
    └── query2/
        └── reduced_query.sql
```

## Quick Start

1. **Ensure you have the required files:**

    - `test.sh` - The shared test script at project root
    - Your queries organized in `queries/queryN/` directories
    - Each query directory should contain `your_query.sql` and optionally `oracle.txt`

2. **Make the test script executable:**

    ```bash
    chmod +x test.sh
    ```

3. **Build the Docker image:**
    ```bash
    docker compose build
    ```

## Using ReduSQL with Your Queries

### Method 1: Direct Execution (Recommended)

Run the reducer directly with `docker compose run`:

```bash
docker compose run --rm redusql reducer \
  --query /queries/query1/original_query.sql \
  --test /app/test.sh
```

The reducer will automatically save the result to `/output/query1/reduced_query.sql`.

**With explicit output path:**

```bash
docker compose run --rm redusql reducer \
  --query /queries/query1/original_query.sql \
  --test /app/test.sh \
  --output /output/query1/reduced_query.sql
```

The `--rm` flag automatically removes the container after execution.

### Method 2: Interactive Mode

If you need to debug or explore:

```bash
docker compose run --rm redusql /bin/bash
```

Then run commands inside the container:

```bash
reducer --query /queries/query1/original_query.sql --test /app/test.sh
```

### Method 3: One-liner Alias

For convenience, add this to your `.bashrc` or `.zshrc`:

```bash
alias redusql='docker compose run --rm redusql reducer'

# Then use:
redusql --query /queries/query1/original_query.sql --test /app/test.sh
```

## Query Organization

Each query should be organized in its own directory under `queries/`:

1. **SQL Query File:** `original_query.sql` - The SQL query to reduce
2. **Oracle File:** `oracle.txt` - (Optional) Specifies the bug type:
    - `CRASH(3.26.0)` - Test for crashes in SQLite 3.26.0
    - `CRASH(3.39.4)` - Test for crashes in SQLite 3.39.4
    - `DIFF` - Test for differential behavior between versions
    - If not provided, defaults to `CRASH(3.26.0)`

**Example oracle.txt:**

```
CRASH(3.26.0)
```

## The Shared Test Script

The `test.sh` script at the project root is automatically copied into the Docker container and handles all testing logic. It:

-   Automatically detects the oracle type from `oracle.txt` in the same directory as the SQL file
-   Supports crash detection for different SQLite versions
-   Supports differential behavior testing between SQLite versions
-   Provides detailed logging of test results

You don't need individual test scripts for each query - the shared script handles everything.

## Running Multiple Reductions

Create a batch script to process multiple queries:

```bash
#!/bin/bash
# save as reduce_all.sh

for query_dir in queries/*/; do
    if [ -f "$query_dir/original_query.sql" ]; then
        query_name=$(basename "$query_dir")
        echo "Reducing $query_name..."

        docker compose run --rm redusql reducer \
            --query "/queries/$query_name/original_query.sql" \
            --test "/app/test.sh"
    fi
done
```

## Viewing Results

All reduced queries are automatically saved in the `output/` directory with the same structure as your input:

```bash
ls -la output/
ls -la output/query1/
cat output/query1/reduced_query.sql
```

## Useful Commands

```bash
# Run a reduction (auto-output path)
docker compose run --rm redusql reducer \
  --query /queries/query1/your_query.sql \
  --test /opt/redusql/test.sh

# Run with explicit output path
docker compose run --rm redusql reducer \
  --query /queries/query1/your_query.sql \
  --test /opt/redusql/test.sh \
  --output /output/query1/reduced_query.sql

# Run with verbose output
docker compose run --rm redusql reducer \
  --query /queries/query1/your_query.sql \
  --test /opt/redusql/test.sh \
  --verbose

# Interactive shell
docker compose run --rm redusql /bin/bash

# Check SQLite versions available
docker compose run --rm redusql /usr/bin/sqlite3-3.26.0 --version
docker compose run --rm redusql /usr/bin/sqlite3-3.39.4 --version

# Test the shared test script directly
docker compose run --rm redusql /app/test.sh /queries/query1/original_query.sql

# Build the image
docker compose build

# Clean up containers
docker compose down
```

## Example Usage

Given this structure:

```
queries/
├── crash_example/
│   ├── original_query.sql
│   └── oracle.txt (contains "CRASH(3.26.0)")
└── diff_example/
    ├── original_query.sql
    └── oracle.txt (contains "DIFF")
```

Run:

```bash
# Test crash example
docker compose run --rm redusql reducer \
  --query /queries/crash_example/original_query.sql \
  --test /app/test.sh

# Test differential example
docker compose run --rm redusql reducer \
  --query /queries/diff_example/original_query.sql \
  --test /app/test.sh
```

Results will be saved to:

-   `output/crash_example/reduced_query.sql`
-   `output/diff_example/reduced_query.sql`

## Troubleshooting

1. **Permission issues with output files:**

    ```bash
    # Fix permissions on output directory
    sudo chown -R $USER:$USER output/
    ```

2. **Container not starting:**

    ```bash
    # Check logs
    docker compose logs

    # Rebuild the image
    docker compose build --no-cache
    ```

3. **Test script not executable:**

    ```bash
    # Make the shared test script executable
    chmod +x test.sh
    ```

4. **Oracle file not found:**
    ```bash
    # The shared test script will default to CRASH(3.26.0) if oracle.txt is missing
    # To explicitly set oracle type:
    echo "CRASH(3.26.0)" > queries/your_query_dir/oracle.txt
    ```

## Clean Up

To remove the container and image:

```bash
docker compose down
docker rmi redusql:latest
```
