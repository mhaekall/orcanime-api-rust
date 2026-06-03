use axum::{
    extract::State,
    response::Json,
    routing::get,
    Router,
};
use serde_json::{json, Value};
use sqlx::{PgPool, Row};
use std::sync::Arc;
use chrono::{DateTime, TimeZone, Utc, FixedOffset};
use std::collections::HashMap;

use crate::AppState;

pub fn create_router() -> Router<Arc<AppState>> {
    Router::new()
        .route("/", get(get_schedule))
}

async fn get_schedule(
    State(state): State<Arc<AppState>>,
) -> Json<Value> {
    let query = r#"
        SELECT m."anilistId", m."cleanTitle", m."nativeTitle", m."coverImage", m."score", m."nextAiringEpisode", m.popularity,
               COALESCE(c.episode_count_actual, m."totalEpisodes") as "totalEpisodes",
               (SELECT MAX(raw_value::numeric) FROM metadata_sources ms WHERE ms.canonical_id = c.id AND ms.field_name = 'score_local') as local_score,
               (SELECT MAX("episodeNumber") FROM episodes e WHERE e."anilistId" = m."anilistId") as "latestEpisode",
               COALESCE((SELECT MAX(raw_value::numeric) FROM metadata_sources ms WHERE ms.canonical_id = c.id AND ms.field_name = 'views_local'), 0) + COALESCE((SELECT SUM(views) FROM daily_anime_stats d WHERE d."anilistId" = m."anilistId"), 0) as local_views
        FROM anime_metadata m
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        WHERE m.status = 'RELEASING'
        ORDER BY local_views DESC, m.popularity DESC NULLS LAST
    "#;

    let rows = match sqlx::query(query).fetch_all(&state.db).await {
        Ok(r) => r,
        Err(e) => return Json(json!({"success": false, "error": e.to_string()})),
    };

    let mut schedule: HashMap<String, Vec<Value>> = HashMap::new();
    let days = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu", "TBA"];
    for day in days.iter() {
        schedule.insert(day.to_string(), Vec::new());
    }

    let wib = FixedOffset::east_opt(7 * 3600).unwrap();

    for row in rows {
        let mut day_name = "TBA".to_string();
        let mut time_str = "".to_string();

        if let Ok(next_air_json) = row.try_get::<Value, _>("nextAiringEpisode") {
            if let Some(airing_at) = next_air_json.get("airingAt").and_then(|v| v.as_i64()) {
                if let Some(dt_utc) = Utc.timestamp_opt(airing_at, 0).single() {
                    let dt_wib = dt_utc.with_timezone(&wib);
                    // chrono weekday: 0 = Mon, 6 = Sun.
                    let weekday_idx = dt_wib.format("%w").to_string().parse::<usize>().unwrap_or(0);
                    // Note: In python, weekday() is 0=Mon. In chrono, %w is 0=Sun. 
                    // Let's use %u which is 1=Mon, 7=Sun.
                    let weekday_idx = dt_wib.format("%u").to_string().parse::<usize>().unwrap_or(7) - 1;
                    if weekday_idx < 7 {
                        day_name = days[weekday_idx].to_string();
                    }
                    time_str = dt_wib.format("%H:%M WIB").to_string();
                }
            }
        } else if let Ok(next_air_str) = row.try_get::<String, _>("nextAiringEpisode") {
             if let Ok(next_air_json) = serde_json::from_str::<Value>(&next_air_str) {
                 if let Some(airing_at) = next_air_json.get("airingAt").and_then(|v| v.as_i64()) {
                    if let Some(dt_utc) = Utc.timestamp_opt(airing_at, 0).single() {
                        let dt_wib = dt_utc.with_timezone(&wib);
                        let weekday_idx = dt_wib.format("%u").to_string().parse::<usize>().unwrap_or(7) - 1;
                        if weekday_idx < 7 {
                            day_name = days[weekday_idx].to_string();
                        }
                        time_str = dt_wib.format("%H:%M WIB").to_string();
                    }
                 }
             }
        }

        let mut final_score: i64 = row.try_get("score").unwrap_or(0);
        if let Ok(local_score) = row.try_get::<f64, _>("local_score") {
             if local_score <= 10.0 {
                 final_score = (local_score * 10.0) as i64;
             } else {
                 final_score = local_score as i64;
             }
        }

        let mut pop_v: i64 = row.try_get("popularity").unwrap_or(0);
        let anilist_id: i32 = row.try_get("anilistId").unwrap_or(0);
        if pop_v == 0 {
            pop_v = (anilist_id as i64 % 900) + 100;
        }

        let eps_v: i64 = row.try_get("totalEpisodes").unwrap_or(12);
        let base_v = (pop_v as f64 * eps_v as f64 * 0.7) as i64;
        let mut local_views: f64 = row.try_get("local_views").unwrap_or(0.0);
        let final_views = local_views as i64 + base_v;

        let clean_title: Option<String> = row.try_get("cleanTitle").ok();
        let native_title: Option<String> = row.try_get("nativeTitle").ok();
        let title = clean_title.unwrap_or(native_title.unwrap_or_default());

        let img: Option<String> = row.try_get("coverImage").ok();
        let latest_episode: Option<f64> = row.try_get("latestEpisode").ok();

        let anime_obj = json!({
            "id": anilist_id.to_string(),
            "title": title,
            "img": img,
            "score": final_score,
            "views": final_views,
            "latestEpisode": latest_episode,
            "airingTime": time_str,
        });

        if let Some(list) = schedule.get_mut(&day_name) {
            list.push(anime_obj);
        }
    }

    // Filter empty
    let mut filtered_schedule: HashMap<String, Vec<Value>> = HashMap::new();
    for (k, v) in schedule {
        if !v.is_empty() {
            filtered_schedule.insert(k, v);
        }
    }

    Json(json!({
        "success": true,
        "data": filtered_schedule
    }))
}
