"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

export function PwaUpdater() {
  const [hasUpdate, setHasUpdate] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined" && "serviceWorker" in navigator) {
      // Periksa update ketika service worker berganti
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        setHasUpdate(true);
      });
      
      // Auto check update secara berkala
      const checkInterval = setInterval(() => {
        navigator.serviceWorker.ready.then(reg => {
          reg.update();
        });
      }, 1000 * 60 * 15); // Cek tiap 15 menit

      return () => clearInterval(checkInterval);
    }
  }, []);

  const handleUpdate = () => {
    window.location.reload();
  };

  if (!hasUpdate) return null;

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[9999] animate-in slide-in-from-top fade-in">
      <div className="bg-[#0A84FF] text-white px-4 py-2 rounded-full shadow-lg flex items-center gap-3 font-semibold text-sm cursor-pointer hover:bg-[#0A84FF]/90 transition-colors" onClick={handleUpdate}>
        <RefreshCw className="w-4 h-4 animate-spin" />
        <span>Versi baru tersedia! Ketuk untuk muat ulang.</span>
      </div>
    </div>
  );
}
