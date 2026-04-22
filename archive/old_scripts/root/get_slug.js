const postgres = require('postgres');
require('dotenv').config({ path: '.env' });

const sql = postgres(process.env.DATABASE_URL);

async function getSlugs() {
  try {
    const result = await sql`SELECT anime_slug FROM anime_mappings LIMIT 1`;
    console.log(JSON.stringify(result));
    process.exit(0);
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
}

getSlugs();
