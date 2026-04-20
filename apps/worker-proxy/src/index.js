/**
 * Cloudflare Worker for Telegram Swarm Storage Proxy
 * This worker acts as a near-0ms bridge between the user's browser and Telegram's servers.
 * It takes a `file_id` from the URL, queries Telegram for the real `file_path`,
 * and streams the file chunk-by-chunk to the browser with full Range Request support
 * (which is mandatory for HLS streaming and video players).
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // Setup CORS headers to allow video players from any origin
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
      "Access-Control-Allow-Headers": "Range, Content-Type",
    };

    // Handle CORS preflight requests
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // Path pattern: /<file_id>
    const fileId = url.pathname.slice(1);
    if (!fileId) {
      return new Response("Missing file_id in URL path", { status: 400, headers: corsHeaders });
    }

    // 1. Get the actual download path from Telegram API
    // We use the TELEGRAM_BOT_TOKEN stored in the Worker's secrets
    
    try {
      // Use KV cache to reduce Telegram getFile API latency
      let filePath = env.FILE_CACHE ? await env.FILE_CACHE.get(fileId) : null;

      if (!filePath) {
        const getFileUrl = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/getFile?file_id=${fileId}`;
        const tgFileResponse = await fetch(getFileUrl);
        if (!tgFileResponse.ok) {
          return new Response("Telegram API Error", { status: tgFileResponse.status, headers: corsHeaders });
        }

        const tgFileData = await tgFileResponse.json();
        if (!tgFileData.ok) {
          return new Response("File not found on Telegram", { status: 404, headers: corsHeaders });
        }

        filePath = tgFileData.result.file_path;
        if (env.FILE_CACHE) {
          ctx.waitUntil(env.FILE_CACHE.put(fileId, filePath, { expirationTtl: 86400 }));
        }
      }

      // 2. Setup caching logic
      const cache = caches.default;
      
      // Create a cache key without the Range header to ensure we match the full cached object
      const cacheKey = new Request(url.toString(), request);
      cacheKey.headers.delete("Range");
      
      let response = await cache.match(cacheKey);

      if (!response) {
        const tgDownloadUrl = `https://api.telegram.org/file/bot${env.TELEGRAM_BOT_TOKEN}/${filePath}`;

        const originalName = url.searchParams.get('name') || '';
        const isHLS = filePath.endsWith('.ts') || filePath.endsWith('.m3u8') || originalName.endsWith('.ts') || originalName.endsWith('.m3u8');

        // Fetch from Telegram
        const fetchHeaders = new Headers();
        const range = request.headers.get("Range");
        
        // Only forward Range header for non-HLS (like MP4s). 
        // For HLS segments, force fetch the full file so we can cache a 200 OK.
        if (range && !isHLS) {
          fetchHeaders.set("Range", range);
        }

        const fileResponse = await fetch(tgDownloadUrl, {
          method: "GET",
          headers: fetchHeaders,
        });

        // Build Response Headers
        const responseHeaders = new Headers(fileResponse.headers);
        for (const [key, value] of Object.entries(corsHeaders)) {
          responseHeaders.set(key, value);
        }
        
        // Cache Control for CDN
        // Cache for 1 year (31536000 seconds) since Telegram files are immutable
        responseHeaders.set('Cache-Control', 'public, max-age=31536000');

        if (filePath.endsWith('.ts') || originalName.endsWith('.ts')) {
          responseHeaders.set('Content-Type', 'video/mp2t');
        } else if (filePath.endsWith('.m3u8') || originalName.endsWith('.m3u8')) {
          responseHeaders.set('Content-Type', 'application/vnd.apple.mpegurl');
        } else if (filePath.endsWith('.mp4') || originalName.endsWith('.mp4')) {
          responseHeaders.set('Content-Type', 'video/mp4');
        } else {
          const upstreamCT = fileResponse.headers.get('Content-Type');
          if (upstreamCT) {
            responseHeaders.set('Content-Type', upstreamCT);
          } else {
            responseHeaders.set('Content-Type', 'video/mp2t');
          }
        }

        response = new Response(fileResponse.body, {
          status: fileResponse.status,
          statusText: fileResponse.statusText,
          headers: responseHeaders,
        });

        // Put in cache (waitUntil prevents blocking the response)
        // Only cache 200 OK responses (or 206 Partial Content if safely cacheable, but CF handles 206 caching differently. 
        // Generally, we cache the 200 response and CF serves 206 from it).
        if (fileResponse.status === 200) {
          ctx.waitUntil(cache.put(cacheKey, response.clone()));
        }
      } else {
        // We have a cache hit. We just need to ensure CORS headers are present.
        const headers = new Headers(response.headers);
        for (const [key, value] of Object.entries(corsHeaders)) {
          headers.set(key, value);
        }
        response = new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers: headers
        });
      }

      return response;

    } catch (error) {
      return new Response(`Proxy Error: ${error.message}`, { status: 500, headers: corsHeaders });
    }
  }
};
