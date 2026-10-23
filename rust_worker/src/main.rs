mod engine;
mod segmenter;
mod vocab;

use axum::{
    extract::{DefaultBodyLimit, Multipart, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use engine::{OcrEngine, OcrResult};
use serde_json::json;
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;
use tower_http::cors::{Any, CorsLayer};

struct AppState {
    engine: OcrEngine,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    tracing_subscriber::fmt::init();

    let models_dir = std::env::var("MODELS_DIR").unwrap_or_else(|_| "models".to_string());
    println!("==================================================================");
    println!("        ThaiOCR ONNX - High Performance Rust Engine Service       ");
    println!("==================================================================");
    println!("[INFO] Initializing Rust Engine from: {}", models_dir);

    let engine = OcrEngine::new(PathBuf::from(models_dir))?;
    println!("[OK] Rust OneOCR Engine initialized and ready!");

    let state = Arc::new(AppState { engine });

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/ocr/image", post(ocr_image_handler))
        .route("/ocr/document", post(ocr_document_handler))
        .layer(DefaultBodyLimit::max(60 * 1024 * 1024)) // Support up to 60MB for large scanned docs
        .layer(cors)
        .with_state(state);

    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8001);

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    println!("[INFO] Listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

async fn health_handler() -> impl IntoResponse {
    Json(json!({
        "status": "healthy",
        "service": "ThaiOCR Rust Worker",
        "engine": "rust"
    }))
}

async fn ocr_image_handler(
    State(state): State<Arc<AppState>>,
    body: axum::body::Bytes,
) -> Result<Json<OcrResult>, (StatusCode, String)> {
    let img = image::load_from_memory(&body).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("Failed to decode image bytes: {}", e),
        )
    })?;

    let result = state
        .engine
        .recognize(&img)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("OCR Error: {}", e)))?;

    Ok(Json(result))
}

async fn ocr_document_handler(
    State(state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    let mut file_bytes: Option<Vec<u8>> = None;
    let mut filename = "document.png".to_string();

    while let Ok(Some(field)) = multipart.next_field().await {
        let name = field.name().unwrap_or("").to_string();
        if name == "file" {
            if let Some(fname) = field.file_name() {
                filename = fname.to_string();
            }
            if let Ok(bytes) = field.bytes().await {
                file_bytes = Some(bytes.to_vec());
            }
        }
    }

    let Some(bytes) = file_bytes else {
        return Err((StatusCode::BAD_REQUEST, "Missing file in multipart".to_string()));
    };

    let img = image::load_from_memory(&bytes).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("Failed to decode document image (PDF should be rendered per page): {}", e),
        )
    })?;

    let res = state
        .engine
        .recognize(&img)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("OCR Error: {}", e)))?;

    let formatted_md = format!(
        "# {}\n\n*ประมวลผลด้วยระบบ ThaiOCR ONNX Rust Native*\n\n---\n\n{}",
        filename, res.text
    );

    Ok(Json(json!({
        "page_count": 1,
        "text": res.text,
        "markdown": formatted_md,
        "latency_ms": res.latency_ms,
        "lines": res.lines,
        "pages": [{"page": 1, "orientation": "แนวตั้ง (Portrait)", "has_table": false, "cols": 1}]
    })))
}
