# ReduSQL with Docker Compose

This guide explains how to use ReduSQL with Docker Compose for reducing SQL queries.

## Prerequisites

-   Docker and Docker Compose installed on your system
-   Your SQL queries ready in the proper directory structure

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
  --query /app/queries/query1/original_query.sql \
  --test /app/test.sh
```

The reducer will automatically save the result to `/app/output/query1/reduced_query.sql`.

**With explicit output path:**

```bash
docker compose run --rm redusql reducer \
  --query /app/queries/query1/original_query.sql \
  --test /app/test.sh \
  --output /app/output/query1/reduced_query.sql
```

The `--rm` flag automatically removes the container after execution.

### Method 2: Interactive Mode

If you need to debug or explore:

```bash
docker compose run --rm redusql /bin/bash
```

Then run commands inside the container:

```bash
reducer --query /app/queries/query1/original_query.sql --test /app/test.sh
```

### Method 3: One-liner Alias

For convenience, add this to your `.bashrc` or `.zshrc`:

```bash
alias redusql='docker compose run --rm redusql reducer'

# Then use:
redusql --query /app/queries/query1/original_query.sql --test /app/test.sh
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
