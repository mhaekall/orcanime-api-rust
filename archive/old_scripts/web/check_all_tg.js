const postgres = require('postgres');
require('dotenv').config({ path: '.env.local' });

async function checkAll() {
  const sql = postgres(process.env.DATABASE_URL);
  try {
    const rows = await sql`
      SELECT e."anilistId", e."episodeNumber", e."episodeUrl", m."cleanTitle"
      FROM episodes e
      LEFT JOIN anime_metadata m ON e."anilistId" = m."anilistId"
      WHERE e."episodeUrl" LIKE '%tg-proxy%'
      ORDER BY e."updatedAt" DESC
    `;

    console.log(JSON.stringify(rows, null, 2));
  } catch (err) {
    console.error("🚨 Error Query:", err.message);
  } finally {
    await sql.end();
  }
}

checkAll();
