import asyncio
import os
import sys
import json

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
import apps.api.db.connection as db_conn
db_conn.database = test_db

from apps.api.services.ingestion.main import IngestionEngine

async def run_final():
    await test_db.connect()
    from apps.api.services.cache import upstash_del
    
    aid = 101280
    engine = IngestionEngine()
    
    eps = [
        (23.0, "https://pixeldrain.com/api/file/rYUUkSdm"),
        (24.0, "https://pixeldrain.com/api/file/v5ohkSCM")
    ]
    
    for ep_num, direct_url in eps:
        print(f"\n🚀 [LOCAL RESCUE] Memulai Ingestion untuk Ep {ep_num}...")
        
        # Clear locks first
        await upstash_del(f"ingest:{aid}:{ep_num}")
        
        row = await test_db.fetch_one('SELECT id FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep LIMIT 1', values={"aid": aid, "ep": ep_num})
        if not row:
            print(f"Row for Ep {ep_num} missing, creating...")
            url = f"https://o.oploverz.ltd/series/tensei-shitara-slime-datta-ken-s1/episode/{int(ep_num)}/"
            await test_db.execute(
                'INSERT INTO episodes ("anilistId", "providerId", "episodeNumber", "episodeTitle", "episodeUrl", "updatedAt") VALUES (101280, \'oploverz\', :ep, :title, :url, NOW())',
                values={"ep": ep_num, "title": f"Episode {int(ep_num)}", "url": url}
            )
            row = await test_db.fetch_one('SELECT id FROM episodes WHERE "anilistId" = 101280 AND "episodeNumber" = :ep LIMIT 1', values={"ep": ep_num})

        try:
            success = await engine.process_episode(
                episode_id=row['id'],
                anilist_id=aid,
                provider_id="oploverz",
                episode_number=ep_num,
                direct_video_url=direct_url
            )
            print(f"✨ Hasil Ingest Lokal Ep {ep_num}: {success}")
        except Exception as e:
            print(f"❌ Error Ingesting Ep {ep_num}: {e}")

    print("\nSELURUH EPISODE TENSURA S1 SELESAI TUNTAS!")
    await test_db.disconnect()

if __name__ == "__main__":
    asyncio.run(run_final())
