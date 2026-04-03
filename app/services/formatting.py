"""
Premium Message Formatters for Destiny 1 & Destiny 2 Telegram Bot
Ultra Premium Version + Colori Classi + Icone Equipaggiamento + Fazioni + Ranghi + Progress Bar Reputazione
"""

import html
from typing import List, Dict, Optional, Any


class TextStyle:
    """Utility per stili di testo premium"""
    @staticmethod
    def bold(text: str) -> str:
        return f"<b>{text}</b>"
    
    @staticmethod
    def code(text: str) -> str:
        return f"<code>{text}</code>"
    
    @staticmethod
    def italic(text: str) -> str:
        return f"<i>{text}</i>"


class ClassStyle:
    """Stili e colori per le classi"""
    CLASS_INFO = {
        0: {"emoji": "🟥", "icon": "🛡️", "name": "Titano"},
        1: {"emoji": "🟨", "icon": "🏹", "name": "Cacciatore"},
        2: {"emoji": "🟦", "icon": "🔮", "name": "Stregone"},
    }
    
    @staticmethod
    def get(class_type: int):
        return ClassStyle.CLASS_INFO.get(class_type, {"emoji": "⚪", "icon": "❔", "name": "Sconosciuto"})
    
    @staticmethod
    def format(class_type: int, level: Optional[int] = None, light: Optional[int] = None) -> str:
        info = ClassStyle.get(class_type)
        base = f"{info['emoji']} {TextStyle.bold(info['name'])}"
        if level is not None and light is not None:
            return f"{base} • Livello {level} • Luce {light}"
        elif level is not None:
            return f"{base} • Livello {level}"
        return base


class FactionStyle:
    """Fazioni con ranghi, icone e Progress Bar per la reputazione"""
    
    FACTION_INFO = {
        "Vanguard":      {"emoji": "🔵", "name": "Avanguardia",      "icon": "🛡️"},
        "Crucible":      {"emoji": "🔴", "name": "Crogiolo",         "icon": "⚔️"},
        "Dead Orbit":    {"emoji": "⚫", "name": "Dead Orbit",        "icon": "☠️"},
        "Future War Cult":{"emoji": "🟢", "name": "Future War Cult",  "icon": "🌌"},
        "New Monarchy":  {"emoji": "🟨", "name": "New Monarchy",      "icon": "👑"},
        "Iron Banner":   {"emoji": "🟠", "name": "Iron Banner",       "icon": "🏆"},
        "Trials of Osiris":{"emoji": "⚪", "name": "Prove di Osiride", "icon": "🏛️"},
        "Xur":           {"emoji": "🌌", "name": "Xûr",               "icon": "👳‍♂️"},
        "Nine":          {"emoji": "🌌", "name": "I Nove",            "icon": "🌌"},
    }

    # Icone progressive per i ranghi
    RANK_ICONS = {
        0: "⚪", 1: "🥉", 2: "🥈", 3: "🥇", 4: "🏅", 5: "🌟", 6: "👑", 7: "✨"
    }

    RANK_NAMES = {
        0: "Nessuna reputazione",
        1: "Rango 1",
        2: "Rango 2",
        3: "Rango 3",
        4: "Rango 4",
        5: "Rango 5 — Leggenda",
        6: "Alleato Supremo",
        7: "Leggenda Vivente",
    }

    @staticmethod
    def get(faction_name: str):
        key = str(faction_name).strip().title()
        for k, v in FactionStyle.FACTION_INFO.items():
            if k.lower() in key.lower() or key.lower() in k.lower():
                return v
        return {"emoji": "🏷️", "name": faction_name, "icon": "🏷️"}

    @staticmethod
    def get_rank_icon(rank: int) -> str:
        rank = max(0, min(rank, 7))
        return FactionStyle.RANK_ICONS.get(rank, "🌟")

    @staticmethod
    def get_rank_name(rank: int) -> str:
        return FactionStyle.RANK_NAMES.get(rank, f"Rango {rank}")

    @staticmethod
    def reputation_progress_bar(current_rep: int, next_rank_rep: int = 5000, width: int = 10) -> str:
        """Crea una progress bar testuale elegante"""
        if next_rank_rep <= 0:
            return "█" * width
        
        progress = min(current_rep / next_rank_rep, 1.0)
        filled = int(progress * width)
        empty = width - filled
        
        bar = "█" * filled + "░" * empty
        percentage = int(progress * 100)
        
        return f"{bar} {percentage}%"

    @staticmethod
    def format(
        faction_name: str,
        rank: Optional[int] = None,
        reputation: Optional[int] = None,
        next_rank_rep: int = 5000
    ) -> str:
        """Formattazione completa della fazione con progress bar"""
        info = FactionStyle.get(faction_name)
        
        if rank is None:
            return f"{info['emoji']} {TextStyle.bold(info['name'])}"
        
        rank_icon = FactionStyle.get_rank_icon(rank)
        rank_name = FactionStyle.get_rank_name(rank)
        
        line = f"{info['emoji']} {TextStyle.bold(info['name'])} {rank_icon} {rank_name}"
        
        if reputation is not None:
            bar = FactionStyle.reputation_progress_bar(reputation, next_rank_rep)
            line += f"\n   ├ Reputazione: {reputation:,} / {next_rank_rep:,}"
            line += f"\n   └ Progress: {bar}"
        
        return line


class GearStyle:
    """Icone Premium per Equipaggiamento"""
    RARITY = {"Exotic": "🌟", "Legendary": "🟡", "Rare": "🔵", "Uncommon": "🟢", "Common": "⚪"}
    
    WEAPON_TYPE = {
        "Auto Rifle": "🔫", "Pulse Rifle": "🔫", "Scout Rifle": "🏹", "Hand Cannon": "🔫",
        "Shotgun": "🔫", "Sniper Rifle": "🎯", "Fusion Rifle": "⚡", "Rocket Launcher": "🚀",
        "Sword": "⚔️", "Bow": "🏹",
    }
    
    @staticmethod
    def get_rarity_icon(rarity: str = "Legendary") -> str:
        return GearStyle.RARITY.get(rarity, "📦")
    
    @staticmethod
    def legendary_item(name: str, item_type: str = "weapon", rarity: str = "Legendary", details: Optional[str] = None) -> str:
        icon = GearStyle.get_rarity_icon(rarity)
        sub_icon = GearStyle.WEAPON_TYPE.get(details, "🔫") if item_type == "weapon" else "🛡️"
        return f"{icon} {sub_icon} {TextStyle.bold(GearStyle._escape(name))}"
    
    @staticmethod
    def _escape(text: Any) -> str:
        return html.escape(str(text)) if text else ""


class Destiny1Formatter:
    """Formatter Ultra Premium per Destiny 1"""

    @staticmethod
    def _escape(text: Any) -> str:
        return html.escape(str(text)) if text else ""

    @staticmethod
    def player_found(
        display_name: str,
        membership_id: str,
        platform: str = "PlayStation",
        characters: Optional[List[Dict]] = None,
        faction: Optional[str] = None,
        faction_rank: Optional[int] = None,
        reputation: Optional[int] = None
    ) -> str:
        lines = [
            "🎮 <b>Giocatore Destiny 1 Trovato</b>\n",
            f"👤 {TextStyle.bold(Destiny1Formatter._escape(display_name))}",
            f"🆔 {TextStyle.code(membership_id)}",
            f"🎮 Piattaforma: {platform}\n"
        ]

        if faction:
            lines.append(FactionStyle.format(faction, faction_rank, reputation))

        if characters:
            lines.append(f"\n👥 {TextStyle.bold(f'Personaggi ({len(characters)})')}")
            for i, char in enumerate(characters, 1):
                class_type = char.get('classType', 0)
                level = char.get('level', 'N/A')
                light = char.get('light', 'N/A')
                lines.append(f"   {i}. {ClassStyle.format(class_type, level, light)}")

        lines.append("\n" + TextStyle.italic("Destiny 1 • Legacy Edition • PlayStation Network"))
        return "\n".join(lines)

    @staticmethod
    def player_not_found(gamertag: str) -> str:
        """Format player not found message"""
        return f"🔍 Giocatore D1 '<b>{gamertag}</b>' non trovato su nessuna piattaforma."

    @staticmethod
    def inventory_summary(
        display_name: str,
        class_type: int,
        char_items: int,
        vault_items: int,
        faction: Optional[str] = None,
        faction_rank: Optional[int] = None,
        reputation: Optional[int] = None,
        total_power: Optional[int] = None
    ) -> str:
        class_line = ClassStyle.format(class_type)
        total = char_items + vault_items
        power_text = f" • Potere ≈ {total_power}" if total_power else ""

        lines = [
            f"🎒 <b>Inventario Destiny 1</b>",
            f"👤 {TextStyle.bold(Destiny1Formatter._escape(display_name))}",
            f"{class_line}{power_text}"
        ]

        if faction:
            lines.append(FactionStyle.format(faction, faction_rank, reputation))

        lines.extend([
            "",
            f"{GearStyle.get_rarity_icon('Legendary')} Oggetti sul personaggio: {TextStyle.bold(str(char_items))}",
            f"🏦 Oggetti nel Vault:     {TextStyle.bold(str(vault_items))}",
            f"📊 Totale stimato:        {TextStyle.bold(str(total))}\n",
            TextStyle.italic("Destiny 1 • Legacy Edition")
        ])

        return "\n".join(lines)

    @staticmethod
    def raid_header(
        display_name: str,
        class_type: int,
        character_level: int,
        faction: Optional[str] = None,
        faction_rank: Optional[int] = None,
        reputation: Optional[int] = None
    ) -> str:
        """Format raid history header with premium styling"""
        class_info = ClassStyle.format(class_type)

        lines = [
            f"⚔️ <b>Storico Raid Destiny 1</b>",
            f"━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"👤 <b>{Destiny1Formatter._escape(display_name)}</b>",
            f"🛡️ {class_info} • Livello {character_level}",
        ]

        if faction:
            lines.append(FactionStyle.format(faction, faction_rank, reputation))

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def raid_entry(name: str, completions: int, best_time: str, kills: int) -> str:
        """Format single raid entry with premium styling"""
        time_str = best_time if best_time and best_time != "N/A" else "⏱️ Nessun record"
        return (
            f"🏆 <b>{name}</b>\n"
            f"   ├ ✅ Completamenti: <b>{int(completions)}</b>\n"
            f"   ├ ⏱️ Record: {time_str}\n"
            f"   └ ⚔️ Nemici: <b>{int(kills):,}</b>"
        )

    @staticmethod
    def raid_footer(total_completions: int, best_raid: str, num_raids: int) -> str:
        """Format raid statistics footer with premium styling"""
        best_raid_escaped = Destiny1Formatter._escape(best_raid) if best_raid else 'N/A'
        return (
            f"\n📊 <b>Riepilogo Attività</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"   ├ 🎯 Totali: <b>{total_completions}</b>\n"
            f"   ├ ⭐ Preferito: {best_raid_escaped}\n"
            f"   └ 🎮 Diverse: <b>{num_raids}</b> raid/assalti\n\n"
            f"<i>🌌 Destiny 1 • Legacy Edition</i>"
        )

    @staticmethod
    def xur_available(location: Optional[str] = None) -> str:
        """Format Xur available message with mysterious Nine theme"""
        loc = f"\n📍 <b>Posizione:</b> {location}" if location else "\n📍 <b>Torre o Riva</b>"
        return (
            "🌌 <b>Xûr, Agente dei Nove</b>\n\n"
            "👳‍♂️ <i>\"Ho ciò che ti serve, Guardiano...\"</i>\n\n"
            "✅ <b>È arrivato!</b>"
            f"{loc}\n"
            "🕒 Disponibile fino a: <b>Martedì 18:00 CET</b>\n\n"
            "<i>🌌 I Nove ti osservano...</i>\n"
            "<i>⚡ Esotici, Consumabili e Misteri</i>"
        )

    @staticmethod
    def xur_not_available() -> str:
        """Format Xur not available message with mysterious Nine theme and countdown"""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        current_day = now.weekday()
        current_hour = now.hour
        
        # Calculate next Friday 18:00 CET (17:00 UTC)
        days_until_friday = (4 - current_day) % 7
        if days_until_friday == 0 and current_hour >= 17:
            days_until_friday = 7
        
        next_xur = now + timedelta(days=days_until_friday)
        next_xur = next_xur.replace(hour=17, minute=0, second=0, microsecond=0)
        
        # Calculate countdown
        time_until = next_xur - now
        days = time_until.days
        hours, remainder = divmod(time_until.seconds, 3600)
        minutes = remainder // 60
        
        if days > 0:
            countdown = f"{days}g {hours}h {minutes}m"
        elif hours > 0:
            countdown = f"{hours}h {minutes}m"
        else:
            countdown = f"{minutes}m"
        
        return (
            f"🌌 <b>Xûr, Agente dei Nove</b>\n\n"
            f"👳‍♂️ <i>\"Non sono i miei possessi che cerco...\"</i>\n\n"
            f"😔 <b>Non disponibile al momento</b>\n"
            f"⏳ <b>Arriva tra:</b> <code>{countdown}</code>\n"
            f"� Venerdì 18:00 CET\n\n"
            f"<i>🌌 I Nove osservano... aspettano...</i>\n"
            f"<i>⚡ Porta Strane Monete e Leggende</i>"
        )

    @staticmethod
    def nightfall_info(hash_value: str, name: str) -> str:
        """Format nightfall info with details and rewards"""
        nightfalls = {
            "2693077237": {
                "name": "L'Eco del Vuoto",
                "description": "Affronta i Vex nelle loro rovine temporali",
                "burn": "Solar Burn",
                "rewards": ["🔫 Armi Esotiche", "💎 Materiali Rari", "⚡ Energia Leggendaria"],
                "difficulty": "280 Light"
            },
            "2680821749": {
                "name": "Città del Vetro", 
                "description": "Esplora la città perduta dei Vex",
                "burn": "Arc Burn",
                "rewards": ["🔫 Armi Esotiche", "💎 Materiali Rari", "🛡️ Armature Leggendarie"],
                "difficulty": "280 Light"
            },
            "3848655169": {
                "name": "Desolazione",
                "description": "Sopravvivi alla desolazione della Luna",
                "burn": "Void Burn", 
                "rewards": ["🔫 Armi Esotiche", "💎 Materiali Rari", "🌙 Materiali Lunari"],
                "difficulty": "280 Light"
            },
            "4107311651": {
                "name": "Tomba di Oryx",
                "description": "Entra nella tomba del Re dei Hive",
                "burn": "Solar Burn",
                "rewards": ["🔫 Armi Esotiche", "💎 Materiali Rari", "👑 Simboli del Re"],
                "difficulty": "320 Light"
            },
            "2082069811": {
                "name": "Dreadnaught",
                "description": "Abborda la nave di Oryx",
                "burn": "Arc Burn",
                "rewards": ["🔫 Armi Esotiche", "💎 Materiali Rari", "⚓ Artefatti del Dreadnaught"],
                "difficulty": "320 Light"
            }
        }
        
        info = nightfalls.get(hash_value, {
            "name": "Sconosciuto",
            "description": "Nightfall misterioso",
            "burn": "N/A",
            "rewards": ["🔫 Arme Esotiche", "💎 Materiali Rari"],
            "difficulty": "280 Light"
        })
        
        lines = [
            f"🌙 <b>Nightfall Settimanale</b>",
            f"━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📋 <b>{info['name']}</b>",
            f"🆔 Hash: <code>{hash_value}</code>",
            f"📖 <i>{info['description']}</i>",
            "",
            f"⚡ <b>Dettagli:</b>",
            f"   🔥 Burn: <code>{info['burn']}</code>",
            f"   💪 Difficoltà: <code>{info['difficulty']}</code>",
            "",
            f"🎁 <b>Ricompense Possibili:</b>"
        ]
        
        for reward in info['rewards']:
            lines.append(f"   • {reward}")
        
        lines.extend([
            "",
            "<i>💡 Consigli: Usa armi elementali corrispondenti al Burn per bonus danni!</i>",
            "",
            "<i>🌌 Destiny 1 • Legacy Edition</i>"
        ])
        
        return "\n".join(lines)

    @staticmethod
    def error(error_msg: str = "Si è verificato un errore imprevisto") -> str:
        return f"❌ <b>Errore</b>\n\n{Destiny1Formatter._escape(error_msg)}"

    @staticmethod
    def activities_deprecated(display_name: str, character_class: str, gamertag: str) -> str:
        """Format activities endpoint deprecated message"""
        return (
            f"📊 <b>Storico D1 di {display_name}</b>\n"
            f"🛡️ Personaggio: {character_class}\n\n"
            f"⚠️ <b>Endpoint ActivityHistory non disponibile</b>\n"
            f"Bungie ha deprecato le API attività recenti per Destiny 1.\n\n"
            f"💡 <b>Alternative:</b>\n"
            f"• <code>/d1_raid {gamertag}</code> - Storico raid\n"
            f"• <code>/d1_inventory {gamertag}</code> - Inventario\n"
            f"• <code>/d1_find {gamertag}</code> - Info personaggio\n\n"
        )


# =============================================================================
# Destiny 2 e OAuth (aggiornati)
# =============================================================================

class Destiny2Formatter:
    @staticmethod
    def player_found(
        display_name: str,
        membership_id: str,
        platform: str = "Steam",
        faction: Optional[str] = None,
        faction_rank: Optional[int] = None,
        reputation: Optional[int] = None
    ) -> str:
        lines = [
            f"🎮 <b>Giocatore Destiny 2 Trovato</b>\n",
            f"👤 {TextStyle.bold(display_name)}",
            f"🆔 {TextStyle.code(membership_id)}",
            f"🔗 Piattaforma: {platform}"
        ]
        if faction:
            lines.append(FactionStyle.format(faction, faction_rank, reputation))
        lines.append("\n" + TextStyle.italic("Pronto per tutti i comandi D2"))
        return "\n".join(lines)

    @staticmethod
    def player_not_found(gamertag: str, platform: str = "Steam") -> str:
        """Format player not found message"""
        return f"🔍 Giocatore '<b>{gamertag}</b>' non trovato su {platform}."

    @staticmethod
    def error_message(error: str) -> str:
        """Format error message"""
        return f"❌ Errore: {error}"

    @staticmethod
    def internal_error() -> str:
        """Format internal error message"""
        return "❌ Errore interno durante l'elaborazione."


class OAuthFormatter:
    @staticmethod
    def auth_success() -> str:
        return (
            "🔐 <b>Autenticazione Bungie Completata con Successo!</b>\n\n"
            "✅ Token salvato in modo sicuro\n"
            "🌟 Accesso premium sbloccato\n"
            "🔄 Refresh automatico attivo\n\n"
            f"{TextStyle.italic('Ora puoi visualizzare equipaggiamento e reputazione fazioni')}"
        )

    @staticmethod
    def token_status(active: bool, time_remaining: int = 0, storage_type: str = "Redis") -> str:
        if not active:
            return "⏰ <b>Token scaduto</b>. Usa <code>/auth</code> per riautenticarti."
        
        hours = time_remaining // 3600
        minutes = (time_remaining % 3600) // 60
        return (
            f"🔐 <b>Stato Sessione OAuth</b>\n\n"
            f"✅ Token: {TextStyle.bold('ATTIVO')}\n"
            f"⏰ Rimanente: {hours}h {minutes}m\n"
            f"🔒 Archiviazione: {storage_type}\n"
            f"🔄 Refresh automatico: {TextStyle.bold('ATTIVO')}"
        )
    
    @staticmethod
    def auth_failed(error: str = None) -> str:
        """Format authentication failed message"""
        msg = "❌ <b>Autenticazione Fallita</b>\n\n"
        if error:
            msg += f"Errore: {error}\n\n"
        msg += "💡 Prova con <code>/auth</code> per riautenticarti."
        return msg
    
    @staticmethod
    def token_refreshed() -> str:
        """Format token refreshed message"""
        return "🔄 <b>Token OAuth aggiornato automaticamente!</b>"
    
    @staticmethod
    def token_expired() -> str:
        """Format token expired message"""
        return "⏰ <b>Token scaduto</b>. Usa <code>/auth</code> per riautenticarti."
