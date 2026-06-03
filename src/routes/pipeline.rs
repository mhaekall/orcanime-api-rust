use axum::{
    extract::{Path, State},
    response::Json,
    routing::post,
    Router,
};
use serde_json::{json, Value};
use sqlx::PgPool;
use std::sync::Arc;

use crate::providers::kuronime::Kuronime;
use crate::AppState;

pub fn create_router() -> Router<Arc<AppState>> {
    Router::new()
        .route("/sync/:anilist_id", post(sync_anime))
}

async fn sync_anime(
    State(state): State<Arc<AppState>>,
    Path(anilist_id): Path<i64>,
) -> Json<Value> {
    let anilist_id_i32 = anilist_id as i32;
    // 1. Get Anime Title
    let title_row = sqlx::query(
        r#"SELECT "cleanTitle", "nativeTitle" FROM anime_metadata WHERE "anilistId" = $1"#
    )
    .bind(anilist_id_i32)
    .fetch_optional(&state.db)
    .await;

    let title = match title_row {
        Ok(Some(row)) => {
            use sqlx::Row;
            let clean_title: Option<String> = row.try_get("cleanTitle").unwrap_or(None);
            let native_title: Option<String> = row.try_get("nativeTitle").unwrap_or(None);
            clean_title.unwrap_or(native_title.unwrap_or_default())
        },
        _ => return Json(json!({"error": "Anime not found"})),
    };

    let start_time = std::time::Instant::now();

    // 2. Search in Kuronime
    let kuronime = Kuronime::new(state.http_client.clone());
    use crate::providers::base::AnimeProvider;
    
    let search_res = kuronime.search(&title).await;
    let detail_url = match search_res {
        Ok(results) if !results.is_empty() => results[0].url.clone(),
        _ => return Json(json!({"error": "Anime not found on provider"})),
    };

    // 3. Fetch Episodes
    let episodes = match kuronime.fetch_episode_list(&detail_url).await {
        Ok(eps) => eps,
        Err(e) => return Json(json!({"error": format!("Failed parsing episodes: {}", e)})),
    };

    // 4. Batch Insert
    let mut synced = 0;
    for ep in episodes {
        let res = sqlx::query(
            r#"
            INSERT INTO episodes
                ("anilistId", "providerId", "episodeNumber", "episodeTitle", "episodeUrl", "updatedAt")
            VALUES
                ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT ("anilistId", "providerId", "episodeNumber")
            DO UPDATE SET
                "episodeUrl"   = EXCLUDED."episodeUrl",
                "episodeTitle" = EXCLUDED."episodeTitle",
                "updatedAt"    = NOW()
            "#
        )
        .bind(anilist_id_i32)
        .bind("kuronime")
        .bind(ep.number as f64)
        .bind(ep.title)
        .bind(ep.url)
        .execute(&state.db)
        .await;
        
        if res.is_ok() {
            synced += 1;
        }
    }

    // 5. Update Mapping
    let _ = sqlx::query(
        r#"
        INSERT INTO anime_mappings ("anilistId", "providerId", "providerSlug", "updatedAt")
        VALUES ($1, 'kuronime', $2, NOW())
        ON CONFLICT ("providerId", "providerSlug") DO NOTHING
        "#
    )
    .bind(anilist_id_i32)
    .bind(detail_url.replace("https://kuronime.sbs/anime/", "").replace("/", ""))
    .execute(&state.db)
    .await;

    let duration = start_time.elapsed().as_millis();

    Json(json!({
        "success": true,
        "anilist_id": anilist_id,
        "provider": "kuronime",
        "synced_episodes": synced,
        "time_ms": duration
    }))
}
