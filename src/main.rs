use axum::{
    routing::get,
    Router,
    response::Json,
};
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::net::TcpListener;
use tower_http::cors::CorsLayer;
use tracing_subscriber;

mod db;
mod routes;
mod providers;
mod utils;
mod services;

use db::connection::init_db;
use services::anilist::AnilistService;
use sqlx::PgPool;
use reqwest::Client;

pub struct AppState {
    pub db: PgPool,
    pub http_client: Client,
    pub anilist_service: AnilistService,
}

#[tokio::main]
async fn main() {
    // Load .env if it exists locally (will fail silently in production/docker which is fine)
    let _ = dotenvy::dotenv();

    // Initialize standard output tracing
    tracing_subscriber::fmt::init();

    // Initialize Postgres connection pool
    let db_pool = match init_db().await {
        Ok(pool) => pool,
        Err(e) => {
            tracing::warn!("⚠️ Could not connect to database, continuing without it: {}", e);
            // In a real app you might want to panic here, but for this PoC we fallback gracefully if ENV is missing
            sqlx::postgres::PgPoolOptions::new()
                .connect_lazy("postgres://postgres:postgres@localhost:5432/postgres")
                .unwrap()
        }
    };

    // Initialize an optimized global HTTP client for scraping
    let http_client = reqwest::Client::builder()
        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        .danger_accept_invalid_certs(true)
        .http1_only()
        .build()
        .unwrap();

    let anilist_service = AnilistService::new(http_client.clone(), db_pool.clone());

    let state = Arc::new(AppState {
        db: db_pool,
        http_client,
        anilist_service,
    });

    // Define routes
    let app = Router::new()
        .route("/", get(root_handler))
        .route("/health", get(health_check))
        .nest("/api/v1", routes::scraper::create_router())
        .nest("/api/v1/anilist", routes::anilist::create_router())
        .nest("/api/v1/manga", routes::manga::create_router())
        .nest("/api/v1/schedule", routes::schedule::create_router())
        .nest("/api/v1/internal", routes::pipeline::create_router())
        .layer(CorsLayer::permissive()) // Adjust CORS to your needs
        .with_state(state);

    // Hugging Face Spaces require listening on port 7860
    let port = std::env::var("PORT").unwrap_or_else(|_| "7860".to_string());
    let addr = format!("0.0.0.0:{}", port);
    
    let listener = TcpListener::bind(&addr).await.unwrap();
    tracing::info!("🚀 Server running natively on {}", addr);
    
    axum::serve(listener, app).await.unwrap();
}

async fn root_handler() -> Json<Value> {
    Json(json!({
        "status": "online",
        "message": "Orcanime Rust API (Zero-Cost Scraper Engine) is running!",
        "engine": "Axum / Tokio / SQLx"
    }))
}

async fn health_check() -> &'static str {
    "OK"
}
