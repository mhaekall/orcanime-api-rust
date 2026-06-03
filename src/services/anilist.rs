use crate::db::queries::get_anime_enrichment;
use moka::future::Cache;
use reqwest::Client;
use serde_json::{json, Value};
use sqlx::PgPool;
use std::time::Duration;
use strsim::jaro_winkler;
use regex::Regex;

const GET_ANIME_BY_ID: &str = r#"
  query ($id: Int) {
    Media(id: $id, type: ANIME, isAdult: false) {
      id
      idMal
      title { romaji english native }
      synonyms
      coverImage { extraLarge large color }
      bannerImage
      averageScore
      popularity
      trending
      episodes
      status
      season
      seasonYear
      description(asHtml: false)
      genres
      tags { name rank }
      studios { nodes { name isAnimationStudio } }
      relations {
        edges {
          relationType
          node { id title { romaji english } coverImage { extraLarge } type }
        }
      }
    }
  }
"#;

const GET_ANIME_DETAILS: &str = r#"
  query ($search: String) {
    Page(page: 1, perPage: 5) {
      media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
        id
        idMal
        title { romaji english native }
        synonyms
        coverImage { extraLarge large color }
        bannerImage
        averageScore
        popularity
        trending
        episodes
        status
        season
        seasonYear
        description(asHtml: false)
        genres
        tags { name rank }
        studios { nodes { name isAnimationStudio } }
        relations {
          edges {
            relationType
            node { id title { romaji english } coverImage { extraLarge } type }
          }
        }
      }
    }
  }
"#;

#[derive(Clone)]
pub struct AnilistService {
    client: Client,
    cache: Cache<String, Value>,
    db: PgPool,
}

impl AnilistService {
    pub fn new(client: Client, db: PgPool) -> Self {
        Self {
            client,
            cache: Cache::builder()
                .time_to_live(Duration::from_secs(86400))
                .max_capacity(1000)
                .build(),
            db,
        }
    }

    pub async fn fetch_by_id(&self, id: u64) -> Result<Option<Value>, Box<dyn std::error::Error + Send + Sync>> {
        let cache_key = format!("anilist_id_{}", id);
        
        if let Some(cached) = self.cache.get(&cache_key).await {
            return Ok(Some(cached));
        }

        let res = self.client.post("https://graphql.anilist.co")
            .json(&json!({
                "query": GET_ANIME_BY_ID,
                "variables": { "id": id }
            }))
            .send().await?;

        let data: Value = res.json().await?;
        let media = data.get("data").and_then(|d| d.get("Media"));

        if let Some(m) = media {
            let enriched = self.enrich_metadata(m.clone()).await;
            self.cache.insert(cache_key, enriched.clone()).await;
            Ok(Some(enriched))
        } else {
            Ok(None)
        }
    }

    pub async fn fetch_by_title(&self, title: &str) -> Result<Option<Value>, Box<dyn std::error::Error + Send + Sync>> {
        let title_clean = Regex::new(r"(?i)\b(episode|ep|sub indo|batch)\b")?.replace_all(title, "").to_string();
        let cache_key = title_clean.trim().to_string();

        if let Some(cached) = self.cache.get(&cache_key).await {
            return Ok(Some(cached));
        }

        let res = self.client.post("https://graphql.anilist.co")
            .json(&json!({
                "query": GET_ANIME_DETAILS,
                "variables": { "search": cache_key.clone() }
            }))
            .send().await?;

        let data: Value = res.json().await?;
        
        if let Some(media_list) = data.get("data").and_then(|d| d.get("Page")).and_then(|p| p.get("media")).and_then(|m| m.as_array()) {
            let mut best_media = None;
            let mut highest_score = 0.0;

            for m in media_list {
                let genres = m.get("genres").and_then(|g| g.as_array());
                let is_hentai = genres.map(|gs| gs.iter().any(|g| g.as_str() == Some("Hentai"))).unwrap_or(false);
                
                if is_hentai { continue; }

                let titles = [
                    m.get("title").and_then(|t| t.get("romaji")).and_then(|t| t.as_str()),
                    m.get("title").and_then(|t| t.get("english")).and_then(|t| t.as_str()),
                    m.get("title").and_then(|t| t.get("native")).and_then(|t| t.as_str()),
                ];

                for t in titles.into_iter().flatten() {
                    let score = jaro_winkler(&cache_key.to_lowercase(), &t.to_lowercase());
                    if score > highest_score {
                        highest_score = score;
                        best_media = Some(m);
                    }
                }
            }

            if highest_score > 0.7 {
                if let Some(m) = best_media {
                    let enriched = self.enrich_metadata(m.clone()).await;
                    self.cache.insert(cache_key, enriched.clone()).await;
                    return Ok(Some(enriched));
                }
            }
        }
        
        Ok(None)
    }

    async fn enrich_metadata(&self, media: Value) -> Value {
        let mut final_media = media.clone();
        
        if let Some(anilist_id) = media.get("id").and_then(|v| v.as_i64()) {
            if let Ok(enrich_data) = get_anime_enrichment(&self.db, anilist_id).await {
                if let Some(obj) = final_media.as_object_mut() {
                    if let Some(enrich_obj) = enrich_data.as_object() {
                        for (k, v) in enrich_obj {
                            // Only copy structural metadata directly
                            if k != "synopsis" && k != "canonicalTitle" && k != "canonicalSchedule" && k != "cleanTitle" && k != "nativeTitle" && k != "localStatus" {
                                obj.insert(k.clone(), v.clone());
                            }
                        }

                        // Override synopsis
                        if let Some(syn) = enrich_obj.get("synopsis").and_then(|v| v.as_str()) {
                            if !syn.is_empty() {
                                obj.insert("description".to_string(), json!(syn));
                                obj.insert("synopsis".to_string(), json!(syn)); // Also set root synopsis
                            }
                        }

                        // Override schedule
                        if let Some(sch) = enrich_obj.get("canonicalSchedule").and_then(|v| v.as_str()) {
                            if !sch.is_empty() {
                                obj.insert("airSchedule".to_string(), json!(sch));
                            }
                        }
                        
                        // Override Status
                        if let Some(st) = enrich_obj.get("localStatus").and_then(|v| v.as_str()) {
                            let st_lower = st.to_lowercase();
                            if st_lower.contains("completed") || st_lower.contains("tamat") {
                                obj.insert("status".to_string(), json!("FINISHED"));
                            } else {
                                obj.insert("status".to_string(), json!("RELEASING"));
                            }
                        }

                        // Handle Titles
                        // 1. Primary Title (cleanTitle / canonicalTitle) goes to title.english and title.romaji
                        let c_title = enrich_obj.get("canonicalTitle").and_then(|v| v.as_str())
                            .or_else(|| enrich_obj.get("cleanTitle").and_then(|v| v.as_str()));
                            
                        if let Some(c_title_str) = c_title {
                            if !c_title_str.is_empty() {
                                obj.insert("cleanTitle".to_string(), json!(c_title_str));
                                if let Some(title_obj) = obj.get_mut("title").and_then(|v| v.as_object_mut()) {
                                    title_obj.insert("english".to_string(), json!(c_title_str));
                                    title_obj.insert("romaji".to_string(), json!(c_title_str));
                                }
                            }
                        }

                        // 2. Secondary Title (nativeTitle) should be AniList's Romaji Title (not Kanji)
                        if let Some(title_obj) = obj.get("title").and_then(|v| v.as_object()) {
                            if let Some(romaji) = title_obj.get("romaji") {
                                obj.insert("nativeTitle".to_string(), romaji.clone());
                            }
                        }
                    }
                    obj.insert("detailUrl".to_string(), json!(format!("/anime/{}", anilist_id)));
                }
            }
        }

        final_media
    }
}
