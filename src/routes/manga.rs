use axum::{
    extract::{Path, State},
    response::Json,
    routing::get,
    Router,
};
use serde_json::{json, Value};
use std::sync::Arc;

use crate::providers::manga::base::MangaProvider;
use crate::providers::manga::komiku::Komiku;
use crate::providers::manga::thrive::Thrive;
use crate::AppState;

pub fn create_router() -> Router<Arc<AppState>> {
    Router::new()
        .route("/chapters/:title", get(get_chapters))
}

async fn get_chapters(
    State(state): State<Arc<AppState>>,
    Path(title): Path<String>,
    axum::extract::Query(params): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Json<Value> {
    let provider_name = params.get("provider").map(|s| s.as_str()).unwrap_or("komiku");

    let provider: Box<dyn MangaProvider + Send + Sync> = match provider_name {
        "thrive" => Box::new(Thrive::new(state.http_client.clone())),
        _ => Box::new(Komiku::new(state.http_client.clone())),
    };
    
    match provider.fetch_chapters(&title).await {
        Ok(chapters) => Json(json!({
            "success": true,
            "provider": provider.name(),
            "title": title,
            "chapters": chapters
        })),
        Err(e) => Json(json!({"error": e.to_string()})),
    }
}
