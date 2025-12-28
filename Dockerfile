# Stage 1: Build dependencies
FROM python:3.11-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libxml2-dev \
    libxslt-dev

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime image
FROM python:3.11-alpine

# Metadata
LABEL maintainer="Fran"
LABEL description="Indexarr - Jackett-compatible API for torrent indexers"

# Install only runtime dependencies
RUN apk add --no-cache \
    libxml2 \
    libxslt \
    && rm -rf /var/cache/apk/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set PATH to use venv
ENV PATH="/opt/venv/bin:$PATH"

# Create working directory
WORKDIR /app

# Copy application code
COPY . .

# Create non-root user for security
RUN addgroup -g 1000 indexerr && \
    adduser -D -u 1000 -G indexerr indexerr && \
    chown -R indexerr:indexerr /app

# Switch to non-root user
USER indexerr

# Expose port
EXPOSE 15505

# Environment variables
ENV PYTHONUNBUFFERED=1

# Start command
CMD ["python3", "app.py"]
