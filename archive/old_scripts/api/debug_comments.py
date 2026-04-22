import asyncio
from db.connection import database
from db.models import comments
from sqlalchemy import select

async def check():
    await database.connect()
    rows = await database.fetch_all(select(comments).order_by(comments.c.created_at.desc()).limit(20))
    print(f"Total Comments Found: {len(rows)}")
    for r in rows:
        d = dict(r)
        print(f"ID: {d['id']}, User: {d['user_id']}, Text: {d['text']}, Episode: {d['episodeNumber']}, Parent: {d['parent_id']}")
    await database.disconnect()

if __name__ == '__main__':
    asyncio.run(check())
