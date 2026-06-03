use crate::providers::base::{AnimeProvider, AnimeResult, EpisodeSource};
use reqwest::Client;
use scraper::{Html, Selector};
use regex::Regex;

pub struct Samehadaku {
    client: Client,
    base_url: String,
}

impl Samehadaku {
    pub fn new(client: Client) -> Self {
        Self {
            client,
            base_url: "https://v2.samehadaku.how".to_string(),
        }
    }

    fn detect_quality(&self, text: &str) -> String {
        let text_lower = text.to_lowercase();
        if text_lower.contains("1080") { return "1080p".to_string(); }
        if text_lower.contains("720") { return "720p".to_string(); }
        if text_lower.contains("480") { return "480p".to_string(); }
        if text_lower.contains("360") { return "360p".to_string(); }
        if text_lower.contains("4k") { return "4k".to_string(); }
        "Auto".to_string()
    }

    fn detect_provider(&self, text: &str) -> String {
        text.replace("1080p", "").replace("720p", "").replace("480p", "").replace("360p", "").trim().to_string()
    }
}

#[axum::async_trait]
impl AnimeProvider for Samehadaku {
    async fn search(&self, query: &str) -> Result<Vec<AnimeResult>, Box<dyn std::error::Error + Send + Sync>> {
        let url = format!("{}/?s={}", self.base_url, urlencoding::encode(query));
        let text = self.client.get(&url)
            .header("Referer", &self.base_url)
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")
            .send().await?.text().await?;
            
        let doc = Html::parse_document(&text);
        let article_sel = Selector::parse("article.animpost").unwrap();
        let link_sel = Selector::parse("a").unwrap();
        let img_sel = Selector::parse("img").unwrap();

        let mut results = Vec::new();
        for el in doc.select(&article_sel) {
            if let Some(link) = el.select(&link_sel).next() {
                let href = link.value().attr("href").unwrap_or_default().to_string();
                let title = link.value().attr("title").map(|s| s.to_string()).unwrap_or_else(|| link.text().collect::<String>());
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
            .header("Referer", &self.base_url)
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")
            .send().await?.text().await?;

        let mut raw_sources = Vec::new();

        {
            let doc = Html::parse_document(&text);
            let opt_sel = Selector::parse(".east_player_option").unwrap();
            let span_sel = Selector::parse("span").unwrap();

            for opt in doc.select(&opt_sel) {
                let label_text = opt.select(&span_sel).next().map(|s| s.text().collect::<String>()).unwrap_or_else(|| "Unknown".to_string());
                let quality = self.detect_quality(&label_text);

                if !["360p", "480p", "720p", "1080p", "4k"].contains(&quality.as_str()) {
                    continue;
                }

                let post = opt.value().attr("data-post").unwrap_or_default();
                let nume = opt.value().attr("data-nume").unwrap_or_default();
                let typ = opt.value().attr("data-type").unwrap_or_default();

                raw_sources.push(EpisodeSource {
                    provider: self.detect_provider(&label_text),
                    quality,
                    url: format!("ajax://{}/{}/{}", post, nume, typ),
                    r#type: "iframe".to_string(),
                });
            }

            // Handle Download links (similar to Python parser)
            let dl_sel = Selector::parse(".download-eps").unwrap();
            let li_sel = Selector::parse("ul li").unwrap();
            let strong_sel = Selector::parse("strong").unwrap();
            let a_sel = Selector::parse("span a").unwrap();

            for container in doc.select(&dl_sel) {
                for li in container.select(&li_sel) {
                    let quality_label = li.select(&strong_sel).next().map(|s| s.text().collect::<String>()).unwrap_or_else(|| "Auto".to_string());
                    let quality = self.detect_quality(&quality_label);
                    
                    if !["360p", "480p", "720p", "1080p", "4k"].contains(&quality.as_str()) {
                        continue;
                    }

                    for a in li.select(&a_sel) {
                        let src_name = a.text().collect::<String>();
                        let url = a.value().attr("href").unwrap_or_default().to_string();

                        if url.starts_with("http") {
                            let is_direct = url.to_lowercase().contains("pixeldrain") || url.to_lowercase().contains("wibufile");
                            raw_sources.push(EpisodeSource {
                                provider: format!("{} (DL)", src_name),
                                quality: quality.clone(),
                                url,
                                r#type: if is_direct { "mp4 (direct)".to_string() } else { "iframe".to_string() },
                            });
                        }
                    }
                }
            }
        } // `doc` and Selectors are dropped here

        // Resolve ajax URLs
        let mut resolved = Vec::new();
        let iframe_re = Regex::new(r#"src=["']([^"']+)["']"#).unwrap();
        let blacklist = ["mega", "mediafire", "zippyshare", "solidfiles", "gofile", "pucuk"];

        for mut src in raw_sources {
            if src.url.starts_with("ajax://") {
                let clean_url = src.url.replace("ajax://", "");
                let parts: Vec<&str> = clean_url.split('/').collect();
                if parts.len() == 3 {
                    let post_id = parts[0];
                    let nume = parts[1];
                    let typ = parts[2];

                    let form_data = [
                        ("action", "player_ajax"),
                        ("post", post_id),
                        ("nume", nume),
                        ("type", typ),
                    ];

                    let ajax_res = self.client.post(&format!("{}/wp-admin/admin-ajax.php", self.base_url))
                        .header("Referer", &self.base_url)
                        .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")
                        .header("X-Requested-With", "XMLHttpRequest")
                        .form(&form_data)
                        .send().await?.text().await?;

                    if let Some(caps) = iframe_re.captures(&ajax_res) {
                        if let Some(matched) = caps.get(1) {
                            src.url = matched.as_str().to_string();
                            let url_lower = src.url.to_lowercase();
                            let is_direct = url_lower.contains("pixeldrain.com/api/file/") || 
                                            url_lower.contains("wibufile.com/video") || 
                                            url_lower.contains("s0.wibufile") ||
                                            (url_lower.ends_with(".mp4") && !url_lower.contains("/embed") && !url_lower.contains("/view"));
                            
                            if is_direct {
                                src.r#type = "mp4 (direct)".to_string();
                            }
                        }
                    }
                }
            }

            // Filtering blacklist
            let provider_lower = src.provider.to_lowercase();
            let url_lower = src.url.to_lowercase();
            
            if src.r#type == "mp4 (direct)" {
                resolved.push(src);
                continue;
            }

            let mut is_blacklisted = false;
            for b in &blacklist {
                if provider_lower.contains(b) || url_lower.contains(b) {
                    is_blacklisted = true;
                    break;
                }
            }

            if !is_blacklisted {
                resolved.push(src);
            }
        }

        Ok(resolved)
    }
}
