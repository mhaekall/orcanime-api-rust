import asyncio
import sys
import os
import httpx
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv()

from db.connection import database
from services.cache import upstash_keys, upstash_get, upstash_del
from services.ingestion.main import IngestionEngine
from services.stream_cache import get_cached_stream

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def retry_failed():
    await database.connect()
    
    logger.info("Scanning Upstash Redis for ingest_progress:* keys...")
    keys = await upstash_keys("ingest_progress:*")
    if not keys:
        logger.info("No progress keys found.")
        await database.disconnect()
        return

    logger.info(f"Found {len(keys)} progress keys. Checking for orphans to retry...")
    
    engine = IngestionEngine()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Limit to first few to avoid long running in single cron hit if many exist
        for key in keys:
            parts = key.split(":")
            if len(parts) != 3:
                continue
            
            anilist_id = int(parts[1])
            episode_num = float(parts[2])
            
            # Check if currently locked
            lock_key = f"ingest:{anilist_id}:{episode_num}"
            is_locked = await upstash_get(lock_key)
            if is_locked:
                logger.info(f"Skipping {key} because it is currently locked (running).")
                continue

            # Check DB to see if the episode successfully uploaded
            row = await database.fetch_one(
                'SELECT id, "episodeUrl" FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :enum LIMIT 1',
                {"aid": anilist_id, "enum": episode_num}
            )
            
            if not row:
                logger.warning(f"Episode {anilist_id} Ep {episode_num} not found in DB.")
                continue
                
            is_successful = False
            if row["episodeUrl"] and ("tg-proxy" in row["episodeUrl"] or "workers.dev" in row["episodeUrl"]):
                is_successful = True
                
            if is_successful:
                logger.info(f"Episode {anilist_id} Ep {episode_num} is SUCCESSFUL. Cleaning up progress key only.")
                await upstash_del(key)
                continue

            # Not successful, let's retry. We need direct_url.
            logger.info(f"Episode {anilist_id} Ep {episode_num} is ORPHANED. Retrying ingest...")
            
            ep_id = row['id']
            
            sources_response = await get_cached_stream(anilist_id, episode_num)
            direct_url = ""
            provider_id = "unknown"
            
            if sources_response and "sources" in sources_response and len(sources_response["sources"]) > 0:
                for s in sources_response["sources"]:
                    if s.get("quality") == "720p" and s.get("type") in ["mp4", "direct", "hls"]:
                        direct_url = s.get("url", "")
                        provider_id = s.get("source", "unknown")
                        break
                
                if not direct_url:
                    for s in sources_response["sources"]:
                        if s.get("type") in ["mp4", "direct", "hls"]:
                            direct_url = s.get("url", "")
                            provider_id = s.get("source", "unknown")
                            break
                            
                if not direct_url:
                    direct_url = sources_response["sources"][0].get("url", "")
                    provider_id = sources_response["sources"][0].get("source", "unknown")
            
            if direct_url and "tg-proxy" not in direct_url:
                success = await engine.process_episode(
                    episode_id=ep_id,
                    anilist_id=anilist_id,
                    provider_id=provider_id,
                    episode_number=episode_num,
                    direct_video_url=direct_url
                )
                logger.info(f"Retry Result {anilist_id} Ep {episode_num}: {success}")
                if success:
                    # Clear progress key on success
                    await upstash_del(key)
                
                # Wait 7 minutes before the next episode
                logger.info("Waiting 7 minutes before next retry to avoid rate limits...")
                await asyncio.sleep(420)
            else:
                logger.error(f"Could not resolve direct URL for retry {anilist_id} Ep {episode_num}")

    logger.info("Retry completed.")
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(retry_failed())
