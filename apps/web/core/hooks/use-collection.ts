// core/hooks/use-collection.ts — Cloud sync with FastAPI /api/v2/collection

import useSWR from "swr";
import { useCallback, useEffect, useState } from "react";
import { WatchlistItem } from "@/core/stores/app-store"; // Keep the interface from there for now

const API_URL = process.env.NEXT_PUBLIC_API_URL ? `${process.env.NEXT_PUBLIC_API_URL}/api/v2/collection` : "https://jonyyyyyyyu-anime-scraper-api.hf.space/api/v2/collection";
const LOCAL_KEY = "ani-collection-v3";
const SYNC_QUEUE_KEY = "ani-sync-queue";

interface SyncAction {
  action: "update" | "remove";
  payload: any;
  timestamp: number;
}

function getSyncQueue(): SyncAction[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(SYNC_QUEUE_KEY) || "[]");
  } catch {
    return [];
  }
}

function addToSyncQueue(action: "update" | "remove", payload: any) {
  if (typeof window === "undefined") return;
  const queue = getSyncQueue();
  queue.push({ action, payload, timestamp: Date.now() });
  localStorage.setItem(SYNC_QUEUE_KEY, JSON.stringify(queue));
}

function clearSyncQueue() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(SYNC_QUEUE_KEY);
}

function getLocal(): WatchlistItem[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(LOCAL_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveLocal(items: WatchlistItem[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(LOCAL_KEY, JSON.stringify(items));
}

const fetcher = async (url: string, userId?: string): Promise<WatchlistItem[]> => {
  if (!userId) return getLocal();
  try {
    const res = await fetch(`${url}?user_id=${userId}`);
    if (!res.ok) throw new Error("Failed to fetch collection");
    const data = await res.json();
    
    const dataArray = Array.isArray(data) ? data : (data?.data || []);
    // Map backend response back to WatchlistItem frontend format
    const mapped = dataArray.map((h: any) => ({
      id: String(h.animeSlug || h.anilistId),
      title: h.cleanTitle || h.nativeTitle || h.animeTitle || `Anime #${h.animeSlug}`,
      img: h.coverImage || h.animeCover,
      totalEps: h.totalEpisodes || 0,
      status: h.status, // watching, plan_to_watch, completed, dropped
      progress: h.progress || 0,
      addedAt: new Date(h.updatedAt).getTime(),
      updatedAt: new Date(h.updatedAt).getTime()
    }));

    if (mapped.length > 0) saveLocal(mapped);
    return mapped;
  } catch (e) {
    console.error("[Collection Sync] Fetch error:", e);
    return getLocal();
  }
};

export function useCollection(userId?: string) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const { data: collection, mutate, isLoading } = useSWR<WatchlistItem[]>(
    mounted && userId ? [API_URL, userId] : null,
    ([url, uid]: [string, string]) => fetcher(url, uid),
    { revalidateOnFocus: false, dedupingInterval: 10_000, keepPreviousData: true }
  );

  // Big Tech Sync Logic: Merge local and cloud, and migrate if cloud is empty
  const [display, setDisplay] = useState<WatchlistItem[]>(getLocal());

  // Background sync processor
  useEffect(() => {
    if (!mounted || !userId) return;

    const processSyncQueue = async () => {
      const queue = getSyncQueue();
      if (queue.length === 0) return;

      console.log(`[Sync] Processing ${queue.length} offline actions...`);
      let allSuccess = true;

      for (const item of queue) {
        try {
          if (item.action === "update") {
            const res = await fetch(API_URL, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(item.payload),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
          } else if (item.action === "remove") {
            const { user_id, anilistId } = item.payload;
            const res = await fetch(`${API_URL}?user_id=${user_id}&anilistId=${anilistId}`, {
              method: "DELETE"
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
          }
        } catch (e) {
          console.error(`[Sync] Failed to process queued action ${item.action}:`, e);
          allSuccess = false;
          break; // Stop processing on first failure
        }
      }

      if (allSuccess) {
        clearSyncQueue();
        mutate(); // Revalidate with server
      }
    };

    const handleOnline = () => processSyncQueue();
    window.addEventListener('online', handleOnline);
    
    // Attempt processing on mount
    if (navigator.onLine) {
      processSyncQueue();
    }

    return () => window.removeEventListener('online', handleOnline);
  }, [mounted, userId, mutate]);

  useEffect(() => {
    if (!mounted) return;
    
    const local = getLocal();
    if (!userId) {
      setDisplay(local);
      return;
    }

    if (collection) {
      if (collection.length === 0 && local.length > 0) {
        // Potential migration needed: if cloud is empty but local has data
        // For now, we show local but we SHOULD show cloud if it's the source of truth.
        // To fix the "disappearing" bug, we merge them.
        const merged = [...collection];
        local.forEach(l => {
          if (!merged.find(m => String(m.id) === String(l.id))) {
            merged.push(l);
          }
        });
        setDisplay(merged);
        
        // Auto-migrate first item to trigger cloud save (or we could loop, but let's keep it safe)
        // updateStatus(local[0]); 
      } else {
        setDisplay(collection);
      }
    }
  }, [collection, userId, mounted]);

  const updateStatus = useCallback(
    async (item: Omit<WatchlistItem, "addedAt" | "updatedAt">) => {
      if (!userId) {
        // Fallback to local only if not logged in
        const nextLocal = (prev: WatchlistItem[] = []) => {
          const idx = prev.findIndex((h) => String(h.id) === String(item.id));
          const copy = [...prev];
          const enriched = { ...item, addedAt: Date.now(), updatedAt: Date.now() };
          if (idx >= 0) copy[idx] = { ...copy[idx], ...enriched };
          else copy.unshift(enriched as WatchlistItem);
          return copy;
        };
        saveLocal(nextLocal(display));
        return;
      }

      // Optimistic cloud update
      const next = (prev: WatchlistItem[] = []) => {
        const idx = prev.findIndex((h) => String(h.id) === String(item.id));
        const copy = [...prev];
        const enriched = { ...item, addedAt: Date.now(), updatedAt: Date.now() };
        if (idx >= 0) copy[idx] = { ...copy[idx], ...enriched };
        else copy.unshift(enriched as WatchlistItem);
        return copy;
      };
      
      saveLocal(next(display));

      await mutate(
        async (current) => {
          const payload = {
            user_id: userId,
            anilistId: String(item.id),
            status: item.status,
            progress: item.progress
          };
          try {
            const res = await fetch(API_URL, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return next(current);
          } catch (e) {
            console.error("[Sync] Offline fallback: Queuing update", e);
            addToSyncQueue("update", payload);
            return next(current);
          }
        },
        { optimisticData: next(display), rollbackOnError: false, revalidate: false }
      );
    },
    [userId, mutate, display]
  );

  const remove = useCallback(
    async (id: string | number) => {
      if (!userId) {
        const nextLocal = display.filter((h) => String(h.id) !== String(id));
        saveLocal(nextLocal);
        return;
      }

      const next = (prev: WatchlistItem[] = []) => prev.filter((h) => String(h.id) !== String(id));

      saveLocal(next(display));

      await mutate(
        async (current) => {
          const payload = { user_id: userId, anilistId: id };
          try {
            const res = await fetch(`${API_URL}?user_id=${userId}&anilistId=${id}`, {
              method: "DELETE"
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return next(current);
          } catch (e) {
            console.error("[Sync] Offline fallback: Queuing remove", e);
            addToSyncQueue("remove", payload);
            return next(current);
          }
        },
        { optimisticData: next(display), rollbackOnError: false, revalidate: false }
      );
    },
    [userId, mutate, display]
  );

  const toggle = useCallback(
    (anime: Omit<WatchlistItem, "status" | "progress" | "addedAt" | "updatedAt">, defaultStatus: WatchlistItem["status"] = "plan_to_watch") => {
      const existing = display.find((w) => String(w.id) === String(anime.id));
      if (existing) {
        remove(anime.id);
        return false;
      } else {
        updateStatus({ ...anime, status: defaultStatus, progress: 0 });
        return true;
      }
    },
    [display, remove, updateStatus]
  );

  return { items: display, toggle, updateStatus, remove, isLoading };
}
