from fastapi import APIRouter, HTTPException, Request
from app.services.orchestrator import ServiceOrchestrator
from app.core.logging import get_logger

logger = get_logger("webhook")
router = APIRouter()

# Global orchestrator instance
orchestrator = ServiceOrchestrator()


@router.post("/telegram")
async def telegram_webhook(update: dict):
    """
    Handle incoming Telegram webhook updates
    """
    if "message" not in update:
        return {"ok": True}
    
    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    
    logger.info(f"Received command from chat {chat_id}: {text}")
    
    # Parse command - Destiny 1 Only
    if text.startswith("/d1_find "):
        gamertag = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_find_player(chat_id, gamertag)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_activities "):
        gamertag = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_activity_history(chat_id, gamertag)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_raid "):
        gamertag = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_raid(chat_id, gamertag)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_inventory "):
        gamertag = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_inventory(chat_id, gamertag)
        return {"ok": True, "result": result}
    
    elif text == "/d1_vendors":
        result = await orchestrator.handle_d1_vendors(chat_id)
        return {"ok": True, "result": result}
    
    elif text == "/d1_pvp":
        result = await orchestrator.handle_d1_pvp(chat_id)
        return {"ok": True, "result": result}
    
    elif text == "/d1_assalti":
        result = await orchestrator.handle_d1_assalti(chat_id)
        return {"ok": True, "result": result}
    
    elif text == "/d1_anziani":
        result = await orchestrator.handle_d1_elders(chat_id)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_stats "):
        gamertag = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_stats(chat_id, gamertag)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_clan "):
        clan_name = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_clan(chat_id, clan_name)
        return {"ok": True, "result": result}
    
    elif text == "/d1_leaderboard":
        result = await orchestrator.handle_d1_leaderboard(chat_id)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_speedruns "):
        gamertag = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_speedruns(chat_id, gamertag)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_clan_ranking "):
        clan_name = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_clan_ranking(chat_id, clan_name)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_global_leaderboard "):
        category = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_global_leaderboard(chat_id, category)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_loadout "):
        parts = text.split(" ", 2)
        if len(parts) >= 3:
            gamertag = parts[1].strip()
            stats_wanted = parts[2].strip()
            result = await orchestrator.handle_d1_loadout(chat_id, gamertag, stats_wanted)
        else:
            result = await orchestrator.handle_d1_loadout_help(chat_id)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_optimize "):
        parts = text.split(" ", 2)
        if len(parts) >= 3:
            gamertag = parts[1].strip()
            target_stats = parts[2].strip()
            result = await orchestrator.handle_d1_optimize(chat_id, gamertag, target_stats)
        else:
            result = await orchestrator.handle_d1_optimize_help(chat_id)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_inventory_advanced "):
        gamertag = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_inventory_advanced(chat_id, gamertag)
        return {"ok": True, "result": result}
    
    elif text == "/d1_equip_check":
        result = await orchestrator.handle_d1_equip_check(chat_id)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_equip "):
        parts = text.split(" ", 2)
        if len(parts) >= 3:
            gamertag = parts[1].strip()
            item_name = parts[2].strip()
            result = await orchestrator.handle_d1_equip(chat_id, gamertag, item_name)
        else:
            result = await orchestrator.handle_d1_equip_help(chat_id)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_events"):
        planet = None
        if text.startswith("/d1_events "):
            planet = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_events(chat_id, planet)
        return {"ok": True, "result": result}
    
    elif text.startswith("/d1_events_subscribe"):
        planets = None
        if text.startswith("/d1_events_subscribe "):
            planets = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_d1_events_subscribe(chat_id, planets)
        return {"ok": True, "result": result}
    
    elif text == "/d1_events_unsubscribe":
        result = await orchestrator.handle_d1_events_unsubscribe(chat_id)
        return {"ok": True, "result": result}
    
    elif text == "/d1_events_status":
        result = await orchestrator.handle_d1_events_status(chat_id)
        return {"ok": True, "result": result}
    
    elif text == "/d1_token":
        result = await orchestrator.handle_d1_token_status(chat_id)
        return {"ok": True, "result": result}
    
    elif text.startswith("/auth_code "):
        auth_code = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_oauth_code(chat_id, auth_code)
        return {"ok": True, "result": result}
    
    elif text == "/auth":
        from app.services.oauth_handler import get_oauth_handler
        oauth = get_oauth_handler()
        auth_url = oauth.get_auth_url(str(chat_id))
        await orchestrator.telegram.send_message(
            chat_id,
            f"🔐 <b>Autenticazione Bungie.net</b>\n\n"
            f"1️⃣ Clicca il link:\n<a href='{auth_url}'>Autenticati su Bungie.net</a>\n\n"
            f"2️⃣ Autorizza l'app\n\n"
            f"3️⃣ Copia il codice di autorizzazione\n\n"
            f"4️⃣ Incolla qui con:\n"
            f"<code>/auth_code TUO_CODICE</code>\n\n"
            f"<i>⚡ Il codice scade dopo 10 minuti</i>"
        )
        return {"ok": True, "auth_url": auth_url}
    
    elif text == "/d1_warsat":
        result = await orchestrator.handle_d1_warsat(chat_id)
        return {"ok": True, "result": result}
    
    elif text == "/start":
        from app.services.adapters import TelegramAdapter
        telegram = TelegramAdapter()
        await telegram.send_message(
            chat_id,
            "🌌 <b>DESTINY 1</b>\n"
            "Legacy Guardian Network\n\n"
            "👋 <b>Ehi Guardiano, sei ancora vivo?</b>\n\n"
            "Dopo tutti questi anni pensavamo fossi passato a Destiny 2… o peggio, a Warframe!\n"
            "Invece eccoti qui, a rispolverare il vecchio server.\n\n"
            "🛡️ <b>La Luce si sta spegnendo… ma tu hai risposto.</b>\n\n"
            "Nel buio del Collasso e del Lungo Silenzio, pochi segnali sono rimasti.\n"
            "Tu sei uno di loro.\n\n"
            "⚔️ <b>Cosa puoi fare qui:</b>\n"
            "• Cercare qualsiasi Guardiano ancora connesso\n"
            "• Rivivere le Incursioni leggendarie (e piangere sui drop)\n"
            "• Controllare il tuo vecchio Inventario level 34\n"
            "• Seguire Xûr che ti vende sempre la stessa cosa\n"
            "• Morire per colpa di un Vex mitico\n\n"
            "🤣 <b>Forza boomer, non deluderci.</b>\n\n"
            "Pronto a rivivere il dolore e la gloria?\n"
            "Digita <code>/d1_find &lt;gamertag&gt;</code> per iniziare\n"
            "o <code>/help</code> per vedere i comandi (senza morire di nostalgia).\n\n"
            "<i>🌌 Destiny 1 • Legacy Edition • \"Gjallarhorn quando?\"</i>"
        )
        return {"ok": True}
    
    elif text == "/help":
        from app.services.adapters import TelegramAdapter
        telegram = TelegramAdapter()
        await telegram.send_message(
            chat_id,
            "🌌 <b>DESTINY 1</b>\n"
            "Legacy Guardian Network\n\n"
            "🔍 <b>Comandi Operativi</b>\n\n"
            "👤 <b>Ricerca Guardiani</b>\n"
            "• <code>/d1_find &lt;gamertag&gt;</code>\n"
            "  Localizza un Guardiano nella rete.\n"
            "  <i>Attenzione: il gamertag è case-sensitive</i>\n\n"
            "📜 <b>Attività Recenti</b>\n"
            "• <code>/d1_activities &lt;gamertag&gt;</code>\n"
            "  Registra le operazioni recenti (PvE • PvP • Missioni)\n\n"
            "🏰 <b>Incursioni (Raid)</b>\n"
            "• <code>/d1_raid &lt;gamertag&gt;</code>\n"
            "  Archivio completo delle Incursioni completate\n\n"
            "🎒 <b>Inventario</b>\n"
            "• <code>/d1_inventory &lt;gamertag&gt;</code>\n"
            "  Visualizza equipaggiamento, armi primarie, secondarie ed esotiche\n\n"
            "🛒 <b>Xûr & Settimanali</b>\n"
            "• <code>/d1_xur</code>\n"
            "  Posizione dell'Agente delle Nove, Nightfall, Settimanale e Trials\n\n"
            "⚔️ <b>Crucible & PvP</b>\n"
            "• <code>/d1_pvp</code>\n"
            "  Situazione attuale del Crucible e Trials of Osiris\n\n"
            "⚡ <b>Assalti</b>\n"
            "• <code>/d1_assalti</code>\n"
            "  Elenco completo degli Assalti disponibili\n\n"
            "🏆 <b>Sfida degli Anziani</b>\n"
            "• <code>/d1_anziani</code>\n"
            "  Dettagli sulla Sfida degli Anziani\n\n"
            "� <b>Statistiche Avanzate</b>\n"
            "• <code>/d1_stats &lt;gamertag&gt;</code>\n"
            "  K/D, ore di gioco, raid completati\n\n"
            "🏆 <b>Classifiche</b>\n"
            "• <code>/d1_leaderboard</code>\n"
            "  Migliori giocatori per categoria\n\n"
            "👥 <b>Ricerca Clan</b>\n"
            "• <code>/d1_clan &lt;nome_clan&gt;</code>\n"
            "  Statistiche raid per clan\n\n"
            "⚡ <b>Speedruns & Pro</b>\n"
            "• <code>/d1_speedruns &lt;gamertag&gt;</code>\n"
            "  Tempi migliori e classifiche speedrun\n\n"
            "🏆 <b>Classifiche Globali</b>\n"
            "• <code>/d1_global_leaderboard raids|speedruns|kd</code>\n"
            "  Top 100 mondiali per categoria\n\n"
            "👥 <b>Clan Rankings</b>\n"
            "• <code>/d1_clan_ranking &lt;nome_clan&gt;</code>\n"
            "  Classifica clan competitiva\n\n"
            "🔔 <b>Notifiche Eventi</b>\n"
            "• <code>/d1_events</code> - Visualizza eventi pubblici imminenti\n"
            "• <code>/d1_events Terra</code> - Filtra per pianeta\n"
            "• <code>/d1_events_subscribe</code> - Iscriviti alle notifiche\n"
            "• <code>/d1_events_subscribe Terra, Luna</code> - Solo specifici pianeti\n"
            "• <code>/d1_events_unsubscribe</code> - Disiscriviti\n"
            "• <code>/d1_events_status</code> - Stato iscrizione\n\n"
            "🎯 <b>Loadout Optimizer</b>\n"
            "• <code>/d1_loadout &lt;gamertag&gt; &lt;stats&gt;</code>\n"
            "  Trova il set armature perfetto per le statistiche desiderate\n"
            "• <code>/d1_optimize &lt;gamertag&gt; &lt;target&gt;</code>\n"
            "  Ottimizzazione avanzata con raccomandazioni\n\n"
            "📦 <b>Inventario Avanzato</b>\n"
            "• <code>/d1_inventory_advanced &lt;gamertag&gt;</code>\n"
            "  Gestione completa inventario con categorie e filtri\n\n"
            "🔐 <b>Autenticazione</b>\n"
            "• <code>/auth</code> - Autenticazione automatica\n"
            "• <code>/auth_code &lt;codice&gt;</code> - Autenticazione manuale\n"
            "• <code>/oauth_status</code> - Stato token OAuth\n\n"
            "⚠️ <b>Note Operative</b>\n"
            "• I gamertag sono case-sensitive\n"
            "• La ricerca avviene su PlayStation e Xbox\n"
            "• I dati sono cached per 5-10 minuti\n\n"
            "<i>💡 Esempio: <code>/d1_find Sporty_FTW</code></i>\n\n"
            "<i>🌌 Destiny 1 • Legacy Edition • Ultra Premium</i>"
        )
        return {"ok": True}
    
    elif text.startswith("/auth_code "):
        auth_code = text.split(" ", 1)[1].strip()
        result = await orchestrator.handle_oauth_code(chat_id, auth_code)
        return {"ok": True, "result": result}
    
    elif text == "/oauth_status":
        result = await orchestrator.handle_oauth_status(chat_id)
        return {"ok": True, "result": result}
    
    elif text == "/auth":
        # Generate auto-auth URL with chat_id
        from app.services.adapters import TelegramAdapter
        from app.services.oauth_handler import get_oauth_handler
        
        try:
            oauth = get_oauth_handler()
            state = f"auto_auth_{chat_id}"
            auth_url = oauth.get_auth_url(state=state)
            
            telegram = TelegramAdapter()
            await telegram.send_message(
                chat_id,
                f"🔐 <b>Autenticazione Automatica</b>\n\n"
                f"1️⃣ Clicca il link qui sotto\n"
                f"2️⃣ Accedi con il tuo account Bungie\n" 
                f"3️⃣ Autorizza l'applicazione\n"
                f"✅ Il codice verrà processato AUTOMATICAMENTE!\n\n"
                f"<a href='{auth_url}'>👉 Clicca qui per autorizzare</a>\n\n"
                f"⏰ Il link è valido per pochi minuti"
            )
            return {"ok": True, "auto_auth": True}
        except Exception as e:
            logger.error(f"Error generating auto-auth URL: {e}")
            return {"ok": False, "error": str(e)}
    
    else:
        # Unknown command
        from app.services.adapters import TelegramAdapter
        telegram = TelegramAdapter()
        await telegram.send_message(
            chat_id,
            "❓ Comando non riconosciuto.\n\n"
            "Usa <code>/help</code> per vedere tutti i comandi disponibili."
        )
        return {"ok": True}


async def init_orchestrator():
    """Initialize orchestrator on startup"""
    await orchestrator.initialize()


async def shutdown_orchestrator():
    """Shutdown orchestrator on cleanup"""
    await orchestrator.shutdown()
