const postgres = require('postgres');
require('dotenv').config({ path: '.env.local' });

async function monitor() {
  const sql = postgres(process.env.DATABASE_URL);
  console.log("🕵️ Mengecek status video Solo Leveling di Neon DB...");

  try {
    const rows = await sql`
      SELECT "anilistId", "episodeNumber", "episodeUrl", "updatedAt"
      FROM episodes 
      WHERE "anilistId" = 151801 OR "anilistId" = 182300
      ORDER BY "updatedAt" DESC
      LIMIT 10
    `;

    if (rows.length > 0) {
      rows.forEach(ep => {
        console.log(`📊 Ep ${ep.episodeNumber}: ${ep.episodeUrl ? '✅ DONE (' + ep.episodeUrl.substring(0, 30) + '...)' : '⏳ PROCESSING'}`);
      });
      
      const isDone = rows.some(ep => ep.episodeNumber == 1 && ep.episodeUrl);
      if (isDone) {
        console.log("\n🎉 SUCCESS! Potongan video pertama sudah mendarat di database.");
        process.exit(0);
      }
    } else {
      console.log("❓ Belum ada data episode untuk anime ini.");
    }
  } catch (err) {
    console.error("🚨 Error Query:", err.message);
  } finally {
    await sql.end();
  }
}

monitor();
