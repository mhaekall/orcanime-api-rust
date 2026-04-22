import asyncio
import sys
import os

API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "apps/api"))
sys.path.insert(0, API_DIR)

from db.connection import database
from services.pipeline import sync_anime_episodes
from services.stream_cache import get_cached_stream
from services.ingestion.main import IngestionEngine
from sqlalchemy import text

async def do_ingest():
    aid = 154587
    ep = 2.0
    
    await database.connect()
    try:
        # 1. Sync to restore the deleted episode row
        print(f"Syncing episodes for {aid}...")
        res = await sync_anime_episodes(aid)
        print("Sync result:", res)
        
        # 2. Get episode ID
        row = await database.fetch_one('SELECT id FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep', values={"aid": aid, "ep": ep})
        if not row:
            print("Failed to restore episode 2!")
            return
            
        ep_id = row["id"]
        print(f"Episode ID for ep 2: {ep_id}")
        
        # 3. Get cached stream to find 720p direct link
        print("Resolving sources for ep 2...")
        stream_data = await get_cached_stream(aid, ep)
        direct_url = None
        provider = "unknown"
        
        if stream_data and "sources" in stream_data:
            # Cari 720p
            for s in stream_data["sources"]:
                if s.get("quality") == "720p" and s.get("type") in ("hls", "mp4", "direct"):
                    direct_url = s.get("raw_url") or s.get("url")
                    provider = s.get("source") or s.get("provider", "unknown")
                    break
                    
            # Fallback direct apa aja
            if not direct_url:
                for s in stream_data["sources"]:
                    if s.get("type") in ("hls", "mp4", "direct"):
                        direct_url = s.get("raw_url") or s.get("url")
                        provider = s.get("source") or s.get("provider", "unknown")
                        break
                        
        if not direct_url:
            print("Could not find a direct stream URL to ingest. Sources available:")
            if stream_data and "sources" in stream_data:
                for s in stream_data["sources"]:
                    print(f"  - Quality: {s.get('quality')} | Type: {s.get('type')} | URL: {s.get('url')[:60]}")
            return
            
        print(f"Found direct URL: {direct_url[:50]}... from {provider}")
        
        # 4. Ingest
        engine = IngestionEngine()
        print("Starting ingestion engine...")
        success = await engine.process_episode(ep_id, aid, provider, ep, direct_url)
        print(f"Ingestion success: {success}")
        
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(do_ingest())
