import asyncio
import os
import sys

root_dir = os.getcwd()
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

async def main():
    await test_db.connect()
    # Tensura S1 Ep 23
    aid = 101280
    ep_num = 23.0
    direct_url = "https://pixeldrain.com/api/file/rYUUkSdm"
    
    row = await test_db.fetch_one('SELECT id FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep LIMIT 1', values={"aid": aid, "ep": ep_num})
    
    engine = IngestionEngine()
    print("🚀 Memulai Ingest Ep 23 Lokal dengan dukungan Subtitle...")
    
    # Force release lock
    from apps.api.services.cache import upstash_del
    await upstash_del(f"ingest:{aid}:{ep_num}")
    
    success = await engine.process_episode(
        episode_id=row['id'],
        anilist_id=aid,
        provider_id="oploverz",
        episode_number=ep_num,
        direct_video_url=direct_url
    )
    print(f"Hasil Akhir: {success}")
    await test_db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
