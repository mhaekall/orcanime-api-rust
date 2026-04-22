import asyncio, os, sys
sys.path.append(os.path.join(os.getcwd(), 'apps', 'api'))
from databases import Database
from dotenv import load_dotenv
load_dotenv("apps/api/.env")
db_url = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+asyncpg://")

async def main():
    db = Database(db_url)
    await db.connect()
    
    # Check if 24 is already there, if so get ID
    row = await db.fetch_one('SELECT id FROM episodes WHERE "anilistId" = 101280 AND "episodeNumber" = 24.0 LIMIT 1')
    if not row:
        print("Creating row for Ep 24...")
        await db.execute('INSERT INTO episodes ("anilistId", "providerId", "episodeNumber", "episodeTitle", "episodeUrl", "updatedAt") VALUES (101280, \'oploverz\', 24.0, \'Episode 24\', \'https://o.oploverz.ltd/series/tensei-shitara-slime-datta-ken-s1/episode/24/\', NOW())')
        row = await db.fetch_one('SELECT id FROM episodes WHERE "anilistId" = 101280 AND "episodeNumber" = 24.0 LIMIT 1')
    
    from apps.api.services.ingestion.main import IngestionEngine
    engine = IngestionEngine()
    
    from services.cache import upstash_del
    await upstash_del("ingest:101280:24.0")
    
    print("🚀 Memulai Final Ingestion: Ep 24 (Single Subtitle Mode)...")
    success = await engine.process_episode(
        episode_id=row['id'],
        anilist_id=101280,
        provider_id="oploverz",
        episode_number=24.0,
        direct_video_url="https://pixeldrain.com/api/file/v5ohkSCM"
    )
    print(f"Hasil: {success}")
    await db.disconnect()

asyncio.run(main())
