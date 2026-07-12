#!/bin/bash
set -euo pipefail

echo "Starting local HashiCorp Vault in Docker..."
# Clean up any existing vault container
docker rm -f healmesh-vault 2>/dev/null || true

docker run --name healmesh-vault -d -p 8200:8200 \
  -e 'VAULT_DEV_ROOT_TOKEN_ID=dev-only-token' \
  -e 'VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200' \
  hashicorp/vault:latest

echo "Waiting for Vault to start..."
sleep 5

export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='dev-only-token'

# If variables are not set in the environment, use placeholders
GROQ_KEY="${GROQ_API_KEY:-placeholder_groq_key}"
BOT_TOKEN="${SLACK_BOT_TOKEN:-placeholder_bot_token}"
SIGNING_SECRET="${SLACK_SIGNING_SECRET:-placeholder_signing_secret}"

echo "Seeding Vault with HealMesh secrets..."
docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=dev-only-token healmesh-vault \
  vault kv put secret/healmesh \
  GROQ_API_KEY="${GROQ_KEY}" \
  SLACK_BOT_TOKEN="${BOT_TOKEN}" \
  SLACK_SIGNING_SECRET="${SIGNING_SECRET}"

echo "Vault setup complete. Vault is running at http://127.0.0.1:8200 with root token 'dev-only-token'."
