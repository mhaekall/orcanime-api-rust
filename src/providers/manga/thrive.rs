use crate::providers::manga::base::{MangaChapter, MangaProvider};
use reqwest::Client;
use scraper::{Html, Selector};
use serde_json::Value;
use strsim::jaro_winkler;

pub struct Thrive {
    client: Client,
}

impl Thrive {
    pub fn new(client: Client) -> Self {
        Self { client }
    }
}

#[axum::async_trait]
impl MangaProvider for Thrive {
    fn id(&self) -> &'static str {
        "thrive"
    }

    fn name(&self) -> &'static str {
        "Thrive.moe"
    }

    async fn fetch_chapters(&self, title: &str) -> Result<Vec<MangaChapter>, Box<dyn std::error::Error + Send + Sync>> {
        let safe_title = urlencoding::encode(title);
        
        let home_res = self.client.get("https://thrive.moe/")
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            .send().await?;

        if !home_res.status().is_success() {
            return Ok(Vec::new());
        }

        let html = home_res.text().await?;
        
        let build_id = {
            let doc = Html::parse_document(&html);
            let next_data_sel = Selector::parse("script#__NEXT_DATA__").unwrap();

            if let Some(el) = doc.select(&next_data_sel).next() {
                let data: Value = serde_json::from_str(&el.text().collect::<String>()).unwrap_or(Value::Null);
                if let Some(bid) = data.get("buildId").and_then(|v| v.as_str()) {
                    Some(bid.to_string())
                } else {
                    None
                }
            } else {
                None
            }
        };

        if build_id.is_none() {
            return Ok(Vec::new());
        }

        let search_api = format!("https://thrive.moe/_next/data/{}/search.json?q={}", build_id.as_ref().unwrap(), safe_title);
        let search_res = self.client.get(&search_api)
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            .send().await?;

        if !search_res.status().is_success() {
            return Ok(Vec::new());
        }

        let search_data: Value = search_res.json().await.unwrap_or(Value::Null);
        let results = search_data.get("pageProps").and_then(|p| p.get("res")).and_then(|r| r.as_array());

        if results.is_none() {
            return Ok(Vec::new());
        }

        let mut best_post = None;
        let mut best_score = 0.0;
        let clean_search = title.to_lowercase();

        for item in results.unwrap() {
            let post_title = item.get("title").and_then(|t| t.as_str()).unwrap_or("").to_lowercase();
            let score = if post_title.contains(&clean_search) || clean_search.contains(&post_title) {
                1.0
            } else {
                jaro_winkler(&clean_search, &post_title) as f64
            };

            if score > best_score {
                best_score = score;
                best_post = Some(item);
            }
        }

        if best_score < 0.5 || best_post.is_none() {
            return Ok(Vec::new());
        }

        let manga_id = best_post.unwrap().get("id").and_then(|id| id.as_str()).unwrap_or("");
        if manga_id.is_empty() {
            return Ok(Vec::new());
        }

        let detail_api = format!("https://thrive.moe/_next/data/{}/title/{}.json", build_id.as_ref().unwrap(), manga_id);
        let detail_res = self.client.get(&detail_api)
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            .send().await?;

        if !detail_res.status().is_success() {
            return Ok(Vec::new());
        }

        let detail_data: Value = detail_res.json().await.unwrap_or(Value::Null);
        let chapters_raw = detail_data.get("pageProps").and_then(|p| p.get("chapterlist")).and_then(|c| c.as_array());

        let mut temp_chapters = Vec::new();
        if let Some(chapters) = chapters_raw {
            for ch in chapters {
                let ch_id = ch.get("chapter_id").and_then(|id| id.as_str()).unwrap_or("");
                let ch_num_str = ch.get("chapter_number").and_then(|n| n.as_str()).unwrap_or("0");
                
                if ch_id.is_empty() || ch_num_str.is_empty() {
                    continue;
                }

                let ch_num: f32 = ch_num_str.parse().unwrap_or(0.0);
                let ch_link = format!("https://thrive.moe/read/{}", ch_id);
                
                let mut ch_title = format!("Chapter {}", ch_num_str);
                if let Some(title_ext) = ch.get("chapter_title").and_then(|t| t.as_str()) {
                    if !title_ext.is_empty() {
                        ch_title = format!("{} - {}", ch_title, title_ext);
                    }
                }

                temp_chapters.push(MangaChapter {
                    id: format!("{}|{}", self.id(), urlencoding::encode(&ch_link)),
                    provider_id: self.id().to_string(),
                    number: ch_num_str.to_string(),
                    episode_number: ch_num,
                    title: ch_title,
                    url: ch_link,
                });
            }
        }

        Ok(temp_chapters)
    }
}
