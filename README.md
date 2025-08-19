# ReduSQL

## Prerequisites

-   Docker and Docker Compose installed on your system
-   Your SQL queries ready in the proper directory structure

## Quick Start

1. **Ensure you have the required files:**

-   Your queries organized in `queries/queryN/` directories
-   Test scripts in a mounted directory (e.g., in `queries/queryN/`)

## Using ReduSQL with Your Queries

### Method 1: Direct Execution (Recommended)

Run the reducer directly with `docker compose run`:

```bash
docker compose run --rm redusql \
  --query /app/queries/query1/original_test.sql \
  --test /app/queries/query1/test_query_1.sh
```

The `--rm` flag automatically removes the container after execution.

### Method 2: Interactive Mode

```bash
docker compose run --rm --entrypoint /bin/bash redusql
```

Then run commands inside the container:

```bash
redusql --query /app/queries/query1/original_test.sql --test /app/queries/query1/test_query_1.sh
```

## Query Organization

Each query should be organized in its own directory under `queries/`:

1. **SQL Query File:** `original_test.sql` - The SQL query to reduce

**Example directory structure:**

```
queries/
├── query1/
│   ├── original_test.sql
│   └── test_query_1.sh
├── query2/
│   ├── original_test.sql
│   └── test_query_2.sh
└── ...
```

## Output

ReduSQL automatically saves results to a directory `output` inside the same directory as your `original_test.sql` file.

```
output/
├── query1/
│   └── original_test_reduced.sql
│   └── original_test_reduced_info.txt
├── query2/
│   └── original_test_reduced.sql
│   └── original_test_reduced_info.txt
└── ...
```

-   `original_test_reduced.sql` - The minimized SQL query
-   `original_test_reduced_info.txt` - Information about the reduction
