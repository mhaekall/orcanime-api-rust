use crate::providers::base::{AnimeProvider, AnimeResult, EpisodeSource};
use reqwest::Client;
use regex::Regex;
use std::collections::HashSet;

pub struct Oploverz {
    client: Client,
    base_url: String,
}

impl Oploverz {
    pub fn new(client: Client) -> Self {
        Self {
            client,
            base_url: "https://vip.oploverz.ltd".to_string(),
        }
    }

    async fn resolve_iframe(&self, iframe_src: &str, referer: &str) -> Option<String> {
        let res = self.client.get(iframe_src)
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            .header("Referer", referer)
            .send().await.ok()?;
        
        let html = res.text().await.ok()?;

        let source_re = Regex::new(r#"(?i)<source\s+[^>]*src=["']([^"']+)["']"#).unwrap();
        if let Some(caps) = source_re.captures(&html) {
            return Some(caps[1].to_string());
        }

        let url_re = Regex::new(r#""url"\s*:\s*"([^"]+)""#).unwrap();
        if let Some(caps) = url_re.captures(&html) {
            let url = caps[1].replace("\\/", "/");
            if url.contains(".mp4") || url.contains(".m3u8") {
                return Some(url);
            }
        }

        let mp4up_re = Regex::new(r#"player\.src\(\s*\{\s*src:\s*["']([^"']+)["']"#).unwrap();
        if let Some(caps) = mp4up_re.captures(&html) {
            return Some(caps[1].to_string());
        }

        None
    }
}

#[axum::async_trait]
impl AnimeProvider for Oploverz {
    async fn search(&self, query: &str) -> Result<Vec<AnimeResult>, Box<dyn std::error::Error + Send + Sync>> {
        let url = format!("{}/?s={}", self.base_url, urlencoding::encode(query));
        let text = self.client.get(&url).send().await?.text().await?;
        
        let mut results = Vec::new();
        let mut seen = HashSet::new();

        let search_re = Regex::new(r#"series:\{id:\d+,(?:seriesId:\d+,)?title:"([^"]+)",[^}]*?slug:"([^"]+)""#).unwrap();
        
        for caps in search_re.captures_iter(&text) {
            let title = caps[1].replace("\\\"", "\"");
            let slug = caps[2].to_string();

            if seen.insert(slug.clone()) {
                results.push(AnimeResult {
                    title,
                    url: format!("{}/series/{}", self.base_url, slug),
                    thumbnail: None,
                });
            }
        }
        
        Ok(results)
    }

    async fn get_episode_sources(&self, episode_url: &str) -> Result<Vec<EpisodeSource>, Box<dyn std::error::Error + Send + Sync>> {
        let html = self.client.get(episode_url).send().await?.text().await?;
        let mut raw_sources = Vec::new();

        // 1. Iframe Streams
        let stream_sec_re = Regex::new(r#"streamUrl:(\[.*?\])"#).unwrap();
        let src_re = Regex::new(r#"\{source:"([^"]+)",url:"(https?://[^"]+)"\}"#).unwrap();

        if let Some(caps) = stream_sec_re.captures(&html) {
            let block = &caps[1];
            for c in src_re.captures_iter(block) {
                raw_sources.push(EpisodeSource {
                    provider: c[1].to_string(),
                    quality: "Auto".to_string(),
                    url: c[2].to_string(),
                    r#type: "iframe".to_string(),
                });
            }
        }

        // 2. Download Links
        let dl_sec_re = Regex::new(r#"quality:"([^"]+)",download_links:\[(.*?)\]"#).unwrap();
        let host_re = Regex::new(r#"host:"([^"]+)",url:"([^"]+)""#).unwrap();

        for cap_dl in dl_sec_re.captures_iter(&html) {
            let quality = cap_dl[1].to_string();
            let block = &cap_dl[2];
            
            for c in host_re.captures_iter(block) {
                let url = c[2].to_string();
                if url.to_lowercase().contains("pixeldrain") {
                    let api_url = if url.contains("/u/") {
                        let file_id = url.split("/u/").last().unwrap_or("").split('?').next().unwrap_or("");
                        format!("https://pixeldrain.com/api/file/{}", file_id)
                    } else {
                        url
                    };
                    
                    raw_sources.push(EpisodeSource {
                        provider: "Pixeldrain (Oploverz)".to_string(),
                        quality: quality.clone(),
                        url: api_url,
                        r#type: "mp4 (direct)".to_string(),
                    });
                }
            }
        }

        // 3. Resolve iframe streams concurrently
        let mut tasks = Vec::new();
        for mut src in raw_sources {
            if src.r#type == "iframe" {
                let client_clone = self.client.clone();
                let ref_clone = episode_url.to_string();
                // Spawn a blocking task to do async HTTP request
                let t = tokio::spawn(async move {
                    let op = Oploverz::new(client_clone);
                    if let Some(direct) = op.resolve_iframe(&src.url, &ref_clone).await {
                        src.url = direct.clone();
                        src.r#type = if direct.to_lowercase().contains(".mp4") {
                            "mp4 (direct)".to_string()
                        } else {
                            "hls (direct)".to_string()
                        };
                    }
                    src
                });
                tasks.push(t);
            } else {
                let t = tokio::spawn(async move { src });
                tasks.push(t);
            }
        }

        let mut resolved_sources = Vec::new();
        for task in tasks {
            if let Ok(src) = task.await {
                resolved_sources.push(src);
            }
        }

        let blacklist = ["nonton online", "mega", "filedon", "vidhide", "pucuk", "gofile", "kraken", "acefile", "mediafire", "doodstream", "zippyshare", "solidfiles"];
        let mut final_sources = Vec::new();

        for s in resolved_sources {
            let p_lower = s.provider.to_lowercase();
            let u_lower = s.url.to_lowercase();
            let is_blacklisted = blacklist.iter().any(|b| p_lower.contains(b) || u_lower.contains(b));
            
            if !is_blacklisted {
                final_sources.push(s);
            }
        }

        Ok(final_sources)
    }
}
