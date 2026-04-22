// features/detail/DetailClient.tsx — Anime detail page client component
"use client";

import { useState, memo, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { IconBack, IconPlay, IconBookmark, IconShare, IconStar } from "@/ui/icons";
import { useSettings, useToast } from "@/core/stores/app-store";
import { useCollection } from "@/core/hooks/use-collection";
import { authClient } from "@/core/lib/auth-client";
import { EpisodeList } from "./EpisodeList";
import { AnimeCard } from "@/ui/cards/AnimeCard";

function formatCountdown(seconds: number) {
  const d = Math.floor(seconds / (3600 * 24));
  const h = Math.floor((seconds % (3600 * 24)) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}H ${h}J`;
  if (h > 0) return `${h}J ${m}M`;
  return `${m}M`;
}

import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then(res => res.json());

export default function DetailClient({ detail, id }: { detail: any; id: string }) {
  const router = useRouter();
  const accent = "#0A84FF";
  const { data: session } = authClient.useSession();
  const { items, toggle } = useCollection(session?.user?.id);
  const { toast } = useToast();
  const [mounted, setMounted] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const { data: stats } = useSWR(
    `https://jonyyyyyyyu-anime-scraper-api.hf.space/api/v2/social/anime/${id}/stats`,
    fetcher
  );

  useEffect(() => {
    setMounted(true);
  }, []);

  const d = detail;
  const saved = mounted ? !!items.find((w: any) => String(w.id) === id) : false;
  const desc = (d.synopsis || "").replace(/<br\s*\/?>/gi, "\n").replace(/<[^>]*>/g, "").trim();
  const eps = d.episodes || [];
  const recs = d.recommendations || [];

  const firstEp = eps.length > 0 && eps[0].url ? eps[0].url.replace(/\/$/, "").split("/").pop() : null;

  const handleShare = () => {
    if (navigator.share) {
      navigator.share({
        title: d.title,
        url: window.location.href
      }).catch(console.error);
    } else {
      navigator.clipboard.writeText(window.location.href);
      toast("Link disalin!", "success");
    }
  };

  return (
    <main className="min-h-screen bg-black pb-24 text-white overflow-y-auto no-scrollbar">
      {/* Hero */}
      <div className="w-full h-[450px] md:h-[500px] relative bg-black anim-fade">
        {d.poster && <img src={d.poster} className="w-full h-full object-cover opacity-50" alt="" loading="eager" fetchPriority="high" onError={(e) => { e.currentTarget.style.display = 'none'; }} />}
        
        {/* Accent Glow (Layer 0: Behind the black fade) */}
        <div className="absolute inset-0 opacity-40 pointer-events-none" style={{ background: `radial-gradient(circle at 50% 80%, ${accent}, transparent 70%)` }} />

        {/* Layer 1: Base shading */}
        <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent" />
        
        {/* Layer 2: Harder gradient at the bottom to ensure seamless blend with black background */}
        <div className="absolute inset-x-0 bottom-0 h-[250px] bg-gradient-to-t from-black via-black/80 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 h-[100px] bg-gradient-to-t from-black to-transparent" />
        
        <button onClick={() => router.back()} className="absolute top-10 left-5 w-9 h-9 bg-black/50 rounded-full flex items-center justify-center text-white border border-white/20 active:scale-90 z-20"><IconBack /></button>
      </div>

      <div className="px-5 md:px-8 -mt-[200px] md:-mt-[240px] relative z-10 max-w-4xl mx-auto">
        {/* Title row */}
        <div className="flex flex-col md:flex-row gap-4 md:gap-6 mb-8 anim-up">
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl md:text-4xl font-black text-white leading-[1.1] mb-1">{d.title}</h1>
            {d.nativeTitle && <h2 className="text-sm text-[#8e8e93] mb-3">{d.nativeTitle}</h2>}

            <div className="flex items-center gap-2 text-[12px] font-semibold flex-wrap mb-4">
              {d.score && <span className="text-[#30D158] flex items-center gap-0.5"><IconStar /> {(d.score / 10).toFixed(1)}</span>}
              <span className="text-[#48484a]">•</span>
              <span className="text-[#e5e5ea]">{d.status === "RELEASING" ? "ONGOING" : d.status === "FINISHED" ? "TAMAT" : d.status || "TBA"}</span>
              <span className="text-[#48484a]">•</span>
              <span className="text-[#e5e5ea]">{eps.length} Eps</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {firstEp ? (
                <Link href={`/watch/${id}/${firstEp}`} className="px-8 py-3 rounded-2xl text-white font-bold flex items-center gap-2 text-sm active:scale-95" style={{ backgroundColor: accent }}>
                  <IconPlay /> Putar Eps 1
                </Link>
              ) : (
                <button disabled className="px-8 py-3 rounded-2xl text-[#8e8e93] bg-[#1c1c1e] font-bold text-sm cursor-not-allowed">Belum Tersedia</button>
              )}
              <button onClick={() => { const added = toggle({ id, title: d.title, img: d.poster, totalEps: d.totalEpisodes || eps.length }); toast(added ? "Ditambahkan" : "Dihapus", added ? "success" : "error"); }}
                className={`w-12 py-3 rounded-2xl flex items-center justify-center border active:scale-95 ${saved ? "bg-white/15 border-white/30 text-white" : "bg-[#1c1c1e] border-white/10 text-[#8e8e93]"}`}>
                <IconBookmark filled={saved} />
              </button>
              <button onClick={handleShare} className="w-12 py-3 rounded-2xl bg-[#1c1c1e] flex items-center justify-center border border-white/10 text-[#8e8e93] active:scale-95"><IconShare /></button>
            </div>
          </div>
        </div>

        <div className="space-y-8 anim-up" style={{ animationDelay: "80ms" }}>
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {[
              ["Status", d.status === "FINISHED" ? "Selesai" : d.status === "RELEASING" ? "Tayang" : "TBA"],
              ["Studio", d.studios?.join(", ") || "-"],
              ["Musim", d.season ? `${d.season.toLowerCase()} ${d.seasonYear}` : "-"],
              ["Jadwal Rilis", d.airSchedule || "-"],
            ].map(([l, v]) => (
              <div key={l} className="bg-[#1c1c1e] rounded-2xl p-3 border border-white/5">
                <p className="text-[#8e8e93] text-[10px] uppercase tracking-wider mb-0.5">{l}</p>
                <p className="text-white font-bold text-sm capitalize line-clamp-1">{v}</p>
              </div>
            ))}
            <div className="bg-[#1c1c1e] rounded-2xl p-3 border border-white/5">
              <p className="text-[#8e8e93] text-[10px] uppercase tracking-wider mb-0.5">Genre</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {d.genres && d.genres.length > 0 ? d.genres.map((g: string) => (
                  <Link key={g} href={`/explore?genre=${encodeURIComponent(g)}`} className="text-white font-bold text-[11px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded transition-colors active:scale-95">
                    {g}
                  </Link>
                )) : <p className="text-white font-bold text-sm">-</p>}
              </div>
            </div>
          </div>

          {/* Synopsis */}
          <div>
            <h3 className="text-white font-bold text-base mb-2">Ringkasan</h3>
            <p className={`text-[#e5e5ea] text-[14px] leading-relaxed whitespace-pre-line transition-all duration-300 ${isExpanded ? "" : "line-clamp-3"}`}>
              {desc || "Sinopsis tidak tersedia."}
            </p>
            {desc && desc.length > 150 && (
              <button 
                onClick={() => setIsExpanded(!isExpanded)}
                className="text-[#0A84FF] text-[13px] font-bold mt-2 hover:underline focus:outline-none"
              >
                {isExpanded ? "Sembunyikan" : "Selengkapnya"}
              </button>
            )}
          </div>

          {/* Episodes List */}
          <div>
            <h3 className="text-white font-bold text-base mb-4">Episode</h3>
            <EpisodeList episodes={eps} animeId={id} cover={d.poster} />
          </div>

          {/* Recommendations */}
          {recs.length > 0 && (
            <div className="mt-8">
              <h3 className="text-white font-bold text-base mb-4">Rekomendasi</h3>
              <div className="flex gap-3 overflow-x-auto no-scrollbar pb-4 snap-x">
                {recs.map((r: any, i: number) => (
                  <div key={i} className="min-w-[120px] snap-start">
                    <AnimeCard id={String(r.id)} title={r.title} img={r.cover || r.poster || r.image} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}