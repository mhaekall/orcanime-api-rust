# Session Snapshot: The Ultimate $0 Cloud Architecture & Distributed Sharding

## 🎯 Pencapaian Utama Terkini (Arsitektur Cloud-Native & Anti-Limit)

1. **Migrasi Tanpa Keringat (Neon DB Copy-on-Write)**
   - Mengatasi batas **100 CU-hour monthly compute allowance** dari Neon DB (Free Tier) yang menyebabkan server terkunci (suspend) dan menghasilkan HTTP 500 di Frontend.
   - Melakukan *pg_dump* sebesar 43MB dan *import* ke *Project* Neon DB yang 100% baru dengan sukses, menyelamatkan 5.800+ anime dan 9.000+ episode tanpa kehilangan data sedikitpun. Penyusutan *storage* dari 69MB ke 55MB membuktikan *database* lebih bersih (hilangnya *dead tuples*).

2. **Serverless Background Workers di Hugging Face**
   - **Skrip 10-Jam (Scraper)** yang sebelumnya harus berjalan di terminal lokal (Termux) **Telah Berhasil Dipindahkan ke Cloud**. Sekarang berjalan sebagai *Background Task* di FastAPI Hugging Face (`sync_10_hours_bg.py`).
   - **Batch Ingestion Engine** (`ingest_pending.py`) juga diubah untuk berjalan secara *native* di dalam Hugging Face Space.

3. **Bypass Blokir Outbound Hugging Face (Telegram API Proxy)**
   - Menemukan bahwa Hugging Face Spaces memblokir koneksi keluar (*outbound*) secara langsung ke `api.telegram.org` (penyebab *timeout* dan *silent crash*).
   - Solusi Tingkat Dewa: Membuat dan mendeploy **Cloudflare Worker khusus (`tele-proxy`)** yang menyamar sebagai *traffic* web biasa untuk meneruskan seluruh *request* notifikasi dan *upload* file ke API Telegram.

4. **Sistem Tahan Banting (Anti-Sleep & Anti-Infinite Loop)**
   - **GitHub Actions "Malaikat Maut" (`keep-alive-workers.yml`):** Robot *cron* yang menge- *ping* server Hugging Face setiap 15 menit dan otomatis menarik tombol pelatuk (*trigger*) skrip Ingesti & 10-Jam. Mengamankan server dari *Sleep Mode*.
   - **Anti-Infinite Loop (10H-Sync):** Kueri pencarian anime kini hanya menargetkan anime yang belum punya episode **DAN** belum dicek dalam 12 jam terakhir (`updatedAt < NOW() - INTERVAL '12 hours'`). Ini mencegah "Groundhog Day" di mana bot terus-menerus mencari "Case Closed" (Conan) dan *crash*.
   - **FFmpeg 45s Timeout:** Mencegah mesin *ingesti* macet berjam-jam saat mencoba mengunduh URL Wibufile (*direct stream*) yang sudah mati/404/ *tarpit*. Bot kini langsung melompat ke resolusi/sumber cadangan lainnya.

5. **Distributed Sharding (Pasukan Kloning)**
   - Mengubah kode `ingest_pending.py` dan API Webhook untuk menerima parameter `shard_id` dan `total_shards`.
   - Menggunakan rumus `MOD(anilistId, total_shards) = shard_id` agar 9.000+ episode dapat dikeroyok secara paralel oleh 3 (atau lebih) Hugging Face Spaces yang berbeda tanpa pernah bertabrakan. Estimasi 4 Hari Ingesti kini bisa ditebas menjadi < 24 Jam.

6. **Notifikasi Telegram Terpisah & Kaya Data**
   - `TELEGRAM_BOT_TOKEN` (`@myorca4_bot`) didedikasikan untuk laporan *Ingesti* yang super detail (mendukung Judul Anime dan Episode).
   - `TELEGRAM_BOT_TOKEN_6` (`@myorca5_bot`) didedikasikan untuk *Scraper* (Skrip 10-Jam) dengan fitur *Papan Peringkat (Recap)* per 100 anime.

## 🛠️ Status Arsitektur Terkini
- **Frontend (Cloudflare Pages):** Berjalan lancar, telah di- *deploy* ulang dengan menunjuk ke `DATABASE_URL` yang baru. API Token Cloudflare telah diperbarui.
- **Backend (Hugging Face Space):** Sepenuhnya otonom. Tidak lagi bergantung pada terminal lokal pengguna. Bertindak sebagai *Scraper*, *Slicer*, *Uploader*, dan penyedia API sekaligus.
- **Database (Neon Postgres):** Berada di instance baru dengan limit 100 CU-Hour yang 100% penuh.
- **Queue/Logs (Upstash Redis):** Digunakan sangat efisien untuk *State Management* (`10h_sync_status`), *Distributed Locks*, dan *Real-time Logging* (`hf_ingest_logs`).

## 📌 Rencana Sesi Berikutnya (Delegasi ke Claude & Agen 1)
**Tugas Tambahan & Sosial:**
- [ ] Buka plan `.agents/CLAUDE_RECONCILER_TASK.md` untuk perbaikan sistem *Reconciler / Auto-Mapper*.
- [ ] Perbaiki logika pencarian judul ke API Anilist di `reconciler.py` agar tidak langsung gagal jika *provider* mengirimkan judul berbentuk *slug* yang kotor (seperti `one-piece-op`).
- [ ] Implementasikan tebakan cerdas menggunakan Gemini jika pencarian Anilist awal gagal.
- [ ] Perbaiki konflik Alembic di backend agar mengabaikan tabel Drizzle (sosial/user).
- [ ] Selesaikan pembuatan *autogenerate migration* untuk `activity_feed`.