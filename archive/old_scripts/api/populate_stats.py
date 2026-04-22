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
        # Set popularity and trending based on score so the homepage is populated
        await conn.execute("""
            UPDATE anime_metadata 
            SET popularity = score * 10, trending = score * 2 
            WHERE popularity IS NULL OR popularity = 0
        """)
        print("Updated popularity and trending values")
        
        # Verify counts
        count = await conn.fetchval("SELECT COUNT(*) FROM anime_metadata WHERE popularity > 0")
        print(f"Anime with popularity > 0: {count}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
