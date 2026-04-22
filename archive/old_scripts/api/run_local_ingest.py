import asyncio
import os
import sys

# Jalankan skrip ini dari dalam folder apps/api/
# Agar services lokal apps/api terpanggil, tapi untuk ingestion kita butuh root services.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(".env")

db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from databases import Database
from services.stream_cache import stream_cache

import importlib.util
spec = importlib.util.spec_from_file_location("ingestion_main", os.path.join(ROOT_DIR, "services", "ingestion", "main.py"))
ingestion_main = importlib.util.module_from_spec(spec)
sys.modules["services.ingestion.main"] = ingestion_main
# Also need to provide services.ingestion.core
import services
services.__path__.append(os.path.join(ROOT_DIR, "services"))

from services.ingestion.main import IngestionEngine
from services.providers import kuronime_provider, extractor

async def force_ingest():
    db = Database(db_url)
    await db.connect()
    
    # Query Database
    row = await db.fetch_one('SELECT id, "episodeNumber", "episodeUrl", "providerId" FROM episodes WHERE "anilistId" = 101280 AND "episodeNumber" = 1.0 LIMIT 1')
    
    if not row:
        print("Episode not found in DB")
        await db.disconnect()
        return
        
    ep_id = row['id']
    aid = 101280
    ep_num = 1.0
    
    print(f"\n--- Memproses {aid} Ep {ep_num} ---")
    
    # Get live URL from Kuronime to ensure the IP matches
    target_ep_url = "https://kuronime.sbs/nonton-tensei-shitara-slime-datta-ken-episode-1/"
    sources = await kuronime_provider.get_episode_sources(target_ep_url)
    
    direct_url = None
    src_list = sources if isinstance(sources, list) else sources.get('sources', [])
    for s in src_list:
        if s.get('quality') == '720p':
            url_to_extract = s.get('url') or s.get('resolved')
            if not url_to_extract: continue
            resolved = await extractor.extract_raw_video(url_to_extract)
            if resolved.endswith(('.mp4', '.m3u8')) or 'videoplayback' in resolved:
                direct_url = resolved
                break
                
    if not direct_url:
        print("Failed to get live 720p URL")
        await db.disconnect()
        return

    print(f"Direct URL found: {direct_url[:50]}...")
    
    engine = IngestionEngine()
    success = await engine.process_episode(
        episode_id=ep_id,
        anilist_id=aid,
        provider_id="kuronime",
        episode_number=ep_num,
        direct_video_url=direct_url
    )
    print(f"Ingest Result {aid} Ep {ep_num}: {success}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(force_ingest())
