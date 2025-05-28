# Use the provided SQLite test image as base
FROM theosotr/sqlite3-test

# Switch to root user to install packages
USER root

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install Python and required dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/src /app/output /app/queries

# Copy the entire source code structure
COPY src/ /app/src/

# Copy test scripts
COPY test_crash_3_26_0.sh /app/test_crash_3_26_0.sh
COPY test_crash_3_39_4.sh /app/test_crash_3_39_4.sh
COPY test_diff.sh /app/test_diff.sh

# Make the scripts executable
RUN chmod +x /app/src/main.py /app/test_crash_3_26_0.sh /app/test_crash_3_39_4.sh /app/test_diff.sh

# Create symbolic links for easier access
RUN ln -sf /app/src/main.py /usr/bin/redusql
RUN ln -sf /app/src/main.py /usr/bin/reducer

# Set working directory
WORKDIR /app

ENTRYPOINT ["python3", "/app/src/main.py"]
