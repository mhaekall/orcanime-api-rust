import { VideoPlayer } from "@/ui/player/VideoPlayer";
import { VideoSource } from "@/core/types/anime";

export default function TestPlayerPage() {
  const proxyBase = process.env.NEXT_PUBLIC_TG_PROXY_URL || "https://tg-proxy-1.moehamadhkl.workers.dev";
  const testSources: VideoSource[] = [
    {
      provider: "Telegram Swarm Proxy",
      quality: "1080p",
      url: `${proxyBase}/BQACAgUAAyEGAATc0SFaAAMkadrcTCsz9C08LyIQzIk5OtbtZw8AAvIbAAJSidhWkIrMPA3jiHo7BA`,
      type: "hls"
    }
  ];

  return (
    <div className="min-h-screen bg-[#0a0c10] p-4 md:p-8 flex flex-col items-center justify-center">
      <div className="w-full max-w-4xl space-y-6">
        <div>
          <h1 className="text-white text-3xl font-bold">Uji Coba Ingestion 0ms</h1>
          <p className="text-[#8e8e93] text-sm mt-2">
            Video ini langsung ditarik dari Telegram melalui Cloudflare Worker Anda.
            <br />
            <strong>Catatan:</strong> Ini adalah sampel video berdurasi 30 detik pertama untuk mempercepat proses uji coba.
          </p>
        </div>

        <div className="rounded-2xl overflow-hidden ring-1 ring-white/10 shadow-2xl">
          <VideoPlayer 
            anilistId={147105}
            title="Classroom of the Elite Season 4 - Episode 1 (Sampel 30 Detik)"
            sources={testSources}
            animeSlug="classroom-of-the-elite"
            episodeNum={1}
          />
        </div>
      </div>
    </div>
  );
}
