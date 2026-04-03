#!/bin/bash
# Script per aggiornare automaticamente il webhook di Telegram

TUNNEL_URL=$(grep "Tunnel attivo" /tmp/helix_watchdog.log | tail -1 | sed 's/.*https:\/\//https:\/\//' | awk '{print $1}')
BOT_TOKEN="8377848932:AAF2RDlzP0Mv5f_jZq_GvxCRZkBsHjXQV-Q"

if [ -n "$TUNNEL_URL" ]; then
    WEBHOOK_URL="${TUNNEL_URL}/webhook"
    echo "Aggiornando webhook: $WEBHOOK_URL"
    curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}"
    echo ""
else
    echo "Tunnel URL non trovato"
    exit 1
fi
