#!/bin/bash
# Auto-restart watchdog per Helix Bot

LOG_FILE="/tmp/helix_watchdog.log"
PID_FILE="/tmp/helix.pid"
TUNNEL_PID="/tmp/helix_tunnel.pid"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

start_server() {
    log "Avvio server..."
    source venv/bin/activate
    nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/helix.log 2>&1 &
    echo $! > "$PID_FILE"
    sleep 3
    
    # Verifica
    if curl -s http://localhost:8000/ | grep -q "Helix"; then
        log "✅ Server avviato (PID: $(cat $PID_FILE))"
        return 0
    else
        log "❌ Server non risponde"
        return 1
    fi
}

start_tunnel() {
    log "Avvio tunnel..."
    pkill -f localtunnel 2>/dev/null
    sleep 1
    nohup npx localtunnel --port 8000 > /tmp/lt.log 2>&1 &
    echo $! > "$TUNNEL_PID"
    sleep 5
    
    URL=$(grep "your url is" /tmp/lt.log | tail -1 | grep -o "https://[^ ]*\.loca\.lt")
    if [ -n "$URL" ]; then
        curl -s -X POST "https://api.telegram.org/bot8377848932:AAF2RDlzP0Mv5f_jZq_GvxCRZkBsHjXQV-Q/setWebhook" \
            -d "url=${URL}/webhook" > /dev/null
        log "✅ Tunnel attivo: $URL"
        return 0
    else
        log "❌ Tunnel non avviato"
        return 1
    fi
}

stop_all() {
    log "Arresto servizi..."
    pkill -f "uvicorn\|python.*app.main" 2>/dev/null
    pkill -f localtunnel 2>/dev/null
    rm -f "$PID_FILE" "$TUNNEL_PID"
    sleep 2
}

check_health() {
    # Controlla server
    if ! curl -s http://localhost:8000/ | grep -q "Helix"; then
        log "⚠️ Server non risponde, riavvio..."
        return 1
    fi
    
    # Controlla tunnel
    if ! pgrep -f "localtunnel" > /dev/null; then
        log "⚠️ Tunnel morto, riavvio..."
        return 1
    fi
    
    return 0
}

# Gestione argomenti
case "${1:-run}" in
    start)
        stop_all
        start_server && start_tunnel
        log "🚀 Bot avviato!"
        echo "✅ Bot avviato in background"
        echo "📋 Log: tail -f $LOG_FILE"
        ;;
    stop)
        stop_all
        log "🛑 Bot arrestato"
        echo "🛑 Bot arrestato"
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    status)
        if [ -f "$PID_FILE" ] && kill -0 "$(cat $PID_FILE)" 2>/dev/null; then
            echo "✅ Server attivo (PID: $(cat $PID_FILE))"
        else
            echo "❌ Server spento"
        fi
        
        if pgrep -f "localtunnel" > /dev/null; then
            echo "✅ Tunnel attivo"
        else
            echo "❌ Tunnel spento"
        fi
        ;;
    run|watchdog)
        # Modalità watchdog - controlla ogni 30 secondi
        log "👁️ Watchdog avviato"
        while true; do
            if ! check_health; then
                log "🔄 Riavvio automatico..."
                stop_all
                start_server
                start_tunnel
            fi
            sleep 30
        done
        ;;
    *)
        echo "Uso: $0 {start|stop|restart|status|watchdog}"
        exit 1
        ;;
esac
