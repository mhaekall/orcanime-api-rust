use axum::{
    extract::{Path, State},
    response::Json,
    routing::get,
    Router,
};
use reqwest::Client;
use serde_json::{json, Value};
use sqlx::PgPool;
use std::sync::Arc;

use crate::providers::base::AnimeProvider;
use crate::providers::kuronime::Kuronime;
use crate::providers::samehadaku::Samehadaku;
use crate::providers::oploverz::Oploverz;
use crate::providers::doronime::Doronime;
use crate::AppState;

pub fn create_router() -> Router<Arc<AppState>> {
    Router::new()
        .route("/anime/search/:query", get(search_anime))
        .route("/anime/streams", get(get_streams)) // Requires query param: ?url=... &provider=...
}

async fn search_anime(
    State(state): State<Arc<AppState>>,
    Path(query): Path<String>,
    axum::extract::Query(params): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Json<Value> {
    let provider_name = params.get("provider").map(|s| s.as_str()).unwrap_or("kuronime");

    let provider: Box<dyn AnimeProvider + Send + Sync> = match provider_name {
        "samehadaku" => Box::new(Samehadaku::new(state.http_client.clone())),
        "oploverz" => Box::new(Oploverz::new(state.http_client.clone())),
        "doronime" => Box::new(Doronime::new(state.http_client.clone())),
        _ => Box::new(Kuronime::new(state.http_client.clone())),
    };
    
    match provider.search(&query).await {
        Ok(results) => Json(json!({
            "success": true,
            "provider": provider_name,
            "query": query,
            "results": results
        })),
        Err(e) => Json(json!({"error": e.to_string()})),
    }
}

async fn get_streams(
    State(state): State<Arc<AppState>>,
    axum::extract::Query(params): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Json<Value> {
    let url = match params.get("url") {
        Some(u) => u,
        None => return Json(json!({"error": "Missing 'url' query parameter"})),
    };

    let provider_name = params.get("provider").map(|s| s.as_str()).unwrap_or("kuronime");

    let provider: Box<dyn AnimeProvider + Send + Sync> = match provider_name {
        "samehadaku" => Box::new(Samehadaku::new(state.http_client.clone())),
        "oploverz" => Box::new(Oploverz::new(state.http_client.clone())),
        "doronime" => Box::new(Doronime::new(state.http_client.clone())),
        _ => Box::new(Kuronime::new(state.http_client.clone())),
    };
    
    match provider.get_episode_sources(url).await {
        Ok(sources) => Json(json!({
            "success": true,
            "provider": provider_name,
            "sources": sources
        })),
        Err(e) => Json(json!({"error": e.to_string()})),
    }
}
