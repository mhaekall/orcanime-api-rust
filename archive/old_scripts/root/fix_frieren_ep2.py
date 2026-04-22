import asyncio
from apps.api.db.connection import database
from sqlalchemy import text
import httpx
from apps.api.services.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN

async def fix():
    await database.connect()
    try:
        aid = 154587
        ep = 2.0
        
        # 1. Update the database to remove the corrupt TG Proxy URL
        # We can just delete the episode row or set its episodeUrl to a dummy so the scraper picks it up again from the mappings.
        # But wait, episodes table holds provider URLs originally. Let's just delete the row for Ep 2, 
        # so next time it is requested, it will re-sync or re-scrape from the provider.
        res = await database.execute(text(f'DELETE FROM episodes WHERE "anilistId" = {aid} AND "episodeNumber" = {ep}'))
        print(f"Deleted {res} row(s) from episodes for Frieren Ep 2.")
        
        # 2. Also delete from video_cache just in case
        await database.execute(text(f'DELETE FROM video_cache WHERE "episodeUrl" LIKE \'%tg-proxy%\''))
        print("Cleaned up video_cache.")
        
        # 3. Clear Redis keys related to this episode
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
            # delete the stream cache, lock, and progress
            keys_to_delete = [
                f"ingest:{aid}:{ep}",
                f"ingest_progress:{aid}:{ep}",
                f"sync_anime:{aid}",
                f"lock:sync:{aid}",
                f"cb:kuronime:fails"
            ]
            for key in keys_to_delete:
                await client.post(f"{UPSTASH_REDIS_REST_URL}/DEL/{key}", headers=headers)
                
            print("Cleared Redis locks and progress.")
            
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(fix())
