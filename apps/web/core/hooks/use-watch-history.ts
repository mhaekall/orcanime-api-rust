// core/hooks/use-watch-history.ts — Cloud sync with FastAPI /api/v2/social/progress

import useSWR from "swr";
import { useCallback, useEffect, useState } from "react";
import type { WatchHistoryItem } from "@/core/types/anime";
import { API } from "@/core/lib/api";

// We use anilistId as the primary key as per TEAM_MANIFESTO.md
const API_URL = `${API}/api/v2/social/progress`;
const LOCAL_KEY = "ani-history-v3";

function getLocal(): WatchHistoryItem[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(LOCAL_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveLocal(items: WatchHistoryItem[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(LOCAL_KEY, JSON.stringify(items.slice(0, 30)));
}

const fetcher = async (url: string, userId?: string): Promise<WatchHistoryItem[]> => {
  if (!userId) return getLocal();
  try {
    const res = await fetch(`${url}?user_id=${userId}`);
    const data = await res.json();
    
    const dataArray = Array.isArray(data) ? data : (data?.data || []);
    // Map backend response back to WatchHistoryItem frontend format
    const mapped = dataArray.map((h: any) => ({
      anilistId: parseInt(h.animeSlug || h.anilistId),
      episode: h.episode || h.episodeNumber,
      timestampSec: h.timestampSec || h.progressSeconds,
      durationSec: h.durationSec || h.durationSeconds,
      completed: h.completed || h.isCompleted,
      updatedAt: h.updatedAt,
      animeTitle: h.cleanTitle || h.nativeTitle || h.animeTitle,
      animeCover: h.coverImage || h.animeCover
    }));

    if (mapped.length > 0) saveLocal(mapped);
    return mapped;
  } catch (e) {
    console.error("[History Sync] Fetch error:", e);
    return getLocal();
  }
};

export function useWatchHistory(userId?: string) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const { data: history, mutate, isLoading } = useSWR<WatchHistoryItem[]>(
    mounted && userId ? [API_URL, userId] : null,
    ([url, uid]: [string, string]) => fetcher(url, uid),
    { revalidateOnFocus: false, dedupingInterval: 10_000, keepPreviousData: true }
  );

  const [display, setDisplay] = useState<WatchHistoryItem[]>(getLocal());

  useEffect(() => {
    if (!mounted) return;
    const local = getLocal();
    if (!userId) {
      setDisplay(local);
      return;
    }

    if (history) {
      if (history.length === 0 && local.length > 0) {
        const merged = [...history];
        local.forEach(l => {
          if (!merged.find(m => m.anilistId === l.anilistId && m.episode === l.episode)) {
            merged.push(l);
          }
        });
        setDisplay(merged);
      } else {
        setDisplay(history);
      }
    }
  }, [history, userId, mounted]);

  const updateProgress = useCallback(
    async (item: Omit<WatchHistoryItem, "updatedAt">) => {
      if (!userId) {
        // Fallback to local only if not logged in
        const nextLocal = (prev: WatchHistoryItem[] = []) => {
          const idx = prev.findIndex((h) => h.anilistId === item.anilistId && h.episode === item.episode);
          const copy = [...prev];
          const enriched = { ...item, updatedAt: new Date().toISOString() };
          if (idx >= 0) copy[idx] = { ...copy[idx], ...enriched };
          else copy.unshift(enriched as WatchHistoryItem);
          return copy.slice(0, 30);
        };
        saveLocal(nextLocal(display));
        return;
      }

      // Optimistic cloud update
      const next = (prev: WatchHistoryItem[] = []) => {
        const idx = prev.findIndex((h) => h.anilistId === item.anilistId && h.episode === item.episode);
        const copy = [...prev];
        const enriched = { ...item, updatedAt: new Date().toISOString() };
        if (idx >= 0) copy[idx] = { ...copy[idx], ...enriched };
        else copy.unshift(enriched as WatchHistoryItem);
        return copy.slice(0, 30);
      };

      saveLocal(next(display));

      await mutate(
        async (current) => {
          try {
            await fetch(API_URL, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                user_id: userId,
                anilistId: item.anilistId,
                episodeNumber: item.episode,
                progressSeconds: item.timestampSec,
                durationSeconds: item.durationSec,
                isCompleted: item.completed
              }),
            });
          } catch (e) {
            console.error("[History Sync] Push failed:", e);
          }
          return next(current);
        },
        { optimisticData: next(display), revalidate: false, rollbackOnError: false }
      );
    },
    [mutate, display, userId]
  );

  return { history: display, isLoading: isLoading || !mounted, updateProgress };
}
