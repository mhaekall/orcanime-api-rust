const postgres = require('postgres');
require('dotenv').config({ path: '.env.local' });

async function check() {
  const sql = postgres(process.env.DATABASE_URL);
  try {
    const rows = await sql`SELECT "episodeUrl" FROM episodes WHERE "anilistId" = 182205 AND "episodeNumber" = 2`;
    console.log(JSON.stringify(rows, null, 2));
  } catch (e) {
    console.error(e);
  } finally {
    await sql.end();
  }
}
check();