use axum::{
    extract::{Path, State},
    response::Json,
    routing::get,
    Router,
};
use serde_json::{json, Value};
use std::sync::Arc;

use crate::AppState;

pub fn create_router() -> Router<Arc<AppState>> {
    Router::new()
        .route("/id/:id", get(get_by_id))
        .route("/search", get(search_by_title))
        .route("/debug/enrich/:id", get(debug_enrich))
        .route("/debug/db", get(debug_db))
}

async fn debug_db(
    State(state): State<Arc<AppState>>,
) -> Json<Value> {
    let row = sqlx::query!("SELECT \"anilistId\", \"cleanTitle\" FROM anime_metadata LIMIT 5")
        .fetch_all(&state.db)
        .await;

    match row {
        Ok(rows) => {
            let mut res = Vec::new();
            for r in rows {
                res.push(json!({"id": r.anilistId, "title": r.cleanTitle}));
            }
            Json(json!({"success": true, "data": res}))
        },
        Err(e) => Json(json!({"success": false, "error": e.to_string()})),
    }
}

async fn debug_enrich(
    State(state): State<Arc<AppState>>,
    Path(id): Path<i64>,
) -> Json<Value> {
    match crate::db::queries::get_anime_enrichment(&state.db, id).await {
        Ok(data) => Json(json!({"success": true, "data": data})),
        Err(e) => Json(json!({"success": false, "error": e.to_string()})),
    }
}

async fn get_by_id(
    State(state): State<Arc<AppState>>,
    Path(id): Path<u64>,
) -> Json<Value> {
    match state.anilist_service.fetch_by_id(id).await {
        Ok(Some(data)) => Json(json!({"success": true, "data": data})),
        Ok(None) => Json(json!({"success": false, "error": "Not found"})),
        Err(e) => Json(json!({"success": false, "error": e.to_string()})),
    }
}

async fn search_by_title(
    State(state): State<Arc<AppState>>,
    axum::extract::Query(params): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Json<Value> {
    let title = match params.get("q") {
        Some(q) => q,
        None => return Json(json!({"success": false, "error": "Missing 'q' parameter"})),
    };

    match state.anilist_service.fetch_by_title(title).await {
        Ok(Some(data)) => Json(json!({"success": true, "data": [data]})),
        Ok(None) => Json(json!({"success": true, "data": []})),
        Err(e) => Json(json!({"success": false, "error": e.to_string()})),
    }
}