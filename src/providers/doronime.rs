use crate::providers::base::{AnimeProvider, AnimeResult, EpisodeSource};
use reqwest::Client;
use scraper::{Html, Selector};
use regex::Regex;

pub struct Doronime {
    client: Client,
    base_url: String,
}

impl Doronime {
    pub fn new(client: Client) -> Self {
        Self {
            client,
            base_url: "https://doronime.id".to_string(),
        }
    }

    fn detect_quality(&self, text: &str) -> String {
        let text_lower = text.to_lowercase();
        if text_lower.contains("1080") { return "1080p".to_string(); }
        if text_lower.contains("720") { return "720p".to_string(); }
        if text_lower.contains("480") { return "480p".to_string(); }
        if text_lower.contains("360") { return "360p".to_string(); }
        "Auto".to_string()
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
impl AnimeProvider for Doronime {
    async fn search(&self, query: &str) -> Result<Vec<AnimeResult>, Box<dyn std::error::Error + Send + Sync>> {
        let url = format!("{}/?s={}", self.base_url, urlencoding::encode(query));
        let text = self.client.get(&url)
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            .header("Referer", &self.base_url)
            .send().await?.text().await?;
        
        let doc = Html::parse_document(&text);
        let article_sel = Selector::parse("article.item-list").unwrap();
        let link_sel = Selector::parse("h2.post-box-title a").unwrap();
        let img_sel = Selector::parse("img").unwrap();

        let mut results = Vec::new();
        for el in doc.select(&article_sel) {
            if let Some(link) = el.select(&link_sel).next() {
                let href = link.value().attr("href").unwrap_or_default().to_string();
                let title = link.text().collect::<String>().trim().to_string();
                let thumbnail = el.select(&img_sel).next().and_then(|img| img.value().attr("src")).map(|s| s.to_string());
                
                if !title.is_empty() {
                    results.push(AnimeResult { title, url: href, thumbnail });
                }
            }
        }
        
        Ok(results)
    }

    async fn get_episode_sources(&self, episode_url: &str) -> Result<Vec<EpisodeSource>, Box<dyn std::error::Error + Send + Sync>> {
        let text = self.client.get(episode_url)
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            .header("Referer", &self.base_url)
            .send().await?.text().await?;

        let mut raw_sources = Vec::new();
        
        {
            let doc = Html::parse_document(&text);
            let table_sel = Selector::parse("table").unwrap();
            let tr_sel = Selector::parse("tr").unwrap();
            let td_sel = Selector::parse("td").unwrap();
            let a_sel = Selector::parse("a").unwrap();

            for table in doc.select(&table_sel) {
                for row in table.select(&tr_sel) {
                    let cells: Vec<_> = row.select(&td_sel).collect();
                    if cells.len() >= 2 {
                        let quality_text = cells[0].text().collect::<String>().to_lowercase();
                        if ["1080", "720", "480", "360"].iter().any(|q| quality_text.contains(q)) {
                            let quality = self.detect_quality(&quality_text);
                            for a in cells[1].select(&a_sel) {
                                let mut provider_name = a.text().collect::<String>().trim().to_uppercase();
                                let raw_url = a.value().attr("href").unwrap_or_default().to_string();

                                if !raw_url.is_empty() {
                                    if raw_url.contains("google.com") || raw_url.contains("drive.") {
                                        provider_name = "GDRIVE".to_string();
                                    } else if raw_url.contains("acefile") {
                                        provider_name = "ACEFILE".to_string();
                                    } else if raw_url.contains("mega.nz") {
                                        provider_name = "MEGA".to_string();
                                    }

                                    raw_sources.push(EpisodeSource {
                                        provider: format!("Doronime - {}", provider_name),
                                        quality: quality.clone(),
                                        url: raw_url.clone(),
                                        r#type: if raw_url.contains("drive") || raw_url.contains("acefile") { "direct".to_string() } else { "iframe".to_string() },
                                    });
                                }
                            }
                        }
                    }
                }
            }

            if raw_sources.is_empty() {
                let li_sel = Selector::parse("ul li").unwrap();
                for li in doc.select(&li_sel) {
                    let text = li.text().collect::<String>().to_lowercase();
                    if ["1080", "720", "480", "360"].iter().any(|q| text.contains(q)) {
                        let quality = self.detect_quality(&text);
                        for a in li.select(&a_sel) {
                            let raw_url = a.value().attr("href").unwrap_or_default().to_string();
                            if !raw_url.is_empty() {
                                raw_sources.push(EpisodeSource {
                                    provider: format!("Doronime - {}", a.text().collect::<String>().trim()),
                                    quality: quality.clone(),
                                    url: raw_url,
                                    r#type: "iframe".to_string(),
                                });
                            }
                        }
                    }
                }
            }
        } // doc dropped

        // Resolve iframe streams concurrently
        let mut tasks = Vec::new();
        for mut src in raw_sources {
            if src.r#type == "iframe" {
                let client_clone = self.client.clone();
                let ref_clone = episode_url.to_string();
                let t = tokio::spawn(async move {
                    let op = Doronime::new(client_clone);
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

        Ok(resolved_sources)
    }
}
