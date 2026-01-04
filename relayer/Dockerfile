# Tesseract Relayer Dockerfile
# Multi-stage build for minimal production image

# Build stage
FROM rust:1.75-bookworm AS builder

WORKDIR /app

# Install dependencies for building
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy manifests
COPY Cargo.toml Cargo.lock ./

# Create dummy main to cache dependencies
RUN mkdir src && \
    echo "fn main() {}" > src/main.rs && \
    cargo build --release && \
    rm -rf src

# Copy actual source
COPY src ./src

# Build for release
RUN touch src/main.rs && cargo build --release

# Runtime stage
FROM debian:bookworm-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy binary from builder
COPY --from=builder /app/target/release/tesseract-relayer /app/tesseract-relayer

# Copy configuration
COPY config /app/config

# Create non-root user
RUN useradd -r -s /bin/false relayer && \
    chown -R relayer:relayer /app

USER relayer

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose ports
EXPOSE 8080 9090

# Set environment
ENV RUST_LOG=info,tesseract_relayer=debug
ENV TESSERACT_CONFIG=/app/config/production.toml

# Run
ENTRYPOINT ["/app/tesseract-relayer"]
