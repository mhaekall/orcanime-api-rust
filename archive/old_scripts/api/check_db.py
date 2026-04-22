import os
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def main():
    db_url = os.getenv("DATABASE_URL")
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    try:
        exists = await conn.fetchval("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'collections')")
        print(f"Collections exists: {exists}")
        
        # Also check popularity column
        pop_exists = await conn.fetchval("SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'anime_metadata' AND column_name = 'popularity')")
        print(f"Popularity exists: {pop_exists}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
