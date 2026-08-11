# Multi-stage build for Rust Proxy Service
FROM rust:1.97-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y pkg-config libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy manifests
COPY Cargo.toml ./
COPY Cargo.lock ./

# Copy source code
COPY src ./src

# Build release binary
RUN cargo build --release

# Runtime stage
FROM debian:bookworm-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y ca-certificates libssl3 curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 proxyuser

# Copy binary from builder
COPY --from=builder /build/target/release/proxy-server /app/proxy-server

# Set ownership
RUN chown -R proxyuser:proxyuser /app

USER proxyuser

# Expose ports (proxy + admin)
EXPOSE 8080 8081

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/health || exit 1

# Run the service
CMD ["/app/proxy-server"]
