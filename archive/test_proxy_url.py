import asyncio
import os
from dotenv import load_dotenv

load_dotenv("apps/api/.env")
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from databases import Database

async def get_url():
    db = Database(db_url)
    await db.connect()
    query = """
        SELECT "episodeUrl" 
        FROM episodes 
        WHERE "episodeUrl" LIKE '%tg-proxy.moehamadhkl.workers.dev%' 
        LIMIT 1
    """
    row = await db.fetch_one(query)
    if row:
        print(row["episodeUrl"])
    else:
        print("NO_URL_FOUND")
    await db.disconnect()

asyncio.run(get_url())
