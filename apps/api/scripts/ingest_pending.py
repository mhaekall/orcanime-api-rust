import asyncio
import os
import sys
import argparse
import time
from dotenv import load_dotenv

API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, API_DIR)

load_dotenv(os.path.join(API_DIR, ".env"))

from db.connection import database as db
from services.ingestion.main import IngestionEngine
from services.stream_cache import get_cached_stream

async def ingest_pending(limit: int = 50):
    # Mengabaikan limit dari parameter lama agar kita bisa memproses lebih banyak secara batch
    limit = 50 
    
    print(f"🚀 Memulai HF Space Worker Ingestion: Mencari maksimal {limit} episode tertunda...")
    
    should_disconnect = False
    if not db.is_connected:
        await db.connect()
        should_disconnect = True
        
    # Cari episode yang URL-nya belum tg-proxy
    # Diurutkan berdasarkan anilistId (Anime yang sama) lalu episodeNumber secara berurutan
    query = """
        SELECT id, "anilistId", "episodeNumber", "episodeUrl" 
        FROM episodes 
        WHERE "episodeUrl" NOT LIKE '%tg-proxy%' 
        AND "episodeUrl" NOT LIKE '%workers.dev%'
        AND "episodeUrl" LIKE 'http%'
        ORDER BY "anilistId" ASC, "episodeNumber" ASC
        LIMIT :limit
    """
    rows = await db.fetch_all(query, values={"limit": limit})
    
    if not rows:
        print("✅ Tidak ada episode yang perlu di-ingest. Semua up-to-date!")
        if should_disconnect:
            await db.disconnect()
        return

    print(f"Ditemukan {len(rows)} episode antrean. Memproses SATU PER SATU secara berurutan (Hard Stitch)...")
    print("-" * 50)

    engine = IngestionEngine()
    
    for row in rows:
        ep_id = row['id']
        aid = row['anilistId']
        ep_num = float(row['episodeNumber'])
        
        anime_row = await db.fetch_one('SELECT "cleanTitle" FROM anime_metadata WHERE "anilistId" = :aid', {"aid": aid})
        title = anime_row["cleanTitle"] if anime_row else f"Anime {aid}"
        
        print(f"\n📺 [{time.strftime('%H:%M:%S')}] Memproses Ingest: {title} - Episode {ep_num}")
        
        sources_response = await get_cached_stream(aid, ep_num)
        if sources_response and "sources" in sources_response and len(sources_response["sources"]) > 0:
            direct_url = ""
            provider_id = "unknown"
            
            # Prioritize 720p
            for s in sources_response["sources"]:
                if s.get("quality") == "720p" and s.get("type") in ["mp4", "direct", "hls", "mp4 (direct)", "hls (direct)"]:
                    direct_url = s.get("raw_url") or s.get("url", "")
                    provider_id = s.get("source", "unknown")
                    break

            # Fallback to first available direct stream if 720p not found
            if not direct_url:
                for s in sources_response["sources"]:
                    if s.get("type") in ["mp4", "direct", "hls", "mp4 (direct)", "hls (direct)"]:
                        direct_url = s.get("raw_url") or s.get("url", "")
                        provider_id = s.get("source", "unknown")
                        break

            if not direct_url:
                print(f"⚠️ Melewati Ep {ep_num} karena tidak memiliki Direct Stream murni (hanya ada Iframe).")
                continue

            if "tg-proxy" in direct_url or "workers.dev" in direct_url:
                print(f"✅ Sudah ter-ingest (Proxy URL Ditemukan).")
                continue

            print(f"🔗 Direct URL: {direct_url[:50]}... [{provider_id}]")
            print(f"⏳ Mengeksekusi Ingestion Engine (Download -> Slice -> Upload Telegram)...")
            
            # Hard Stitch (Tunggu sampai selesai 100% baru lanjut ke episode berikutnya)
            success = await engine.process_episode(
                episode_id=ep_id,
                anilist_id=aid,
                provider_id=provider_id,
                episode_number=ep_num,
                direct_video_url=direct_url
            )
            
            if success:
                print(f"🎉 SUKSES: Episode {ep_num} berhasil disimpan permanen ke Telegram!")
            else:
                print(f"❌ GAGAL: Terjadi kesalahan saat memproses episode {ep_num}.")
        else:
            print(f"❌ Sumber mentah tidak ditemukan untuk {aid} Ep {ep_num}")

        # Jeda pendinginan agar server/Telegram API tidak overload
        print("⏳ Jeda pendinginan 10 detik sebelum episode selanjutnya...")
        await asyncio.sleep(10)

    print("-" * 50)
    print("🎉 Seluruh proses antrean batch selesai!")

    if should_disconnect:
        await db.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest pending episodes")
    parser.add_argument("--limit", type=int, default=50, help="Max episodes to process")
    args = parser.parse_args()
    
    asyncio.run(ingest_pending(args.limit))