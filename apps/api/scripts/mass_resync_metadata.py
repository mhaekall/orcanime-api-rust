import sys
import os
import asyncio
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import database
from services.pipeline import sync_anime_episodes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def mass_resync():
    await database.connect()
    try:
        # Get all anilistIds that have mappings
        rows = await database.fetch_all('SELECT DISTINCT "anilistId" FROM anime_mappings')
        anilist_ids = [row["anilistId"] for row in rows]
        
        logger.info(f"Found {len(anilist_ids)} animes to resync. Starting mass resync...")
        
        # Concurrency semaphore
        sem = asyncio.Semaphore(3)
        
        async def sync_one(aid: int):
            async with sem:
                logger.info(f"Resyncing anilistId: {aid}")
                try:
                    await sync_anime_episodes(aid)
                except Exception as e:
                    logger.error(f"Failed to resync {aid}: {e}")
                    
        # Instead of asyncio.gather all at once, chunk it to avoid memory/connection issues
        chunk_size = 10
        for i in range(0, len(anilist_ids), chunk_size):
            chunk = anilist_ids[i:i+chunk_size]
            tasks = [sync_one(aid) for aid in chunk]
            await asyncio.gather(*tasks)
            # Sleep a bit to not hammer providers
            await asyncio.sleep(1)
            
        logger.info("Mass resync completed successfully!")
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(mass_resync())