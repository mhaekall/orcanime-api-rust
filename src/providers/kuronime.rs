use crate::providers::base::{AnimeProvider, AnimeResult, EpisodeSource};
use crate::utils::crypto::decrypt_cryptojs_aes;
use reqwest::Client;
use scraper::{Html, Selector};
use serde_json::Value;
use regex::Regex;

pub struct Kuronime {
    client: Client,
    base_url: String,
}

use crate::providers::types::EpisodeListResult;

impl Kuronime {
    pub fn new(client: Client) -> Self {
        Self {
            client,
            base_url: "https://kuronime.sbs".to_string(),
        }
    }

    pub async fn fetch_episode_list(&self, detail_url: &str) -> Result<Vec<EpisodeListResult>, Box<dyn std::error::Error + Send + Sync>> {
        let text = self.client.get(detail_url).send().await?.text().await?;
        let doc = Html::parse_document(&text);
        let ep_sel = Selector::parse("div.bxcl ul li span.lchx a").unwrap();
        
        let mut episodes = Vec::new();
        let re = Regex::new(r"(?i)(?:episode|eps?)[.\s]*(\d+(?:[.,]\d+)?)").unwrap();

        for el in doc.select(&ep_sel) {
            let url = el.value().attr("href").unwrap_or_default().to_string();
            let title = el.text().collect::<String>().trim().to_string();
            
            let num = if let Some(caps) = re.captures(&title) {
                caps[1].replace(",", ".").parse::<f32>().unwrap_or(0.0)
            } else {
                0.0
            };

            if num > 0.0 {
                episodes.push(EpisodeListResult {
                    number: num,
                    title,
                    url,
                });
            }
        }
        Ok(episodes)
    }

    fn extract_req_id(&self, html: &str) -> Option<String> {
        // Find var something = "..."
        // e.g. var _0x123abc = "req_id_string_long"
        // Simplified regex logic:
        let re = regex::Regex::new(r#"var\s+[a-zA-Z0-9_]+\s*=\s*["']([^"']{100,})["']"#).ok()?;
        if let Some(caps) = re.captures(html) {
            return Some(caps.get(1)?.as_str().to_string());
        }
        None
    }
}

#[axum::async_trait]
impl AnimeProvider for Kuronime {
    async fn search(&self, query: &str) -> Result<Vec<AnimeResult>, Box<dyn std::error::Error + Send + Sync>> {
        let url = format!("{}/?s={}", self.base_url, urlencoding::encode(query));
        let text = self.client.get(&url).send().await?.text().await?;
        let doc = Html::parse_document(&text);
        
        let item_sel = Selector::parse("div.bixbox div.bs div.bsx").unwrap();
        let title_sel = Selector::parse("div.tt").unwrap();
        let link_sel = Selector::parse("a").unwrap();
        let img_sel = Selector::parse("img").unwrap();

        let mut results = Vec::new();
        for el in doc.select(&item_sel) {
            if let Some(link) = el.select(&link_sel).next() {
                let href = link.value().attr("href").unwrap_or_default().to_string();
                let title = link.select(&title_sel).next().map(|t| t.text().collect::<String>()).unwrap_or_default().trim().to_string();
                let thumbnail = el.select(&img_sel).next().and_then(|img| img.value().attr("src")).map(|s| s.to_string());
                
                if !title.is_empty() {
                    results.push(AnimeResult { title, url: href, thumbnail });
                }
            }
        }
        Ok(results)
    }

    async fn get_episode_sources(&self, episode_url: &str) -> Result<Vec<EpisodeSource>, Box<dyn std::error::Error + Send + Sync>> {
        let html = self.client.get(episode_url).send().await?.text().await?;
        let req_id = match self.extract_req_id(&html) {
            Some(id) => id,
            None => return Err("Kuronime: Cannot extract req_id (possibly protected by Cloudflare)".into()),
        };

        let api_url = "https://animeku.org/api/v9/sources";
        
        let res = self.client.post(api_url)
            .header("Referer", "https://kuronime.sbs/")
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            .header("Accept", "application/json, text/javascript, */*; q=0.01")
            .header("X-Requested-With", "XMLHttpRequest")
            .header("Content-Type", "application/json")
            .json(&serde_json::json!({"id": req_id}))
            .send().await?;

        let res_text = res.text().await?;
        let data: Value = serde_json::from_str(&res_text).unwrap_or_else(|_| serde_json::json!({}));
        let mut sources = Vec::new();
        let decrypt_key = "3&!Z0M,VIZ;dZW==";

        let mut process_direct = |key: &str, quality: &str| {
            if let Some(encrypted_val) = data.get(key).and_then(|v| v.as_str()) {
                if let Ok(decrypted_str) = decrypt_cryptojs_aes(encrypted_val, decrypt_key) {
                    if decrypted_str.starts_with("http") {
                        sources.push(EpisodeSource {
                            provider: "KuroPlayer".to_string(),
                            quality: quality.to_string(),
                            url: decrypted_str,
                            r#type: "hls (direct)".to_string(),
                        });
                    } else if let Ok(parsed) = serde_json::from_str::<Value>(&decrypted_str) {
                        if let Some(src) = parsed.get("src").and_then(|s| s.as_str()) {
                            sources.push(EpisodeSource {
                                provider: "KuroPlayer".to_string(),
                                quality: quality.to_string(),
                                url: src.to_string(),
                                r#type: "hls (direct)".to_string(),
                            });
                        }
                    }
                }
            }
        };

        process_direct("src", "1080p");
        process_direct("src_sd", "480p");

        if let Some(mirror_enc) = data.get("mirror").and_then(|v| v.as_str()) {
            if let Ok(decrypted_str) = decrypt_cryptojs_aes(mirror_enc, decrypt_key) {
                if let Ok(mirror_json) = serde_json::from_str::<Value>(&decrypted_str) {
                    if let Some(embeds) = mirror_json.get("embed").and_then(|v| v.as_object()) {
                        for (res_key, res_providers) in embeds {
                            let quality = res_key.replace("v", "");
                            if !["360p", "480p", "720p", "1080p", "4k"].contains(&quality.as_str()) { continue; }
                            
                            if let Some(providers) = res_providers.as_object() {
                                for (p_name, p_url_val) in providers {
                                    if let Some(p_url) = p_url_val.as_str() {
                                        if !p_url.is_empty() {
                                            let is_direct = p_url.to_lowercase().contains("pixeldrain");
                                            sources.push(EpisodeSource {
                                                provider: p_name.to_string(),
                                                quality: quality.clone(),
                                                url: p_url.to_string(),
                                                r#type: if is_direct { "mp4 (direct)".to_string() } else { "iframe".to_string() },
                                            });
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        if sources.is_empty() {
            return Err(format!("Kuronime streams empty. API Response: {}", res_text).into());
        }

        Ok(sources)
    }
}
