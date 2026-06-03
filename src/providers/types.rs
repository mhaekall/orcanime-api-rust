use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct EpisodeListResult {
    pub number: f32,
    pub title: String,
    pub url: String,
}
