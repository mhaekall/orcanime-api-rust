# Stage 1: Builder
FROM rust:alpine AS builder

WORKDIR /usr/src/app

# Install musl-dev and build tools for static compilation
RUN apk add --no-cache musl-dev build-base pkgconfig

# Create a dummy project to cache dependencies
RUN cargo new --bin orcanime-api-rust
WORKDIR /usr/src/app/orcanime-api-rust
COPY Cargo.toml Cargo.lock* ./
RUN cargo build --release --target x86_64-unknown-linux-musl || true

# Copy real source code
COPY src ./src

# Build for release using musl target (static linking)
RUN touch src/main.rs && cargo build --release --target x86_64-unknown-linux-musl > build.log 2>&1 || true

# Check if binary was built, if so copy it, else copy a dummy
RUN mkdir -p /output && \
    if [ -f target/x86_64-unknown-linux-musl/release/orcanime-api-rust ]; then \
        cp target/x86_64-unknown-linux-musl/release/orcanime-api-rust /output/server; \
    else \
        touch /output/server; \
    fi

# Stage 2: Runtime (Debug mode)
FROM alpine:3.18

RUN apk add --no-cache python3 ca-certificates

WORKDIR /app

# Copy the logs and potential binary
COPY --from=builder /usr/src/app/orcanime-api-rust/build.log /app/build.log
COPY --from=builder /output/server /app/server

ENV PORT=7860
EXPOSE 7860

# Run the binary
CMD ["/app/server"]