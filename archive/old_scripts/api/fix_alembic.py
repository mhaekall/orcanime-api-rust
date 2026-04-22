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
        await conn.execute("UPDATE alembic_version SET version_num = '652f4316b654'")
        print("Updated alembic_version")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
