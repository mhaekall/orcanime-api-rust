use sqlx::{PgPool, Row};
use serde_json::{json, Value};

pub async fn get_anime_enrichment(pool: &PgPool, anilist_id: i64) -> Result<Value, sqlx::Error> {
    // 1. Get Provider Mappings and Metadata Overrides
    let meta_rows = sqlx::query(
        r#"
        SELECT am."providerId", am."providerSlug", 
               m.synopsis, 
               m."cleanTitle",
               m."nativeTitle",
               c.title_preferred as "canonicalTitle", 
               c.air_schedule_wib as "canonicalSchedule",
               m.status as "localStatus"
        FROM anime_metadata m
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        LEFT JOIN anime_mappings am ON m."anilistId" = am."anilistId"
        WHERE m."anilistId" = $1
        "#
    )
    .bind(anilist_id as i32)
    .fetch_all(pool)
    .await?;

    let mut providers = Vec::new();
    let mut synopsis: Option<String> = None;
    let mut clean_title: Option<String> = None;
    let mut native_title: Option<String> = None;
    let mut canonical_title: Option<String> = None;
    let mut canonical_schedule: Option<String> = None;
    let mut local_status: Option<String> = None;

    let mut debug_errors = Vec::new();

    for row in meta_rows {
        if let Ok(provider_id) = row.try_get::<Option<String>, _>("providerId") {
            if let Some(pid) = provider_id {
                if !providers.contains(&pid) {
                    providers.push(pid);
                }
            }
        }
        
        match row.try_get::<Option<String>, _>("cleanTitle") {
            Ok(v) => if clean_title.is_none() { clean_title = v; },
            Err(e) => debug_errors.push(format!("cleanTitle: {}", e)),
        }

        if synopsis.is_none() {
            synopsis = row.try_get::<Option<String>, _>("synopsis").unwrap_or_else(|e| { debug_errors.push(format!("synopsis: {}", e)); None });
        }
        if native_title.is_none() {
            native_title = row.try_get::<Option<String>, _>("nativeTitle").unwrap_or_else(|e| { debug_errors.push(format!("nativeTitle: {}", e)); None });
        }
        if canonical_title.is_none() {
            canonical_title = row.try_get::<Option<String>, _>("canonicalTitle").unwrap_or_else(|e| { debug_errors.push(format!("canonicalTitle: {}", e)); None });
        }
        if canonical_schedule.is_none() {
            canonical_schedule = row.try_get::<Option<String>, _>("canonicalSchedule").unwrap_or_else(|e| { debug_errors.push(format!("canonicalSchedule: {}", e)); None });
        }
        if local_status.is_none() {
            local_status = row.try_get::<Option<String>, _>("localStatus").unwrap_or_else(|e| { debug_errors.push(format!("localStatus: {}", e)); None });
        }
    }

    // 2. Fetch Episodes
    let ep_rows = sqlx::query(
        r#"
        SELECT DISTINCT ON ("episodeNumber")
               "episodeNumber", "episodeTitle", "episodeUrl", "providerId", "thumbnailUrl"
        FROM   episodes
        WHERE  "anilistId" = $1
        ORDER  BY
               "episodeNumber" DESC,
               CASE "providerId"
                WHEN 'kuronime'   THEN 1
                WHEN 'samehadaku' THEN 2
                WHEN 'oploverz'   THEN 3
                WHEN 'doronime'   THEN 4
                WHEN 'otakudesu'  THEN 5
                ELSE 6
               END ASC
        "#
    )
    .bind(anilist_id as i32)
    .fetch_all(pool)
    .await?;

    let mut episodes_list = Vec::new();
    for row in ep_rows {
        let ep_num: f64 = row.try_get("episodeNumber").unwrap_or(0.0);
        let ep_title: Option<String> = row.try_get("episodeTitle").ok();
        let ep_url: Option<String> = row.try_get("episodeUrl").ok();
        let provider_id: Option<String> = row.try_get("providerId").ok();
        let thumbnail_url: Option<String> = row.try_get("thumbnailUrl").ok();

        episodes_list.push(json!({
            "episodeNumber": ep_num,
            "episodeTitle": ep_title,
            "episodeUrl": ep_url,
            "providerId": provider_id,
            "thumbnailUrl": thumbnail_url,
        }));
    }

    Ok(json!({
        "hasMapping": !providers.is_empty(),
        "providers": providers,
        "hasEpisodes": !episodes_list.is_empty(),
        "episodes": episodes_list,
        "synopsis": synopsis,
        "cleanTitle": clean_title,
        "nativeTitle": native_title,
        "canonicalTitle": canonical_title,
        "canonicalSchedule": canonical_schedule,
        "localStatus": local_status,
        "debug_errors": debug_errors
    }))
}

pub async fn get_manga_enrichment(pool: &PgPool, anilist_id: i64) -> Result<Value, sqlx::Error> {
    let meta_row = sqlx::query(
        r#"
        SELECT meta.*, 
               (SELECT COUNT(*) FROM manga_chapters ch WHERE ch."anilistId" = meta."anilistId") as chapter_count_db
        FROM manga_metadata meta
        WHERE meta."anilistId" = $1
        "#
    )
    .bind(anilist_id)
    .fetch_optional(pool)
    .await?;

    if let Some(row) = meta_row {
        let chapter_count_db: i64 = row.try_get("chapter_count_db").unwrap_or(0);
        Ok(json!({
            "hasMetadata": true,
            "chapter_count_db": chapter_count_db
        }))
    } else {
        Ok(json!({
            "hasMetadata": false,
            "chapter_count_db": 0
        }))
    }
}
