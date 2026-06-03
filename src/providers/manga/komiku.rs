use crate::providers::manga::base::{MangaChapter, MangaProvider};
use reqwest::Client;
use scraper::{Html, Selector};
use regex::Regex;

pub struct Komiku {
    client: Client,
}

impl Komiku {
    pub fn new(client: Client) -> Self {
        Self { client }
    }
}

#[axum::async_trait]
impl MangaProvider for Komiku {
    fn id(&self) -> &'static str {
        "komiku"
    }

    fn name(&self) -> &'static str {
        "Komiku"
    }

    async fn fetch_chapters(&self, title: &str) -> Result<Vec<MangaChapter>, Box<dyn std::error::Error + Send + Sync>> {
        let safe_title = urlencoding::encode(title);
        let search_url = format!("https://komiku.id/?post_type=manga&s={}", safe_title);
        
        let res = self.client.get(&search_url)
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            .send().await?;

        if !res.status().is_success() {
            return Ok(Vec::new());
        }

        let html = res.text().await?;
        
        let detail_url = {
            let doc = Html::parse_document(&html);
            let post_sel = Selector::parse(".bge, .bgei").unwrap();
            let link_sel = Selector::parse("h3 a, a").unwrap();

            if let Some(post) = doc.select(&post_sel).next() {
                if let Some(link) = post.select(&link_sel).next() {
                    let mut url = link.value().attr("href").unwrap_or_default().to_string();
                    if url.starts_with("/") {
                        url = format!("https://komiku.id{}", url);
                    }
                    Some(url)
                } else {
                    None
                }
            } else {
                None
            }
        };

        if detail_url.is_none() {
            return Ok(Vec::new());
        }

        let det_res = self.client.get(&detail_url.unwrap())
            .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            .send().await?;
            
        let det_html = det_res.text().await?;
        let det_doc = Html::parse_document(&det_html);
        let chapter_sel = Selector::parse("#Daftar_Chapter tr td:first-child a").unwrap();

        let mut temp_chapters = Vec::new();
        let re = Regex::new(r"(\d+(\.\d+)?)").unwrap();

        for ch in det_doc.select(&chapter_sel) {
            let ch_title = ch.text().collect::<String>().trim().to_string();
            let mut ch_link = ch.value().attr("href").unwrap_or_default().to_string();
            if ch_link.starts_with("/") {
                ch_link = format!("https://komiku.id{}", ch_link);
            }

            let ch_num_str = if let Some(caps) = re.captures(&ch_title) {
                caps[1].to_string()
            } else {
                "0".to_string()
            };

            let ch_num: f32 = ch_num_str.parse().unwrap_or(0.0);

            temp_chapters.push(MangaChapter {
                id: format!("{}|{}", self.id(), urlencoding::encode(&ch_link)),
                provider_id: self.id().to_string(),
                number: ch_num_str,
                episode_number: ch_num,
                title: ch_title,
                url: ch_link,
            });
        }

        Ok(temp_chapters)
    }
}
