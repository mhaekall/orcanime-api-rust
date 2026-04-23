// ui/cards/AnimeRow.tsx — Horizontal scrollable row of AnimeCards

"use client";

import { memo } from "react";
import { AnimeCard } from "./AnimeCard";

interface Props {
  title: string;
  items: any[];
  showRank?: boolean;
  variant?: "vertical" | "horizontal";
}

function AnimeRowInner({ title, items, showRank, variant = "vertical" }: Props) {
  if (!items || items.length === 0) return null;

  const isHorizontal = variant === "horizontal";
  const itemWidthClass = isHorizontal ? "w-[240px] md:w-[280px]" : "w-[130px] sm:w-[150px] md:w-[170px]";

  return (
    <section className="mb-8 w-full overflow-hidden">
      <div className="flex items-center justify-between mb-3 px-5 md:px-8">
        <h2 className="text-lg md:text-xl font-black text-white">{title}</h2>
      </div>
      <div className="flex gap-3 md:gap-4 overflow-x-auto pb-4 snap-x snap-mandatory no-scrollbar px-5 md:px-8" style={{ WebkitOverflowScrolling: "touch" }}>
        {items.map((a, i) => {
          const id = String(a.anilistId || a.id || "");
          if (!id) return null;
          return (
            <div key={`${id}-${i}`} className={`snap-start shrink-0 ${itemWidthClass}`}>
              <AnimeCard
                id={id}
                title={a.title?.english || a.title?.romaji || a.title || ""}
                img={a.img || a.coverImage?.extraLarge || a.coverImage?.large || null}
                banner={a.banner || a.bannerImage || null}
                score={a.score || a.averageScore}
                views={a.views}
                color={a.color || a.coverImage?.color}
                epId={a.latestEpisode ? String(a.latestEpisode) : undefined}
                rank={showRank ? i + 1 : undefined}
                variant={variant}
              />
            </div>
          );
        })}
      </div>
    </section>
  );
}

export const AnimeRow = memo(AnimeRowInner);

