import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("apps/api"))

from db.connection import database

async def run():
    await database.connect()
    rows = await database.fetch_all('SELECT id, "providerId", "episodeUrl" FROM episodes WHERE "anilistId" = 108511 AND "episodeNumber" = 1')
    for r in rows:
        print(dict(r))
        if 'tg-proxy' in r['episodeUrl']:
            await database.execute(
                'UPDATE episodes SET "episodeUrl" = :url WHERE id = :id',
                values={"url": "https://kuronime.sbs/nonton-tensei-shitara-slime-datta-ken-season-2-episode-1/", "id": r['id']}
            )
            print(f"Reverted tg-proxy url for ID {r['id']}")
            
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(run())
