use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct AnimeResult {
    pub title: String,
    pub url: String,
    pub thumbnail: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct EpisodeSource {
    pub provider: String,
    pub quality: String,
    pub url: String,
    pub r#type: String, // e.g. "hls (direct)", "iframe"
}

// Defining a trait makes it easy to mock and swap scrapers
#[axum::async_trait]
pub trait AnimeProvider {
    async fn search(&self, query: &str) -> Result<Vec<AnimeResult>, Box<dyn std::error::Error + Send + Sync>>;
    async fn get_episode_sources(&self, episode_url: &str) -> Result<Vec<EpisodeSource>, Box<dyn std::error::Error + Send + Sync>>;
}
