import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath("apps/api"))

from db.connection import database

async def run():
    await database.connect()
    # Find Tensura S2 Ep 1 Kuronime
    await database.execute("""
        UPDATE episodes 
        SET "episodeUrl" = 'https://kuronime.sbs/nonton-tensei-shitara-slime-datta-ken-season-2-episode-1/' 
        WHERE "anilistId" = 108511 AND "episodeNumber" = 1 AND "providerId" = 'kuronime'
    """)
    print("URL reverted!")
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(run())
