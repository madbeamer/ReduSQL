#!/bin/bash

echo "Starting redusql execution for queries 1-20..."

for i in {1..20}; do
    echo "================================================"
    echo "Running query $i..."
    echo "================================================"
    
    docker compose run --rm redusql \
        --query /app/queries/query$i/original_test.sql \
        --test /app/queries/query$i/test_query_$i.sh \
        --parallel --algorithm=DDHDD --atom=line

    # Check if the command was successful
    if [ $? -eq 0 ]; then
        echo "Query $i completed successfully"
    else
        echo "Query $i failed with exit code $?"
    fi
    
    echo ""
done

echo "All queries completed!"
