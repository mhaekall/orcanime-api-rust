const postgres = require('postgres');
require('dotenv').config({ path: '.env.local' });

const sql = postgres(process.env.DATABASE_URL);

async function monitor() {
  console.log("🕵️ X-RAY MONITOR AKTIF: Mengintip Database Neon untuk Wistoria (182300) Episode 1...");
  
  const startTime = Date.now();
  const maxDuration = 10 * 60 * 1000; // 10 menit
  
  while (Date.now() - startTime < maxDuration) {
    try {
      const rows = await sql`
        SELECT "episodeUrl", "updatedAt"
        FROM episodes 
        WHERE "anilistId" = 182300 AND "episodeNumber" = 1
        LIMIT 1
      `;
      
      const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
      
      if (rows.length === 0) {
        console.log(`🕒 [${elapsedSec}s] Wistoria belum terdaftar di tabel episodes. (Mungkin masih download file mentah di Hugging Face)`);
      } else {
        const url = rows[0].episodeUrl;
        
        if (!url) {
             console.log(`🕒 [${elapsedSec}s] Baris Wistoria ditemukan, namun URL masih KOSONG. (Sedang proses Slicing/Upload...)`);
        } else if (url.includes("tg-proxy")) {
             console.log(`\n🎉 BINGO! VIDEO TERKIRIM KE TELEGRAM!`);
             console.log(`🔗 Link Akhir: ${url}`);
             console.log(`⏲️ Total waktu pemrosesan: ${elapsedSec} detik.`);
             process.exit(0);
        } else {
             console.log(`🕒 [${elapsedSec}s] Link terdeteksi: ${url.substring(0, 30)}... (Ini masih link sumber/mentah. Sedang dikonversi ke Telegram di latar belakang)`);
        }
      }
    } catch (err) {
      console.error(`🚨 Error Database: ${err.message}`);
    }
    
    // Tunggu 15 detik sebelum mengintip lagi
    await new Promise(resolve => setTimeout(resolve, 15000));
  }
  
  console.log("⚠️ Waktu pemantauan habis (10 Menit). Proses mungkin masih berlanjut di Cloud.");
  process.exit(1);
}

monitor();
