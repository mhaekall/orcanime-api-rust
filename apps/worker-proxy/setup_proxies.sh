#!/bin/bash
set -e

cd "$(dirname "$0")"

# Number of proxy instances to create
NUM_PROXIES=5

echo "🚀 Setting up $NUM_PROXIES Telegram Swarm Proxies on Cloudflare Workers..."

# We need the main TELEGRAM_BOT_TOKEN to set as a secret.
# Let's extract it from the api/.env file
BOT_TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' ../api/.env | cut -d '=' -f2 | tr -d '"')

if [ -z "$BOT_TOKEN" ]; then
  echo "❌ Error: TELEGRAM_BOT_TOKEN not found in apps/api/.env"
  exit 1
fi

PROXY_URLS=""

for i in $(seq 1 $NUM_PROXIES); do
  WORKER_NAME="tg-proxy-$i"
  echo "📦 Deploying $WORKER_NAME..."
  
  # Create a temporary wrangler.toml for this specific proxy
  cat <<EOF > wrangler.toml
name = "$WORKER_NAME"
main = "src/index.js"
compatibility_date = "2023-10-16"

[[kv_namespaces]]
binding = "FILE_CACHE"
id = "bcda6844249d4c4a862c04f3ba21d77f"
EOF

  # Deploy the worker
  pnpm exec wrangler deploy
  
  # Set the secret (bot token) for the worker
  echo "$BOT_TOKEN" | pnpm exec wrangler secret put TELEGRAM_BOT_TOKEN --name "$WORKER_NAME"
  
  # The URL usually follows this format:
  # https://tg-proxy-$i.<your-cloudflare-subdomain>.workers.dev
  # We will get the URL from wrangler output or predict it.
  
  # Assuming the subdomain is 'moehamadhkl' based on previous logs:
  URL="https://$WORKER_NAME.moehamadhkl.workers.dev"
  PROXY_URLS="$PROXY_URLS\nTG_PROXY_BASE_URL_$i=\"$URL\""
done

# Restore the original wrangler.toml
cat <<EOF > wrangler.toml
name = "tg-proxy"
main = "src/index.js"
compatibility_date = "2023-10-16"

[[kv_namespaces]]
binding = "FILE_CACHE"
id = "bcda6844249d4c4a862c04f3ba21d77f"
EOF

echo -e "\n✅ Deployment Complete!"
echo -e "Add these to your apps/api/.env:"
echo -e "$PROXY_URLS"

# Automatically append to .env if not exists
for i in $(seq 1 $NUM_PROXIES); do
  WORKER_NAME="tg-proxy-$i"
  URL="https://$WORKER_NAME.moehamadhkl.workers.dev"
  if ! grep -q "TG_PROXY_BASE_URL_$i" ../api/.env; then
    echo "TG_PROXY_BASE_URL_$i=\"$URL\"" >> ../api/.env
  fi
done

echo "Updated apps/api/.env successfully."
