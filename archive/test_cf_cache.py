import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv("apps/api/.env")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def test_cache():
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return

    # 1. Create a dummy file
    with open("dummy_video.mp4", "wb") as f:
        f.write(b"this is a dummy video content for testing cloudflare cache api")

    # 2. Upload to Telegram
    print("Uploading dummy file to Telegram...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    async with httpx.AsyncClient() as client:
        with open("dummy_video.mp4", "rb") as f:
            response = await client.post(
                url,
                data={"chat_id": CHAT_ID},
                files={"document": ("dummy_video.mp4", f)}
            )
    
    if response.status_code != 200:
        print("Upload failed:", response.text)
        return
    
    data = response.json()
    file_id = data["result"]["document"]["file_id"]
    print(f"Uploaded successfully! File ID: {file_id}")

    proxy_url = f"https://tg-proxy.moehamadhkl.workers.dev/{file_id}"
    print(f"\nTesting Proxy URL: {proxy_url}")

    # 3. First request (Should MISS cache and fetch from origin)
    print("\n--- Request 1 (Should be MISS or DYNAMIC) ---")
    async with httpx.AsyncClient() as client:
        t0 = time.time()
        res1 = await client.get(proxy_url)
        t1 = time.time()
        print(f"Status: {res1.status_code}")
        print(f"CF-Cache-Status: {res1.headers.get('CF-Cache-Status')}")
        print(f"Time taken: {(t1 - t0) * 1000:.2f} ms")

    time.sleep(2) # Wait a bit for Edge cache to persist

    # 4. Second request (Should HIT cache)
    print("\n--- Request 2 (Should be HIT) ---")
    async with httpx.AsyncClient() as client:
        t0 = time.time()
        res2 = await client.get(proxy_url)
        t1 = time.time()
        print(f"Status: {res2.status_code}")
        print(f"CF-Cache-Status: {res2.headers.get('CF-Cache-Status')}")
        print(f"Time taken: {(t1 - t0) * 1000:.2f} ms")
        
if __name__ == "__main__":
    import asyncio
    asyncio.run(test_cache())