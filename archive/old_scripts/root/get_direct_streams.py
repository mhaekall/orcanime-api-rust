import asyncio
import json
from apps.api.db.connection import database
from sqlalchemy import text

async def get_direct_streams():
    await database.connect()
    try:
        # Fetch all video cache entries joined with episodes and anime metadata
        query = """
            SELECT vc.payload, e."episodeNumber", a."cleanTitle"
            FROM video_cache vc
            JOIN episodes e ON vc."episodeUrl" = e."episodeUrl"
            JOIN anime_metadata a ON e."anilistId" = a."anilistId"
        """
        rows = await database.fetch_all(text(query))
        
        direct_streams = []
        
        for row in rows:
            payload_str = row['payload']
            try:
                payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                if not payload: continue
                
                sources = payload.get('sources', [])
                
                has_direct = False
                
                for s in sources:
                    url = s.get('url', '')
                    # Check if it's a direct stream (not a proxy or telegram link)
                    if 'tg' not in url.lower() and 'proxy' not in url.lower() and 't.me' not in url.lower():
                        has_direct = True
                        break
                        
                if has_direct:
                    direct_streams.append({
                        "title": row["cleanTitle"],
                        "episode": row["episodeNumber"]
                    })
            except Exception as e:
                pass
                
        # Group by title
        anime_map = {}
        for ds in direct_streams:
            title = ds["title"]
            ep = ds["episode"]
            if title not in anime_map:
                anime_map[title] = []
            # Avoid duplicates
            if ep not in anime_map[title]:
                anime_map[title].append(ep)
            
        print(f"Total Anime with Direct Streams: {len(anime_map)}")
        print(f"Total Episodes with Direct Streams: {sum(len(eps) for eps in anime_map.values())}")
        print("---")
        for title, eps in sorted(anime_map.items()):
            eps.sort()
            ep_str = ", ".join([str(e) if e % 1 != 0 else str(int(e)) for e in eps])
            print(f"- {title}: Episode {ep_str}")
            
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(get_direct_streams())
