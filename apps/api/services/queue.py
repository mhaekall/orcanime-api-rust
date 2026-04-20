import os
import httpx
import time
from services.config import QSTASH_TOKEN

class QStashPublisher:
    """Lightweight QStash REST publisher."""
    
    @staticmethod
    async def publish_sync_task(anilist_id: int):
        if not QSTASH_TOKEN:
            print(f"[QStash] Token missing, cannot queue sync for {anilist_id}")
            return
            
        # Target webhook URL is dynamic based on environment.
        # In production, it's the HuggingFace URL or custom domain.
        target_url = os.getenv("API_PUBLIC_URL", "https://jonyyyyyyyu-anime-scraper-api.hf.space")
        target_url = f"{target_url.rstrip('/')}/api/v2/webhook/sync"
        qstash_url = os.getenv("QSTASH_URL", "https://qstash.upstash.io").rstrip("/")
        
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(
                    f"{qstash_url}/v2/publish/" + target_url,
                    headers={
                        "Authorization": f"Bearer {QSTASH_TOKEN}",
                        "Content-Type": "application/json",
                        "Upstash-Retries": "5",  # Higher retries for HF Space cold starts
                    },
                    json={"anilistId": anilist_id}
                )
                if res.status_code >= 400:
                    print(f"[QStash] Publish Failed: {res.status_code} - {res.text}")
                else:
                    print(f"[QStash] Queued sync for anilistId={anilist_id} successfully.")
            except Exception as e:
                print(f"[QStash] Exception publishing to QStash: {e}")

    @staticmethod
    async def publish_ingest_task(episode_id: int, anilist_id: int, provider_id: str, episode_number: float, direct_url: str, delay: str = None):
        if not QSTASH_TOKEN:
            print(f"[QStash] Token missing, cannot queue ingest for Ep {episode_number}")
            return

        # --- DEDUPLICATION: Prevent redundant tasks using Redis lock ---
        from services.cache import upstash_set
        lock_key = f"ingest:{anilist_id}:{episode_number}"
        
        # nx=True means "only set if the key does not already exist" (Distributed Lock)
        # We lock for 30 minutes (1800s) to cover the typical ingestion duration
        is_locked = await upstash_set(lock_key, {
            "status": "processing",
            "started_at": int(time.time()),
            "provider": provider_id
        }, ex=1800, nx=True)
        
        if not is_locked:
            print(f"[QStash] Ingest already queued/in-progress for {anilist_id} Ep {episode_number}. Skipping deduplicate.")
            return
            
        target_url = os.getenv("API_PUBLIC_URL", "https://jonyyyyyyyu-anime-scraper-api.hf.space")
        target_url = f"{target_url.rstrip('/')}/api/v2/webhook/ingest"
        qstash_url = os.getenv("QSTASH_URL", "https://qstash.upstash.io").rstrip("/")
        
        headers = {
            "Authorization": f"Bearer {QSTASH_TOKEN}",
            "Content-Type": "application/json",
            "Upstash-Retries": "5", 
        }
        if delay:
            headers["Upstash-Delay"] = delay
            
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(
                    f"{qstash_url}/v2/publish/" + target_url,
                    headers=headers,
                    json={
                        "episode_id": episode_id,
                        "anilist_id": anilist_id,
                        "provider_id": provider_id,
                        "episode_number": episode_number,
                        "direct_url": direct_url
                    }
                )
                if res.status_code >= 400:
                    print(f"[QStash] Ingest Publish Failed: {res.status_code} - {res.text}")
                else:
                    delay_msg = f" with {delay} delay" if delay else ""
                    print(f"[QStash] Queued Ingestion for Ep {episode_number} successfully{delay_msg}.")
            except Exception as e:
                print(f"[QStash] Exception publishing ingest to QStash: {e}")

    @staticmethod
    async def publish_ingest_batch_task():
        if not QSTASH_TOKEN:
            print(f"[QStash] Token missing, cannot queue batch ingest")
            return

        # Deduplication: Prevent redundant batch triggers within 15 minutes (900s)
        from services.cache import upstash_set
        lock_key = "lock:ingest_batch_trigger"
        
        is_locked = await upstash_set(lock_key, {
            "status": "queued",
            "started_at": int(time.time()),
        }, ex=900, nx=True)
        
        if not is_locked:
            print(f"[QStash] Batch ingest trigger already queued. Skipping deduplicate.")
            return
            
        target_url = os.getenv("API_PUBLIC_URL", "https://jonyyyyyyyu-anime-scraper-api.hf.space")
        target_url = f"{target_url.rstrip('/')}/api/v2/webhook/ingest-batch"
        qstash_url = os.getenv("QSTASH_URL", "https://qstash.upstash.io").rstrip("/")
        
        headers = {
            "Authorization": f"Bearer {QSTASH_TOKEN}",
            "Content-Type": "application/json",
            "Upstash-Retries": "5", 
        }
            
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(
                    f"{qstash_url}/v2/publish/" + target_url,
                    headers=headers,
                    json={"action": "run_batch"}
                )
                if res.status_code >= 400:
                    print(f"[QStash] Ingest Batch Publish Failed: {res.status_code} - {res.text}")
                else:
                    print(f"[QStash] Queued Batch Ingestion successfully.")
            except Exception as e:
                print(f"[QStash] Exception publishing batch ingest to QStash: {e}")

enqueue_sync = QStashPublisher.publish_sync_task
enqueue_ingest = QStashPublisher.publish_ingest_task
enqueue_ingest_batch = QStashPublisher.publish_ingest_batch_task