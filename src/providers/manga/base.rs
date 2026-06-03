use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct MangaChapter {
    pub id: String,
    pub provider_id: String,
    pub number: String,
    pub episode_number: f32,
    pub title: String,
    pub url: String,
}

#[axum::async_trait]
pub trait MangaProvider {
    fn id(&self) -> &'static str;
    fn name(&self) -> &'static str;
    async fn fetch_chapters(&self, title: &str) -> Result<Vec<MangaChapter>, Box<dyn std::error::Error + Send + Sync>>;
}
