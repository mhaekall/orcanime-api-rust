#!/usr/bin/env python3
"""
scripts/force_sync_kuronime.py
================================
Force-trigger reconciliation for all Kuronime slugs that are still
unmapped in the anime_mappings table.

Usage:
    cd apps/api
    python -m scripts.force_sync_kuronime [--dry-run] [--limit N]

What it does:
  1. Queries the DB for all Kuronime provider entries with no anilist mapping.
  2. Runs them through AnimeReconciler.reconcile() — which now includes
     slug sanitization + Gemini fallback (the fix in reconciler.py).
  3. On success, upserts the result into anime_mappings.
  4. Prints a summary at the end.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import os

# Allow running from apps/api root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import database
from services.reconciler import AnimeReconciler, GeminiMatcher

PROVIDER_ID = "kuronime"


async def fetch_unmapped_slugs(limit: int | None = None) -> list[dict]:
    """Fetch recent anime from Kuronime provider and filter out those already mapped."""
    from services.providers import kuronime_provider
    
    slugs_to_process = []
                
    # Also we want Dan Da Dan and One Piece explicitly
    search_queries = ["one piece", "dan da dan", "naruto", "bleach", "jujutsu kaisen"]
    for query in search_queries:
        print(f"[ForceSyncKuronime] Searching for '{query}'...")
        try:
            results = await kuronime_provider.search(query)
            for item in results:
                url = item.get('url', '')
                if url:
                    slug = url.strip('/').split('/')[-1]
                    slugs_to_process.append({"providerSlug": slug, "rawTitle": item.get('title')})
        except Exception as e:
            print(f"[ForceSyncKuronime] Error searching '{query}': {e}")
                
    # Deduplicate
    unique_slugs = {}
    for item in slugs_to_process:
        unique_slugs[item["providerSlug"]] = item
    
    slugs_to_process = list(unique_slugs.values())
    
    # Filter out already mapped
    unmapped = []
    for item in slugs_to_process:
        slug = item["providerSlug"]
        row = await database.fetch_one(
            'SELECT "anilistId" FROM anime_mappings WHERE "providerId" = :pid AND "providerSlug" = :slug',
            {"pid": PROVIDER_ID, "slug": slug}
        )
        if not row:
            unmapped.append(item)
            
    if limit:
        unmapped = unmapped[:limit]
        
    return unmapped


async def upsert_mapping(provider_slug: str, anilist_id: int) -> None:
    await database.execute(
        """
        INSERT INTO anime_mappings ("providerId", "providerSlug", "anilistId")
        VALUES (:pid, :slug, :aid)
        ON CONFLICT ("providerId", "providerSlug")
        DO UPDATE SET "anilistId" = EXCLUDED."anilistId"
        """,
        {"pid": PROVIDER_ID, "slug": provider_slug, "aid": anilist_id},
    )


async def run(dry_run: bool = False, limit: int | None = None) -> None:
    await database.connect()
    reconciler = AnimeReconciler()

    print(f"[ForceSyncKuronime] Fetching unmapped slugs (limit={limit or 'all'}) ...")
    slugs = await fetch_unmapped_slugs(limit)
    print(f"[ForceSyncKuronime] Found {len(slugs)} unmapped Kuronime slugs.\n")

    if not slugs:
        print("[ForceSyncKuronime] Nothing to sync. Exiting.")
        await database.disconnect()
        return

    ok_count = 0
    fail_count = 0
    fail_slugs: list[str] = []

    for i, row in enumerate(slugs, 1):
        slug = row["providerSlug"]
        raw_title = row.get("rawTitle") or slug

        print(f"[{i}/{len(slugs)}] Processing: '{slug}' (raw_title='{raw_title}')")

        result = await reconciler.reconcile(
            provider_id=PROVIDER_ID,
            provider_slug=slug,
            raw_title=raw_title,
        )

        if result:
            print(
                f"  ✅  Matched → '{result.canonical_title}' "
                f"(anilistId={result.canonical_anilist_id}, "
                f"via={result.providers[0].matched_via if result.providers else '?'})"
            )
            if not dry_run:
                await upsert_mapping(slug, result.canonical_anilist_id)
            ok_count += 1
        else:
            print(f"  ❌  No match found.")
            fail_count += 1
            fail_slugs.append(slug)

        # Small delay to respect AniList rate limit (90 req/min)
        await asyncio.sleep(0.7)

    print(f"\n{'='*60}")
    print(f"[ForceSyncKuronime] Done.")
    print(f"  Mapped:   {ok_count}")
    print(f"  Failed:   {fail_count}")
    if dry_run:
        print("  (DRY RUN — no changes written to DB)")
    if fail_slugs:
        print(f"\nFailed slugs:")
        for s in fail_slugs:
            print(f"  - {s}")

    await GeminiMatcher.close()
    await database.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Force-sync Kuronime → AniList mappings")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to DB")
    parser.add_argument("--limit", type=int, default=None, help="Max slugs to process")
    args = parser.parse_args()

    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()