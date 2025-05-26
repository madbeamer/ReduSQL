#!/bin/bash
# Quick start script for ReduSQL with Docker Compose

echo "ReduSQL Quick Start"
echo "=================="

# Create directory structure
echo "Creating directory structure..."
mkdir -p queries output benchmarks
mkdir -p queries/example

# Create example SQL query
cat > queries/example/original_test.sql << 'EOF'
CREATE TABLE t1(a INTEGER PRIMARY KEY, b TEXT);
INSERT INTO t1 VALUES(1, 'test');
INSERT INTO t1 VALUES(2, 'data'); 
SELECT * FROM t1 WHERE a = 1 AND b LIKE '%test%';
DROP TABLE t1;
EOF

# Create example oracle file
echo "CRASH(3.26.0)" > queries/example/oracle.txt

# Create example test script
cat > queries/example/test.sh << 'EOF'
#!/bin/bash
# Simple example that always returns 0 (bug present)
# In a real scenario, this would test for an actual bug
exit 0
EOF

chmod +x queries/example/test.sh

# Build the Docker image
echo "Building Docker image..."
docker compose build

# Wait a moment
sleep 1

# Run the example reduction
echo ""
echo "Running example reduction..."
docker compose run --rm redusql reducer \
    --query /queries/example/original_test.sql \
    --test /queries/example/test.sh \
    --output /output/example_reduced.sql

echo ""
echo "Setup complete!"
echo ""
echo "You can now:"
echo "1. Add your queries to the 'queries/' directory"
echo "2. View reduced queries in the 'output/' directory" 
echo "3. Run reductions: docker compose run --rm redusql reducer --query /queries/your.sql --test /queries/test.sh"
echo "4. Interactive mode: docker compose run --rm redusql /bin/bash"
