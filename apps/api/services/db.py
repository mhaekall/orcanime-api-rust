import json
from db.connection import database
from db.models import anime_mappings, anime_metadata

async def upsert_anime_db(anilist_data, provider_id: str, provider_slug: str):
    if not anilist_data or not anilist_data.get('anilistId'):
        return
        
    # BLOKIR OTOMATIS GENRE HENTAI
    genres = anilist_data.get('genres', [])
    if isinstance(genres, list):
        if any('hentai' in str(g).lower() for g in genres):
            print(f"[BLOCKED] Mengabaikan anime Hentai: {anilist_data.get('cleanTitle', '')} ({provider_id})")
            return
            
    try:
        # ── METADATA RECONCILIATION LOGIC ──
        # If AniList says 'NOT_YET_RELEASED', but we know we are scraping episodes for it, 
        # forcefully reconcile the status to 'RELEASING' to match reality.
        final_status = anilist_data.get('status', '')
        if final_status == 'NOT_YET_RELEASED':
            # Fast check if episodes exist for this anilistId
            eps = await database.fetch_val(
                'SELECT COUNT(*) FROM episodes WHERE "anilistId" = :aid',
                values={'aid': anilist_data.get('anilistId')}
            )
            if eps and eps > 0:
                final_status = 'RELEASING'
                
        query_meta = """
            INSERT INTO anime_metadata (
                "anilistId", "cleanTitle", "nativeTitle", "coverImage", "bannerImage", 
                "synopsis", "score", "popularity", "trending", "status", 
                "totalEpisodes", "season", "year", "studios", "genres", 
                "recommendations", "nextAiringEpisode", "updatedAt"
            )
            VALUES (
                :anilistId, :cleanTitle, :nativeTitle, :coverImage, :bannerImage, 
                :synopsis, :score, :popularity, :trending, :status, 
                :totalEpisodes, :season, :year, :studios, :genres, 
                :recommendations, :nextAiringEpisode, NOW()
            )
            ON CONFLICT ("anilistId") DO UPDATE SET
                "cleanTitle" = EXCLUDED."cleanTitle",
                "nativeTitle" = EXCLUDED."nativeTitle",
                "coverImage" = EXCLUDED."coverImage",
                "bannerImage" = EXCLUDED."bannerImage",
                "synopsis" = EXCLUDED."synopsis",
                "score" = EXCLUDED."score",
                "popularity" = EXCLUDED."popularity",
                "trending" = EXCLUDED."trending",
                "status" = EXCLUDED."status",
                "totalEpisodes" = EXCLUDED."totalEpisodes",
                "season" = EXCLUDED."season",
                "year" = EXCLUDED."year",
                "studios" = EXCLUDED."studios",
                "genres" = EXCLUDED."genres",
                "recommendations" = EXCLUDED."recommendations",
                "nextAiringEpisode" = EXCLUDED."nextAiringEpisode",
                "updatedAt" = NOW()
        """
        await database.execute(query=query_meta, values={
            'anilistId': anilist_data.get('anilistId'),
            'cleanTitle': anilist_data.get('cleanTitle', ''),
            'nativeTitle': anilist_data.get('nativeTitle', ''),
            'coverImage': anilist_data.get('hdImage', ''),
            'bannerImage': anilist_data.get('banner', ''),
            'synopsis': anilist_data.get('description', ''),
            'score': anilist_data.get('score'),
            'popularity': anilist_data.get('popularity', 0),
            'trending': anilist_data.get('trending', 0),
            'status': final_status,
            'totalEpisodes': anilist_data.get('totalEpisodes'),
            'season': anilist_data.get('season', ''),
            'year': anilist_data.get('year'),
            'studios': json.dumps(anilist_data.get('studios', [])),
            'genres': json.dumps(anilist_data.get('genres', [])),
            'recommendations': json.dumps(anilist_data.get('recommendations', [])),
            'nextAiringEpisode': json.dumps(anilist_data.get('nextAiringEpisode'))
        })
        
        query_map = """
            INSERT INTO anime_mappings ("anilistId", "providerId", "providerSlug", "updatedAt")
            VALUES (:anilistId, :providerId, :providerSlug, NOW())
            ON CONFLICT ("providerId", "providerSlug") DO UPDATE SET
                "anilistId" = EXCLUDED."anilistId",
                "updatedAt" = NOW()
        """
        await database.execute(query=query_map, values={
            'anilistId': anilist_data.get('anilistId'),
            'providerId': provider_id,
            'providerSlug': provider_slug
        })
    except Exception as e:
        print(f"[DB Upsert Error] {e}")

async def upsert_mapping_atomic(
    anilist_id: int,
    provider_id: str,
    provider_slug: str,
    clean_title: str,
    cover_image: str,
) -> None:
    await database.execute(
        """
        SELECT upsert_mapping_atomic(
            :anilist_id, :provider_id, :provider_slug,
            :clean_title, :cover_image
        )
        """,
        values={
            "anilist_id":    anilist_id,
            "provider_id":   provider_id,
            "provider_slug": provider_slug,
            "clean_title":   clean_title,
            "cover_image":   cover_image,
        },
    )
