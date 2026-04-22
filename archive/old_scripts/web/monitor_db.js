const postgres = require('postgres');
require('dotenv').config({ path: '.env.local' });

const sql = postgres(process.env.DATABASE_URL);
const anilistId = parseInt(process.argv[2]);
const episodeNumber = parseInt(process.argv[3]);

if (!anilistId || !episodeNumber) {
  console.error("Gunakan: node monitor_db.js <anilistId> <episode>");
  process.exit(1);
}

async function monitor() {
  console.log(`🕵️ X-RAY AKTIF: Mengintip Anime ID ${anilistId} Episode ${episodeNumber}...`);
  
  const startTime = Date.now();
  const maxDuration = 10 * 60 * 1000; // 10 menit
  
  while (Date.now() - startTime < maxDuration) {
    try {
      const rows = await sql`
        SELECT "episodeUrl", "updatedAt"
        FROM episodes 
        WHERE "anilistId" = ${anilistId} AND "episodeNumber" = ${episodeNumber}
        LIMIT 1
      `;
      
      const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
      
      if (rows.length === 0) {
        console.log(`🕒 [${elapsedSec}s] Belum terdaftar di DB. (Mencari sumber/Menunggu QStash)`);
      } else {
        const url = rows[0].episodeUrl;
        
        if (!url) {
             console.log(`🕒 [${elapsedSec}s] Baris ditemukan, URL kosong. (Proses Slicing/Upload...)`);
        } else if (url.includes("tg-proxy")) {
             console.log(`\n🎉 BINGO! VIDEO TERKIRIM KE TELEGRAM!`);
             console.log(`🔗 Link Akhir: ${url}`);
             console.log(`⏲️ Total waktu dari DB: ${elapsedSec} detik.`);
             process.exit(0);
        } else {
             console.log(`🕒 [${elapsedSec}s] Link mentah: ${url.substring(0, 30)}... (Sedang On-the-fly Slicing ke Telegram)`);
        }
      }
    } catch (err) {
      console.error(`🚨 Error Database: ${err.message}`);
    }
    
    await new Promise(resolve => setTimeout(resolve, 15000));
  }
  
  console.log("⚠️ Waktu habis (10 Menit).");
  process.exit(1);
}

monitor();
