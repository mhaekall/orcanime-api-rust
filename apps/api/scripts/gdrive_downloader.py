import httpx
import re
import sys
import asyncio
import os
import gdown

async def download_gdrive(url: str, output_path: str):
    print(f"🔗 Memulai resolusi Google Drive via gdown: {url}")
    try:
        # Run gdown in a separate thread to not block the event loop
        success = await asyncio.to_thread(
            gdown.download, 
            url, 
            output_path, 
            quiet=False, 
            fuzzy=True
        )
        if success:
            print(f"\n✅ Berhasil mengunduh ke '{output_path}'")
        else:
            print("\n❌ Gagal mengunduh file.")
    except Exception as e:
        print(f"\n❌ Terjadi kesalahan saat mengunduh via gdown: {e}")

if __name__ == "__main__":
    url = "https://link.desustream.com/?id=Uk83OUtycXp4T0NoTWt3RTFpTzBNdW9xSnA5Z3NXWnBJV1h1L1dTUkxOK3M3THhjcVo1SUN5ZkFFRHhrdzh0d2FXV09oMmpvc09WY2cyb2p6VEZpOUllbS9tVzNWVHhGZERHMnNPZ0hRRzdsMTZWZHEwbHRZdXRjR0VnQUR5SFBMZ0o2L0h1NlUzeGpGMUt5Skx0QTlraz0="
    asyncio.run(download_gdrive(url, "Death_Note_720p.mp4"))
