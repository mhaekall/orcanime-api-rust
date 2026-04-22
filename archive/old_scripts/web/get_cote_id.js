const postgres = require('postgres');
require('dotenv').config({ path: '.env.local' });

async function run() {
  const sql = postgres(process.env.DATABASE_URL);
  try {
    const rows = await sql`SELECT DISTINCT "anilistId" FROM episodes WHERE "episodeUrl" ILIKE '%classroom%' OR "episodeUrl" ILIKE '%cote%'`;
    console.log("Found AniList IDs:", rows.map(r => r.anilistId));
  } catch (err) {
    console.error(err);
  } finally {
    await sql.end();
  }
}
run();