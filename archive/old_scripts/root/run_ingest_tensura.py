import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("apps/api"))

from db.connection import database
from services.stream_cache import stream_cache
from routes.stream_v2 import get_sources_v2
from services.ingestion.main import IngestionEngine

os.environ['PROXY_SECRET'] = "anime-pro-secure-2026"

async def run():
    await database.connect()
    anilist_id = 108511
    ep_num = 1.0
    
    ep_url = "https://kuronime.sbs/nonton-tensei-shitara-slime-datta-ken-season-2-episode-1/"
    print("Invalidating old cache...")
    await stream_cache.invalidate(ep_url)
    
    print("Fetching stream using stream_cache...")
    res = await stream_cache.get_stream(ep_url, "kuronime")
    
    target_src = next((s for s in res['sources'] if s['quality'] == '720p' and s['type'] == 'mp4'), None)
    if not target_src:
        print("No 720p MP4 target source found")
        await database.disconnect()
        return
        
    proxy_url = target_src['url']
    print(f"Proxy URL: {proxy_url}")
    
    row = await database.fetch_one('SELECT id FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep LIMIT 1', values={"aid": anilist_id, "ep": ep_num})
    ep_id = row['id']
    
    engine = IngestionEngine()
    print("Starting ingestion...")
    success = await engine.process_episode(
        episode_id=ep_id,
        anilist_id=anilist_id,
        provider_id="kuronime",
        episode_number=ep_num,
        direct_video_url=proxy_url
    )
    
    print(f"Hasil Ingestion: {success}")
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(run())
