const postgres = require('postgres');
require('dotenv').config({ path: '.env.local' });

async function run() {
  const sql = postgres(process.env.DATABASE_URL);
  try {
    const rows = await sql`SELECT id, "providerId", "episodeUrl" FROM episodes WHERE "anilistId" = 180745 AND "episodeNumber" = 5 LIMIT 1`;
    console.log(JSON.stringify(rows[0]));
  } catch (err) {
    console.error(err);
  } finally {
    await sql.end();
  }
}
run();