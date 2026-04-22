import asyncio
from apps.api.db.connection import database
from sqlalchemy import text

async def check_duplicates():
    await database.connect()
    try:
        # Check for duplicated tg-proxy URLs in episodes table
        query = """
            SELECT "episodeUrl", COUNT(*) as cnt, array_agg("anilistId") as anime_ids, array_agg("episodeNumber") as ep_nums
            FROM episodes
            WHERE "episodeUrl" LIKE '%tg-proxy%' OR "episodeUrl" LIKE '%workers.dev%'
            GROUP BY "episodeUrl"
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
        """
        duplicates = await database.fetch_all(text(query))
        
        print(f"Total unique TG proxy URLs with duplicates: {len(duplicates)}")
        if duplicates:
            print("Top 10 duplicates:")
            for d in duplicates[:10]:
                print(f"URL: {d['episodeUrl'][:50]}... | Count: {d['cnt']} | Anime IDs: {d['anime_ids']} | Eps: {d['ep_nums']}")
        else:
            print("No duplicated TG links found in episodes table.")
            
        # Let's also check Frieren Ep 2
        frieren_ep2 = await database.fetch_one(text('SELECT id, "episodeUrl" FROM episodes WHERE "anilistId" = 154587 AND "episodeNumber" = 2'))
        if frieren_ep2:
            print(f"\\nFrieren Ep 2 Current URL: {frieren_ep2['episodeUrl']}")
            
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(check_duplicates())
