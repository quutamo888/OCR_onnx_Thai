# Multi-stage Dockerfile for ThaiOCR Web Application

# Stage 1: Build React Frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend Runtime
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY oneocr/ ./oneocr/
COPY server/ ./server/
COPY pdf_to_md.py .
COPY example.py .

# Copy built frontend from Stage 1
COPY --from=frontend-builder /build/dist ./frontend/dist

# Security Hardening: Create unprivileged non-root user (UID 10001)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser && \
    mkdir -p /app/data /app/output && \
    chown -R appuser:appgroup /app

USER appuser:appgroup

# Expose Web Portal Port
EXPOSE 8000

# Start server with hardened security flags (no server banner)
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--no-date-header"]
