# ReduSQL with Docker Compose

This guide explains how to use ReduSQL with Docker Compose for reducing SQL queries using delta debugging.

## Prerequisites

-   Docker and Docker Compose installed on your system
-   Your SQL queries ready in the proper directory structure

## Quick Start

1. **Ensure you have the required files:**

    - Test script (e.g., `test.sh`) at project root
    - Your queries organized in `queries/queryN/` directories

2. **Build the Docker image:**
    ```bash
    docker compose build
    ```

## Using ReduSQL with Your Queries

### Method 1: Direct Execution (Recommended)

Run the reducer directly with `docker compose run`:

```bash
docker compose run --rm redusql \
  --query /app/queries/query1/original_test.sql \
  --test /app/test.sh
```

**With verbose output:**

```bash
docker compose run --rm redusql \
  --query /app/queries/query1/original_test.sql \
  --test /app/test.sh \
  --verbose
```

**With parallel processing:**

```bash
docker compose run --rm redusql \
  --query /app/queries/query1/original_test.sql \
  --test /app/test.sh \
  --parallel
```

The `--rm` flag automatically removes the container after execution.

### Method 2: Interactive Mode

If you need to debug or explore:

```bash
docker compose run --rm --entrypoint /bin/bash redusql
```

Then run commands inside the container:

```bash
redusql --query /app/queries/query1/original_test.sql --test /app/test_crash_3_26_0.sh
```

## Query Organization

Each query should be organized in its own directory under `queries/`:

1. **SQL Query File:** `original_test.sql` - The SQL query to reduce

**Example directory structure:**

```
queries/
├── query1/
│   └── original_test.sql
├── query2/
│   └── original_test.sql
└── ...
```

## Output

ReduSQL automatically saves results to the `/app/output/` directory (mounted from your local `./output/`):

```
output/
├── query1/
│   └── reduced_query.sql
│   └── reduced_query_tokens.txt
├── query2/
│   └── reduced_query.sql
│   └── reduced_query_tokens.txt
└── ...
```

-   `reduced_query.sql` - The minimized SQL query
-   `reduced_query_tokens.txt` - Token-level information about the reduction
