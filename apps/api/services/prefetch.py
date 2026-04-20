import asyncio
import logging
from sqlalchemy import select, and_, func
from db.connection import database
from db.models import anime_metadata, episodes
from services.queue import enqueue_sync, enqueue_ingest_batch
from services.pipeline import resolve_episode_sources

logger = logging.getLogger(__name__)

async def get_ingestion_stats():
    """
    Returns statistics about total episodes and how many are successfully ingested to Telegram.
    """
    try:
        # Total episodes in DB
        ep_count_query = 'SELECT COUNT(*) as count FROM episodes'
        total_eps = await database.fetch_one(ep_count_query)
        total_eps = total_eps["count"] if total_eps else 0

        # Ingested episodes (URL contains tg-proxy or workers.dev)
        ingested_query = '''
            SELECT COUNT(*) as count FROM episodes 
            WHERE "episodeUrl" LIKE '%tg-proxy%' OR "episodeUrl" LIKE '%workers.dev%'
        '''
        ingested_eps = await database.fetch_one(ingested_query)
        ingested_eps = ingested_eps["count"] if ingested_eps else 0

        # Total Anime
        anime_count_query = 'SELECT COUNT(*) as count FROM anime_metadata'
        total_anime = await database.fetch_one(anime_count_query)
        total_anime = total_anime["count"] if total_anime else 0

        return {
            "total_anime": total_anime,
            "total_episodes": total_eps,
            "ingested_episodes": ingested_eps,
            "pending_episodes": total_eps - ingested_eps
        }
    except Exception as e:
        logger.error(f"[Prefetch] Error fetching stats: {e}")
        return {"total_anime": 0, "total_episodes": 0, "ingested_episodes": 0, "pending_episodes": 0}

async def smart_prefetch_episodes():
    """
    Finds RELEASING anime, syncs their latest episodes if missing, 
    and enqueues un-ingested episodes for Telegram uploading.
    """
    logger.info("[Prefetch] Starting Smart Pre-fetch for Ongoing Anime...")
    
    try:
        # 1. Ambil anime yang statusnya RELEASING
        query = 'SELECT "anilistId" FROM anime_metadata WHERE status = :status LIMIT 50'
        releasing_anime = await database.fetch_all(query, values={"status": "RELEASING"})
        
        if not releasing_anime:
            logger.info("[Prefetch] No releasing anime found.")
            return {"status": "success", "message": "No releasing anime found"}
            
        anime_ids = [row["anilistId"] for row in releasing_anime]
        logger.info(f"[Prefetch] Found {len(anime_ids)} releasing anime. Queueing sync tasks...")
        
        # 2. Trigger Sync untuk memperbarui daftar episode (jika ada yang baru)
        for aid in anime_ids:
            await enqueue_sync(aid)
            
        # 3. Cari episode-episode dari anime tersebut yang BELUM di-ingest ke Telegram
        # Batasi ke 50 episode terbaru agar tidak membebani QStash
        un_ingested_query = '''
            SELECT id, "anilistId", "episodeNumber", "episodeUrl", "providerId"
            FROM episodes
            WHERE "anilistId" = ANY(:anime_ids)
              AND "episodeUrl" NOT LIKE '%tg-proxy%'
              AND "episodeUrl" NOT LIKE '%workers.dev%'
            ORDER BY "created_at" DESC
            LIMIT 20
        '''
        un_ingested_eps = await database.fetch_all(un_ingested_query, values={"anime_ids": anime_ids})
        
        queued_count = len(un_ingested_eps)
        if queued_count > 0:
            await enqueue_ingest_batch()
            
        logger.info(f"[Prefetch] Successfully queued batch ingest trigger for {queued_count} episodes.")
        return {"status": "success", "queued_ingestions": queued_count, "synced_anime": len(anime_ids)}
        
    except Exception as e:
        logger.error(f"[Prefetch] Error during smart prefetch: {e}")
        return {"status": "error", "message": str(e)}