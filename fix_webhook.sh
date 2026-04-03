#!/bin/bash
# Script per aggiornare automaticamente il webhook dopo ogni avvio

BOT_TOKEN="8377848932:AAF2RDlzP0Mv5f_jZq_GvxCRZkBsHjXQV-Q"
LOG_FILE="/tmp/helix_watchdog.log"

# Estrai l'URL del tunnel più recente
TUNNEL_URL=$(grep "Tunnel attivo" "$LOG_FILE" | tail -1 | sed 's/.*https:\/\//https:\/\//' | awk '{print $1}')

if [ -n "$TUNNEL_URL" ]; then
    WEBHOOK_URL="${TUNNEL_URL}/api/v1/webhook/telegram"
    echo "🔗 Aggiornando webhook: $WEBHOOK_URL"
    
    # Cancella webhook vecchio
    curl -s "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook?drop_pending_updates=true" > /dev/null
    
    # Imposta nuovo webhook
    RESULT=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")
    
    if echo "$RESULT" | grep -q '"ok":true'; then
        echo "✅ Webhook aggiornato con successo!"
        echo "🌐 URL: $WEBHOOK_URL"
    else
        echo "❌ Errore aggiornamento webhook:"
        echo "$RESULT"
    fi
else
    echo "❌ Nessun URL tunnel trovato nel log"
fi
