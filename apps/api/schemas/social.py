from pydantic import BaseModel
from typing import Optional

class WatchProgressUpdate(BaseModel):
    user_id: str
    anilistId: int
    episodeNumber: float
    progressSeconds: int
    durationSeconds: int
    isCompleted: bool

class WatchEventCreate(BaseModel):
    user_id: str
    anilistId: int
    episodeNumber: float
    event_type: str # "start", "progress", "complete"
    timestamp_sec: int

class EpisodeLikeCreate(BaseModel):
    user_id: str
    anilistId: int
    episodeNumber: float

class WatchSessionUpdate(BaseModel):
    user_id: str
    anilist_id: int
    episode_number: float
    watch_duration_sec: int
    total_duration_sec: int
    quality_watched: str = "Auto"
    provider_used: Optional[str] = None
