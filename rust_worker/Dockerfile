FROM rust:latest
WORKDIR /app

COPY rust_worker/Cargo.toml ./
COPY rust_worker/src/ ./src/

RUN cargo build --release

COPY models/ /app/models/

ENV PORT=8001
ENV MODELS_DIR=/app/models
EXPOSE 8001

CMD ["/app/target/release/thai_rust_ocr"]
