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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def delete_telegram_message(client: httpx.AsyncClient, bot_token: str, chat_id: str, message_id: int):
    url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
    try:
        res = await client.post(url, json={"chat_id": chat_id, "message_id": message_id})
        if not res.is_success:
            # Maybe message already deleted
            logger.debug(f"Failed to delete {message_id}: {res.text}")
    except Exception as e:
        logger.warning(f"Error deleting {message_id}: {e}")

async def purge_orphans():
    await database.connect()
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not chat_id:
        logger.error("TELEGRAM_CHAT_ID not set. Cannot purge messages.")
        await database.disconnect()
        return

    logger.info("Scanning Upstash Redis for ingest_progress:* keys...")
    keys = await upstash_keys("ingest_progress:*")
    if not keys:
        logger.info("No progress keys found.")
        await database.disconnect()
        return

    logger.info(f"Found {len(keys)} progress keys. Checking for orphans...")

    async with httpx.AsyncClient(timeout=30.0) as client:
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
                'SELECT "episodeUrl" FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :enum LIMIT 1',
                {"aid": anilist_id, "enum": episode_num}
            )
            
            is_successful = False
            if row and ("tg-proxy" in row["episodeUrl"] or "workers.dev" in row["episodeUrl"]):
                is_successful = True
                
            progress_data = await upstash_get(key)
            if not progress_data or not isinstance(progress_data, dict):
                # Invalid or old format, just clean up the key
                upstash_del(key)
                continue

            if is_successful:
                # Successfully uploaded, so the segments are NOT orphaned.
                # We can just clean up the redis key to save space.
                logger.info(f"Episode {anilist_id} Ep {episode_num} is SUCCESSFUL. Cleaning up progress key only.")
                upstash_del(key)
                continue

            # If not successful, the chunks are ORPHANED. We must delete them from Telegram.
            logger.info(f"Episode {anilist_id} Ep {episode_num} is ORPHANED. Purging {len(progress_data)} segments from Telegram...")
            
            deleted_count = 0
            for seg_idx, file_data in progress_data.items():
                if isinstance(file_data, dict):
                    msg_id = file_data.get("message_id")
                    bot_token = file_data.get("bot_token")
                    if msg_id and bot_token:
                        await delete_telegram_message(client, bot_token, chat_id, msg_id)
                        deleted_count += 1
                        await asyncio.sleep(0.05) # Prevent hitting bot api limits
            
            logger.info(f"Purged {deleted_count} messages for {key}.")
            upstash_del(key)

    logger.info("Purge completed successfully.")
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(purge_orphans())