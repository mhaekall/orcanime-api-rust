import asyncio
import os
import sys

root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root_dir)
sys.path.append(os.path.join(root_dir, 'apps', 'api'))

from databases import Database
from dotenv import load_dotenv

load_dotenv("apps/api/.env")
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

test_db = Database(db_url)

async def queue_ep23_24():
    await test_db.connect()
    from apps.api.services.queue import enqueue_ingest
    from apps.api.services.cache import upstash_del
    
    aid = 101280
    provider_id = "oploverz"
    
    # From tensura_s1_batch.json
    eps = [
        (23.0, "https://pixeldrain.com/api/file/rYUUkSdm", "0m"),
        (24.0, "https://pixeldrain.com/api/file/v5ohkSCM", "10m")
    ]
    
    for ep_num, direct_url, delay in eps:
        # 1. Bersihkan sisa lock atau progress lama di Redis agar bisa di-queue ulang dengan mulus
        await upstash_del(f"ingest:{aid}:{ep_num}")
        await upstash_del(f"ingest_progress:{aid}:{ep_num}")
        
        # 2. Pastikan row ada di DB
        row = await test_db.fetch_one('SELECT id FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep LIMIT 1', values={"aid": aid, "ep": ep_num})
        if not row:
            url = f"https://o.oploverz.ltd/series/tensei-shitara-slime-datta-ken-s1/episode/{int(ep_num)}/"
            await test_db.execute(
                'INSERT INTO episodes ("anilistId", "providerId", "episodeNumber", "episodeTitle", "episodeUrl", "updatedAt") VALUES (:aid, :pid, :ep, :title, :url, NOW())',
                values={"aid": aid, "pid": provider_id, "ep": ep_num, "title": f"Episode {int(ep_num)}", "url": url}
            )
            row = await test_db.fetch_one('SELECT id FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep LIMIT 1', values={"ep": ep_num})
            
        ep_id = row['id']
        
        # 3. Tembak ke QStash Queue
        print(f"🚀 Mendorong Antrean Ingestion untuk Ep {ep_num} (Delay: {delay})...")
        try:
            await enqueue_ingest(
                episode_id=ep_id,
                anilist_id=aid,
                provider_id=provider_id,
                episode_number=ep_num,
                direct_url=direct_url,
                delay=delay
            )
            print(f"✅ Ep {ep_num} sukses didorong ke antrean!")
        except Exception as e:
            print(f"❌ Gagal antre Ep {ep_num}: {e}")

    print("\nEksekusi antrean Ep 23 dan 24 SELESAI!")
    await test_db.disconnect()

if __name__ == "__main__":
    asyncio.run(queue_ep23_24())
