import asyncio
import sys
import os

API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "apps/api"))
sys.path.insert(0, API_DIR)

from db.connection import database
from services.stream_cache import get_cached_stream
from services.ingestion.main import IngestionEngine
from sqlalchemy import text

async def ingest_with_delay():
    aid = 154587
    
    await database.connect()
    try:
        # Get all episodes >= 3 that don't have tg-proxy yet
        eps = await database.fetch_all(
            '''
            SELECT id, "episodeNumber", "episodeUrl" 
            FROM episodes 
            WHERE "anilistId" = :aid 
              AND "episodeNumber" >= 3 
              AND "episodeUrl" NOT LIKE '%tg-proxy%'
              AND "episodeUrl" NOT LIKE '%workers.dev%'
            ORDER BY "episodeNumber" ASC
            ''',
            values={"aid": aid}
        )
        
        if not eps:
            print("No episodes >= 3 found that need ingestion.")
            return
            
        print(f"Found {len(eps)} episodes to ingest with delay.")
    finally:
        await database.disconnect()

    engine = IngestionEngine()
    
    for idx, ep_row in enumerate(eps):
        ep_id = ep_row["id"]
        ep_num = ep_row["episodeNumber"]
        
        print(f"\n--- [{idx+1}/{len(eps)}] Starting delayed ingestion for Ep {ep_num} ---")
        
        await database.connect()
        try:
            # 1. Resolve sources
            stream_data = await get_cached_stream(aid, ep_num)
        finally:
            await database.disconnect()
            
        direct_sources = []
        if stream_data and "sources" in stream_data:
            # Gather ONLY 720p direct sources
            for s in stream_data["sources"]:
                if s.get("type") in ("hls", "mp4", "direct") and s.get("quality") == "720p":
                    direct_sources.append(s)
            
        success = False
        for s in direct_sources:
            direct_url = s.get("url")
            provider = s.get("source") or s.get("provider", "unknown")
            print(f"Trying direct URL for Ep {ep_num}: {direct_url[:50]}... from {provider} (Quality: {s.get('quality')})")
            
            success = await engine.process_episode(ep_id, aid, provider, ep_num, direct_url)
            if success:
                print(f"✅ Ingestion success for Ep {ep_num}!")
                break
            else:
                print(f"⚠️ Failed with {provider} {s.get('quality')}, trying next source...")
                
        if not success:
            print(f"❌ Could not ingest Ep {ep_num} with any direct sources.")
            
        # Delay 3 minutes if not the last episode
        if idx < len(eps) - 1:
            print("Waiting 3 minutes before next episode...")
            await asyncio.sleep(3 * 60)

if __name__ == "__main__":
    # Ensure stdout is unbuffered for logging
    sys.stdout.reconfigure(line_buffering=True)
    asyncio.run(ingest_with_delay())
