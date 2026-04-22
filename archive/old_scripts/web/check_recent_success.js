const postgres = require('postgres');
require('dotenv').config({ path: '.env.local' });

const sql = postgres(process.env.DATABASE_URL);

async function checkRecentSuccess() {
  console.log("🕵️ Mengecek episode terbaru yang berhasil masuk Telegram...");
  try {
    const rows = await sql`
      SELECT "anilistId", "episodeNumber", "episodeUrl", "updatedAt"
      FROM episodes 
      WHERE "episodeUrl" LIKE '%tg-proxy%'
      ORDER BY "updatedAt" DESC
      LIMIT 5
    `;

    if (rows.length > 0) {
      console.log("\n🎉 BERIKUT DAFTAR VIDEO DI TELEGRAM ANDA:");
      rows.forEach(ep => {
        console.log(`- Anime ID: ${ep.anilistId} | Ep: ${ep.episodeNumber}`);
        console.log(`  🔗 Link: ${ep.episodeUrl.substring(0, 50)}...`);
        console.log(`  🕒 Diupdate: ${ep.updatedAt}`);
      });
    } else {
      console.log("❓ Belum ada link Telegram di database.");
    }
  } catch (err) {
    console.error("🚨 Error Query:", err.message);
  } finally {
    await sql.end();
  }
}

checkRecentSuccess();
