import asyncio
import json
import sys
import os

API_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "apps/api"))
sys.path.insert(0, API_DIR)

from db.connection import database
from services.stream_cache import get_cached_stream

async def find_streams():
    aid = 154587
    
    await database.connect()
    try:
        # Get all episodes for this anime >= 2
        eps = await database.fetch_all(
            '''
            SELECT DISTINCT "episodeNumber" 
            FROM episodes 
            WHERE "anilistId" = :aid AND "episodeNumber" >= 2
            ORDER BY "episodeNumber" ASC
            ''',
            values={"aid": aid}
        )
        
        if not eps:
            print("No episodes found >= 2")
            return
            
        print(f"Found {len(eps)} episodes to check.")
        
        for ep_row in eps:
            ep_num = ep_row["episodeNumber"]
            print(f"\\n--- Checking Episode {ep_num} ---")
            
            res = await get_cached_stream(aid, ep_num)
            
            if res and "sources" in res and len(res["sources"]) > 0:
                direct_sources = [s for s in res["sources"] if s.get("type") in ("hls", "mp4", "direct")]
                if direct_sources:
                    print(f"✅ Found {len(direct_sources)} direct streams!")
                    for s in direct_sources:
                        print(f"  - Quality: {s.get('quality')} | Provider: {s.get('provider')} | URL: {s.get('url')}")
                else:
                    print(f"⚠️ No direct streams found (only iframe). Raw sources:")
                    for s in res["sources"]:
                        print(f"  - Type: {s.get('type')} | Provider: {s.get('provider')} | URL: {s.get('url')}")
            else:
                print("❌ No sources returned.")
                
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(find_streams())
