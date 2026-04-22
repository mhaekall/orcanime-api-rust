import os
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return
    # Convert sqlalchemy url if needed
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    
    conn = await asyncpg.connect(db_url)
    try:
        tables_to_drop = [
            "comments",
            "comment_reactions",
            "follows",
            "notifications",
            "watch_events",
            "collections",
            "activity_feed",
            "episode_likes",
            "users"
        ]
        for table in tables_to_drop:
            try:
                await conn.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
                print(f"Dropped {table}")
            except Exception as e:
                print(f"Failed to drop {table}: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
