import asyncio
import os
import sys
from dotenv import load_dotenv

API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, API_DIR)

load_dotenv(os.path.join(API_DIR, ".env"))
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from db.connection import database as db
import httpx

async def process_delayed():
    if not db.is_connected:
        await db.connect()
    
    rows = await db.fetch_all('''
        SELECT id, "episodeNumber", "providerId"
        FROM episodes
        WHERE "anilistId" = 154587 AND "episodeNumber" > 1
        AND "providerId" = 'kuronime'
        AND ("episodeUrl" NOT LIKE '%tg-proxy%' AND "episodeUrl" NOT LIKE '%workers.dev%')
        ORDER BY "episodeNumber" ASC
    ''')
    
    print(f"Ditemukan {len(rows)} episode Frieren (Eps 2+) yang belum di-ingest.")
    if not rows:
        print("Semua episode sudah masuk Telegram.")
        await db.disconnect()
        return
        
    for row in rows:
        ep_num = row['episodeNumber']
        print(f"\n🚀 [{ep_num}] Memicu Ingestion untuk Frieren Episode {ep_num}...")
        
        # Prioritaskan episode ini di Database agar diproses paling pertama
        await db.execute('''
            UPDATE episodes 
            SET "updatedAt" = NOW() + interval '1 day'
            WHERE id = :id
        ''', {"id": row['id']})
        
        # Hapus kunci antrean agar HF space bisa langsung menerima request baru
        try:
            from services.cache import upstash_del
            await upstash_del("lock:ingest_batch_trigger")
        except Exception as e:
            print(f"Gagal menghapus Redis lock: {e}")
        
        # Panggil API Hugging Face untuk membangunkan proses Ingest
        async with httpx.AsyncClient(verify=False) as client:
            try:
                # Memanggil stream endpoint secara otomatis membangunkan enqueue_ingest_batch()
                res = await client.get(
                    f"https://jonyyyyyyyu-anime-scraper-api.hf.space/api/v2/stream/sources?title=frieren&ep={ep_num}&anilist_id=154587",
                    timeout=10.0
                )
                print(f"[{ep_num}] Trigger API HF Space Status: {res.status_code}")
            except Exception as e:
                print(f"[{ep_num}] Trigger API Timeout (Normal karena background processing jalan): {e}")
                
        print(f"[{ep_num}] Menunggu 15 menit (900 detik) untuk memberi waktu Server HF memotong video...")
        
        # Delay 15 Menit
        for i in range(15):
            print(f"   ... Menunggu {15-i} menit tersisa ...")
            await asyncio.sleep(60)
        
    await db.disconnect()
    print("\n✅ Seluruh antrean Frieren S1 telah selesai disuntikkan ke Hugging Face Space!")

if __name__ == "__main__":
    asyncio.run(process_delayed())