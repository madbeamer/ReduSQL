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

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the entire source code structure
COPY src/ /app/src/

# Create symbolic links for easier access
RUN ln -sf /app/src/main.py /usr/bin/redusql
RUN ln -sf /app/src/main.py /usr/bin/reducer

# Set working directory
WORKDIR /app

ENTRYPOINT ["python3", "/app/src/main.py"]
