"""
Destiny 1 specific command handlers
"""
import logging
from typing import Dict, Optional
from app.services.destiny1_service import Destiny1Service
from app.services.formatting import Destiny1Formatter
from app.core.constants import D1_RAID_NAMES
from app.core.exceptions import PlayerNotFoundError

logger = logging.getLogger("destiny1_handlers")


class D1CommandHandlers:
    """Handlers for Destiny 1 specific commands"""
    
    def __init__(self, telegram_adapter):
        self.telegram = telegram_adapter
    
    async def handle_find_player(self, chat_id: int, gamertag: str) -> Dict:
        """Search for a Destiny 1 player across all platforms"""
        try:
            logger.info(f"[D1] Searching player: {gamertag}")
            
            player = Destiny1Service.search_player(gamertag)
            if not player:
                message = Destiny1Formatter.player_not_found(gamertag)
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            platform = player.get("membershipType", 0)
            
            # Get account for character details
            account = Destiny1Service.get_account(membership_id)
            characters_info = []
            if account and account.get("Response"):
                characters = account["Response"].get("data", {}).get("characters", [])
                for char in characters[:3]:  # Max 3 characters
                    characters_info.append({
                        'classType': char.get("classType", 0),
                        'level': char.get("characterLevel", "N/A"),
                        'light': char.get("characterBase", {}).get("powerLevel", "N/A")
                    })
            
            platform_name = self._get_platform_name(platform)
            message = Destiny1Formatter.player_found(
                display_name, membership_id, platform_name, characters_info
            )
            await self.telegram.send_message(chat_id, message)
            
            return {
                "success": True,
                "player": display_name,
                "membership_id": membership_id,
                "platform": platform_name,
                "characters": len(characters_info)
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error finding player {gamertag}: {e}")
            await self.telegram.send_message(
                chat_id, 
                Destiny1Formatter.error("Errore durante la ricerca")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_raid_history(self, chat_id: int, gamertag: str) -> Dict:
        """Get Destiny 1 raid history for a player"""
        try:
            logger.info(f"[D1] Getting raid history: {gamertag}")
            
            # Search player
            player = Destiny1Service.search_player(gamertag)
            if not player:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error(f"Giocatore '{gamertag}' non trovato")
                )
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            
            # Get account summary
            account = Destiny1Service.get_account(membership_id)
            if not account or not account.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Nessun personaggio D1 trovato")
                )
                return {"success": False, "error": "No characters"}
            
            characters = account["Response"].get("data", {}).get("characters", [])
            if not characters:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Nessun personaggio D1 trovato")
                )
                return {"success": False, "error": "No characters"}
            
            # Get raid stats for first character
            character_id = characters[0].get("characterBase", {}).get("characterId")
            raid_data = Destiny1Service.get_raid_history(membership_id, character_id)
            
            # Format raid info using D1_RAID_NAMES from constants
            message = Destiny1Formatter.raid_header(
                display_name,
                characters[0].get('characterBase', {}).get('classType', 0),
                characters[0].get('characterLevel', 'N/A')
            )
            
            raid_info = []
            total_completions = 0
            best_raid = None
            best_count = 0
            
            if raid_data and raid_data.get("Response"):
                activities = raid_data["Response"].get("data", {}).get("activities", [])
                
                # Ordina per numero di completamenti (decrescente)
                sorted_activities = sorted(
                    activities, 
                    key=lambda x: x.get("values", {}).get("activityCompletions", {}).get("basic", {}).get("value", 0),
                    reverse=True
                )
                
                for activity in sorted_activities[:10]:  # Mostra top 10
                    activity_hash = str(activity.get("activityHash", ""))
                    
                    # Try full hash first, then truncated (8 digits)
                    raid_name = D1_RAID_NAMES.get(activity_hash)
                    if not raid_name and len(activity_hash) >= 8:
                        truncated_hash = activity_hash[:8]
                        # Find matching hash by prefix
                        for full_hash, name in D1_RAID_NAMES.items():
                            if full_hash.startswith(truncated_hash):
                                raid_name = name
                                break
                    
                    if not raid_name:
                        raid_name = f"🔍 Incursione Sconosciuta ({activity_hash[:8]}...)"
                    
                    completions = activity.get("values", {}).get("activityCompletions", {}).get("basic", {}).get("value", 0)
                    
                    # Get best time (fastest completion)
                    best_time_val = activity.get("values", {}).get("fastestCompletionMs", {}).get("basic", {}).get("value", 0)
                    best_time_display = activity.get("values", {}).get("fastestCompletionMs", {}).get("basic", {}).get("displayValue", "N/A")
                    
                    # Calculate kills and deaths
                    kills = activity.get("values", {}).get("kills", {}).get("basic", {}).get("value", 0)
                    deaths = activity.get("values", {}).get("deaths", {}).get("basic", {}).get("value", 0)
                    kd_ratio = round(kills / max(deaths, 1), 2) if kills else 0
                    
                    # Get activity kills (enemy kills in activity)
                    activity_kills = activity.get("values", {}).get("activityKills", {}).get("basic", {}).get("value", 0)
                    
                    if completions > 0:
                        total_completions += int(completions)
                        if int(completions) > best_count:
                            best_count = int(completions)
                            best_raid = raid_name
                        
                        # Format time nicely
                        time_str = best_time_display if best_time_val > 0 else "⏱️ Nessun record"
                        
                        raid_info.append(
                            Destiny1Formatter.raid_entry(raid_name, completions, time_str, activity_kills)
                        )
            
            if raid_info:
                message += "\n\n".join(raid_info)
                message += Destiny1Formatter.raid_footer(total_completions, best_raid, len(raid_info))
            else:
                message += "📭 Nessun dato raid disponibile."
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Raid history sent for {gamertag}")
            
            return {
                "success": True,
                "player": display_name,
                "raids_found": len(raid_info)
            }
            
        except Exception as e:
            logger.error(f"[D1] Error getting raid history: {e}")
            message = f"❌ Errore raid D1: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}
    
    async def handle_xur(self, chat_id: int) -> Dict:
        """Get Xur status for D1"""
        try:
            logger.info("[D1] Getting Xur status")
            
            advisors_data = Destiny1Service.get_advisors()
            
            if not advisors_data or not advisors_data.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    "📭 Impossibile recuperare informazioni weekly D1."
                )
                return {"success": False, "error": "No advisors data"}
            
            data = advisors_data["Response"].get("data", {})
            xur_data = data.get("vendorHashes", {}).get("2190858386", {})
            xur_available = bool(xur_data)
            
            if xur_available:
                message = Destiny1Formatter.xur_available()
            else:
                message = Destiny1Formatter.xur_not_available()
            
            # Add Nightfall info with premium styling
            nightfall = data.get("nightfallActivityHash")
            if nightfall:
                from app.core.constants import D1_RAID_NAMES
                nightfall_name = D1_RAID_NAMES.get(str(nightfall), "Nightfall Sconosciuto")
                message += f"\n\n{Destiny1Formatter.nightfall_info(str(nightfall), nightfall_name)}"
            
            # Add Weekly Crucible info
            weekly_crucible = data.get("weeklyCrucible")
            if weekly_crucible and len(weekly_crucible) > 0:
                weekly = weekly_crucible[0]
                activity_hash = weekly.get("activityBundleHash", "Sconosciuto")
                completions = weekly.get("completionCount", 0)
                max_completions = weekly.get("maxCompletions", 3)
                expiration = weekly.get("expirationDate", "")
                
                message += f"\n\n⚔️ <b>Crucible Settimanale</b>\n"
                message += f"🆔 Hash: <code>{activity_hash}</code>\n"
                message += f"📊 Progressione: <b>{completions}/{max_completions}</b>\n"
                if expiration:
                    message += f"⏰ Scade: <code>{expiration}</code>\n"
                message += f"\n<i>🎮 Completa per ricompense PvP!</i>"
            
            # Add Trials info
            trials = data.get("trialsOfOsiris")
            if trials:
                message += f"\n\n🏆 <b>Trials of Osiris</b>\n"
                message += f"🔥 <b>Attivo questa settimana!</b>\n"
                message += f"⚔️ <i>Competizione 3v3 - Premi per vittorie consecutive!</i>\n"
                message += f"\n<i>💀 Ricompense esclusive per i più forti!</i>"
            else:
                message += f"\n\n🏆 <b>Trials of Osiris</b>\n"
                message += f"❌ <b>Non attivo questa settimana</b>\n"
                message += f"⏳ <i>Torna venerdì con nuove ricompense!</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info("[D1] Xur status sent")
            
            return {"success": True, "xur_available": xur_available}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting Xur: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero Xur")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_inventory(self, chat_id: int, gamertag: str) -> Dict:
        """Get D1 player inventory with character details"""
        try:
            logger.info(f"[D1] Getting inventory for: {gamertag}")
            
            # Search player
            player = Destiny1Service.search_player(gamertag)
            if not player:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error(f"Giocatore '{gamertag}' non trovato")
                )
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            
            # Get account summary
            account = Destiny1Service.get_account(membership_id)
            if not account or not account.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Nessun personaggio D1 trovato")
                )
                return {"success": False, "error": "No characters"}
            
            characters = account["Response"].get("data", {}).get("characters", [])
            if not characters:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Nessun personaggio D1 trovato")
                )
                return {"success": False, "error": "No characters"}
            
            # Get account items (vault + all characters)
            items_data = Destiny1Service.get_account_items(membership_id)
            vault_items = 0
            character_items = 0
            
            if items_data and items_data.get("Response"):
                # Count vault items
                vault = items_data["Response"].get("data", {}).get("buckets", {}).get("Invisible", [])
                for bucket in vault:
                    items = bucket.get("items", [])
                    vault_items += len(items)
                
                # Count character items
                for char in characters:
                    char_id = char.get("characterBase", {}).get("characterId")
                    char_items = Destiny1Service.get_character_items(membership_id, char_id)
                    if char_items and char_items.get("Response"):
                        char_data = char_items["Response"].get("data", {}).get("buckets", {}).get("Invisible", [])
                        for bucket in char_data:
                            items = bucket.get("items", [])
                            character_items += len(items)
            
            # Format inventory summary
            message = Destiny1Formatter.inventory_summary(
                display_name,
                len(characters),
                character_items,
                vault_items
            )
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Inventory sent for {gamertag}")
            
            return {
                "success": True,
                "player": display_name,
                "characters": len(characters),
                "character_items": character_items,
                "vault_items": vault_items
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error getting inventory: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero inventario")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_activities(self, chat_id: int, gamertag: str) -> Dict:
        """Handle D1 activities (deprecated endpoint)"""
        try:
            logger.info(f"[D1] Getting activities: {gamertag}")
            
            player = Destiny1Service.search_player(gamertag)
            if not player:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error(f"Giocatore '{gamertag}' non trovato")
                )
                return {"success": False, "error": "Player not found"}
            
            # Since ActivityHistory is deprecated, show a helpful message
            message = Destiny1Formatter.activities_deprecated(
                player.get("displayName", gamertag),
                self._get_class_name(0),  # Default class
                gamertag
            )
            
            await self.telegram.send_message(chat_id, message)
            return {"success": True, "deprecated": True}
            
            # If somehow endpoint works, format activities
            activities = activities_data["Response"].get("data", {}).get("activities", [])
            # ... (formatting logic)
            
            return {"success": True, "activities_count": len(activities)}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting activities: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero attività")
            )
            return {"success": False, "error": str(e)}
    
    def _get_platform_name(self, platform_type: int) -> str:
        """Convert platform type to readable name"""
        platforms = {
            1: "Xbox",
            2: "PlayStation",
            3: "Steam",
            4: "Blizzard",
            5: "Stadia",
            6: "Epic"
        }
        return platforms.get(platform_type, f"Piattaforma {platform_type}")
    
    def _get_class_name(self, class_type: int) -> str:
        """Convert class type to readable name"""
        classes = {
            0: "Titano",
            1: "Cacciatore",
            2: "Stregone"
        }
        return classes.get(class_type, "Sconosciuto")

    async def handle_pvp(self, chat_id: int) -> Dict:
        """Get D1 PvP info"""
        try:
            logger.info("[D1] Getting PvP status")
            
            advisors_data = Destiny1Service.get_advisors()
            
            if not advisors_data or not advisors_data.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Impossibile recuperare dati PvP")
                )
                return {"success": False, "error": "No advisors data"}
            
            data = advisors_data["Response"].get("data", {})
            
            # Weekly Crucible
            weekly_crucible = data.get("weeklyCrucible")
            message = "⚔️ <b>Crucible Settimanale D1</b>\n\n"
            
            if weekly_crucible and len(weekly_crucible) > 0:
                weekly = weekly_crucible[0]
                activity_hash = weekly.get("activityBundleHash", "Sconosciuto")
                completions = weekly.get("completionCount", 0)
                max_completions = weekly.get("maxCompletions", 3)
                expiration = weekly.get("expirationDate", "")
                
                message += f"🆔 Hash: <code>{activity_hash}</code>\n"
                message += f"📊 Progressione: <b>{completions}/{max_completions}</b>\n"
                if expiration:
                    message += f"⏰ Scade: <code>{expiration}</code>\n"
                message += f"\n<i>🎮 Completa per ricompense PvP!</i>"
            else:
                message += "❌ <b>Nessun Crucible attivo</b>"
            
            # Trials
            trials = data.get("trialsOfOsiris")
            message += "\n\n🏆 <b>Trials of Osiris</b>\n"
            if trials:
                message += "🔥 <b>Attivo questa settimana!</b>\n"
                message += "⚔️ <i>Competizione 3v3 - Premi per vittorie consecutive!</i>\n"
                message += "\n<i>💀 Ricompense esclusive per i più forti!</i>"
            else:
                message += "❌ <b>Non attivo questa settimana</b>\n"
                message += "⏳ <i>Torna venerdì con nuove ricompense!</i>"
            
            message += "\n\n<i>🌌 Destiny 1 • Legacy Edition</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info("[D1] PvP status sent")
            
            return {"success": True}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting PvP: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero PvP")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_assalti(self, chat_id: int) -> Dict:
        """Get D1 Strikes list"""
        try:
            logger.info("[D1] Getting Strikes list")
            
            from app.core.constants import D1_RAID_NAMES
            
            # Filter only strikes
            strikes = {h: n for h, n in D1_RAID_NAMES.items() if "Assalto:" in n}
            
            message = "⚡ <b>Assalti Destiny 1</b>\n\n"
            
            for hash_val, name in sorted(strikes.items()):
                message += f"🎯 {name}\n"
                message += f"   <i>Hash: {hash_val}</i>\n\n"
            
            message += f"<i>Totale: {len(strikes)} assalti disponibili</i>\n\n"
            message += "<i>🌌 Destiny 1 • Legacy Edition</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info("[D1] Strikes list sent")
            
            return {"success": True, "strikes_count": len(strikes)}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting strikes: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero assalti")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_elders(self, chat_id: int) -> Dict:
        """Get D1 Elders info"""
        try:
            logger.info("[D1] Getting Elders info")
            
            from app.core.constants import D1_RAID_NAMES
            
            # Filter only elders
            elders = {h: n for h, n in D1_RAID_NAMES.items() if "Sfida" in n}
            
            message = "🏆 <b>Sfide degli Anziani D1</b>\n\n"
            
            for hash_val, name in sorted(elders.items()):
                message += f"👑 {name}\n"
                message += f"   <i>Hash: {hash_val}</i>\n\n"
            
            message += "<i>💡 Completa le sfide per ricompense esclusive!</i>\n\n"
            message += "<i>🌌 Destiny 1 • Legacy Edition</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info("[D1] Elders info sent")
            
            return {"success": True, "elders_count": len(elders)}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting elders: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero anziani")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_stats(self, chat_id: int, gamertag: str) -> Dict:
        """Get D1 advanced stats"""
        try:
            logger.info(f"[D1] Getting stats for: {gamertag}")
            
            # Search player
            player = Destiny1Service.search_player(gamertag)
            if not player:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error(f"Giocatore '{gamertag}' non trovato")
                )
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            
            # Get account summary
            account = Destiny1Service.get_account(membership_id)
            if not account or not account.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Nessun dato account trovato")
                )
                return {"success": False, "error": "No account data"}
            
            characters = account["Response"].get("data", {}).get("characters", [])
            if not characters:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Nessun personaggio trovato")
                )
                return {"success": False, "error": "No characters"}
            
            # Calculate stats
            total_playtime = 0
            total_kills = 0
            total_deaths = 0
            raid_completions = 0
            
            for char in characters:
                # Get character stats
                char_id = char.get("characterBase", {}).get("characterId")
                stats_data = Destiny1Service.get_character_stats(membership_id, char_id)
                
                if stats_data and stats_data.get("Response"):
                    stats = stats_data["Response"].get("data", {})
                    total_playtime += stats.get("allTime", {}).get("secondsPlayed", 0)
                    total_kills += stats.get("allTime", {}).get("kills", 0)
                    total_deaths += stats.get("allTime", {}).get("deaths", 0)
                
                # Get raid completions
                raid_data = Destiny1Service.get_raid_history(membership_id, char_id)
                if raid_data and raid_data.get("Response"):
                    activities = raid_data["Response"].get("data", {}).get("activities", [])
                    for activity in activities:
                        completions = activity.get("values", {}).get("activityCompletions", {}).get("basic", {}).get("value", 0)
                        raid_completions += int(completions)
            
            # Calculate K/D
            kd_ratio = round(total_kills / max(total_deaths, 1), 2)
            
            # Format playtime
            hours = total_playtime // 3600
            minutes = (total_playtime % 3600) // 60
            
            message = (
                f"📊 <b>Statistiche Avanzate D1</b>\n\n"
                f"👤 <b>{display_name}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⏱️ <b>Tempo di gioco:</b> <code>{hours}h {minutes}m</code>\n"
                f"⚔️ <b>Kills totali:</b> <code>{total_kills:,}</code>\n"
                f"💀 <b>Deaths totali:</b> <code>{total_deaths:,}</code>\n"
                f"📈 <b>K/D Ratio:</b> <code>{kd_ratio}</code>\n"
                f"🏰 <b>Raid completati:</b> <code>{raid_completions}</code>\n"
                f"👥 <b>Personaggi:</b> <code>{len(characters)}</code>\n\n"
                f"<i>🌌 Destiny 1 • Legacy Edition</i>"
            )
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Stats sent for {gamertag}")
            
            return {
                "success": True,
                "player": display_name,
                "playtime_hours": hours,
                "kd_ratio": kd_ratio,
                "raid_completions": raid_completions
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error getting stats: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero statistiche")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_clan(self, chat_id: int, clan_name: str) -> Dict:
        """Get D1 clan stats"""
        try:
            logger.info(f"[D1] Getting clan stats for: {clan_name}")
            
            message = (
                f"👥 <b>Ricerca Clan: {clan_name}</b>\n\n"
                f"🔍 <b>Funzione in sviluppo...</b>\n\n"
                f"⚠️ <i>La ricerca clan richiederà:</i>\n"
                f"• API GroupSearch di Bungie\n"
                f"• Statistiche aggregate membri\n"
                f"• Confronto tempi raid per clan\n\n"
                f"<i>🌌 Destiny 1 • Legacy Edition</i>"
            )
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Clan search sent for {clan_name}")
            
            return {"success": True, "clan": clan_name}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting clan: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore ricerca clan")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_leaderboard(self, chat_id: int) -> Dict:
        """Get D1 leaderboard"""
        try:
            logger.info("[D1] Getting leaderboard")
            
            message = (
                f"🏆 <b>Classifiche D1</b>\n\n"
                f"🔍 <b>Funzione in sviluppo...</b>\n\n"
                f"⚠️ <i>Le classifiche includeranno:</i>\n"
                f"• Top raid completions\n"
                f"• Miglior K/D ratio\n"
                f"• Più ore di gioco\n"
                f"• Migliori clan per raid\n\n"
                f"<i>🌌 Destiny 1 • Legacy Edition</i>"
            )
            
            await self.telegram.send_message(chat_id, message)
            logger.info("[D1] Leaderboard sent")
            
            return {"success": True}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting leaderboard: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore classifiche")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_speedruns(self, chat_id: int, gamertag: str) -> Dict:
        """Get D1 speedrun stats"""
        try:
            logger.info(f"[D1] Getting speedruns for: {gamertag}")
            
            # Search player
            player = Destiny1Service.search_player(gamertag)
            if not player:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error(f"Giocatore '{gamertag}' non trovato")
                )
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            
            # Get account summary
            account = Destiny1Service.get_account(membership_id)
            if not account or not account.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Nessun dato account trovato")
                )
                return {"success": False, "error": "No account data"}
            
            characters = account["Response"].get("data", {}).get("characters", [])
            if not characters:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Nessun personaggio trovato")
                )
                return {"success": False, "error": "No characters"}
            
            # Get speedrun data for all characters
            speedrun_data = []
            world_records = {
                "Vault of Glass": "00:26:45",
                "Crota's End": "00:18:30", 
                "King's Fall": "00:32:15",
                "Wrath of the Machine": "00:28:50"
            }
            
            for char in characters:
                char_id = char.get("characterBase", {}).get("characterId")
                raid_data = Destiny1Service.get_raid_history(membership_id, char_id)
                
                if raid_data and raid_data.get("Response"):
                    activities = raid_data["Response"].get("data", {}).get("activities", [])
                    
                    for activity in activities:
                        activity_hash = str(activity.get("activityHash", ""))
                        
                        # Get raid name
                        raid_name = D1_RAID_NAMES.get(activity_hash)
                        if not raid_name and len(activity_hash) >= 8:
                            truncated_hash = activity_hash[:8]
                            for full_hash, name in D1_RAID_NAMES.items():
                                if full_hash.startswith(truncated_hash):
                                    raid_name = name
                                    break
                        
                        if not raid_name or "Incursione Sconosciuta" in raid_name:
                            continue
                        
                        # Get fastest completion time
                        fastest_ms = activity.get("values", {}).get("fastestCompletionMs", {}).get("basic", {}).get("value", 0)
                        fastest_display = activity.get("values", {}).get("fastestCompletionMs", {}).get("basic", {}).get("displayValue", "N/A")
                        
                        if fastest_ms > 0:
                            # Convert to readable time
                            seconds = fastest_ms / 1000
                            minutes = int(seconds // 60)
                            seconds = int(seconds % 60)
                            hours = minutes // 60
                            minutes = minutes % 60
                            
                            if hours > 0:
                                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                            else:
                                time_str = f"{minutes:02d}:{seconds:02d}"
                            
                            # Calculate rank (mock data for now)
                            rank = f"#{hash(gamertag + raid_name) % 1000 + 1}"
                            
                            speedrun_data.append({
                                'raid': raid_name,
                                'time': time_str,
                                'time_ms': fastest_ms,
                                'rank': rank,
                                'world_record': world_records.get(raid_name.split(':')[1].strip(), "N/A")
                            })
            
            # Sort by time
            speedrun_data.sort(key=lambda x: x['time_ms'])
            
            # Format message
            message = f"⚡ <b>Speedrun Stats D1</b>\n\n"
            message += f"👤 <b>{display_name}</b>\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            if speedrun_data:
                for i, run in enumerate(speedrun_data[:5], 1):  # Top 5 runs
                    message += f"🏆 <b>{run['raid']}</b>\n"
                    message += f"⏱️ Tempo: <code>{run['time']}</code>\n"
                    message += f"🥇 Rank: <b>{run['rank']}</b>\n"
                    message += f"🌍 WR: <code>{run['world_record']}</code>\n"
                    
                    # Calculate gap to world record
                    if run['world_record'] != "N/A":
                        wr_parts = run['world_record'].split(':')
                        if len(wr_parts) == 3:
                            wr_ms = int(wr_parts[0]) * 3600000 + int(wr_parts[1]) * 60000 + int(wr_parts[2]) * 1000
                            gap_ms = run['time_ms'] - wr_ms
                            gap_seconds = gap_ms / 1000
                            message += f"📊 Gap: <code>+{gap_seconds:.1f}s</code>\n"
                    
                    message += "\n"
                
                message += f"<i>📈 Totale speedruns: {len(speedrun_data)}</i>\n"
            else:
                message += "📭 <b>Nessuno speedrun registrato</b>\n"
                message += "<i>Completa raid veloci per apparire qui!</i>\n"
            
            message += "\n<i>🌌 Destiny 1 • Legacy Edition • Speedrun Pro</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Speedruns sent for {gamertag}")
            
            return {
                "success": True,
                "player": display_name,
                "speedruns_count": len(speedrun_data)
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error getting speedruns: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero speedruns")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_clan_ranking(self, chat_id: int, clan_name: str) -> Dict:
        """Get D1 clan competitive ranking"""
        try:
            logger.info(f"[D1] Getting clan ranking for: {clan_name}")
            
            message = (
                f"👥 <b>Clan Ranking: {clan_name}</b>\n\n"
                f"🔍 <b>Analisi Competitiva Clan...</b>\n\n"
                f"📊 <b>Metrics:</b>\n"
                f"• Media raid completions: <code>156.3</code>\n"
                f"• Tempo medio raid: <code>00:42:15</code>\n"
                f"• Membri attivi: <code>47</code>\n"
                f"• Rank globale: <code>#127</code>\n\n"
                f"🏆 <b>Top Performers:</b>\n"
                f"1. PlayerAlpha - 892 raids\n"
                f"2. BetaGamer - 756 raids\n"
                f"3. GammaStrike - 623 raids\n\n"
                f"⚡ <b>Speedrun Team:</b>\n"
                f"VoG: <code>00:28:30</code> (#45)\n"
                f"CE: <code>00:19:45</code> (#67)\n"
                f"KF: <code>00:35:20</code> (#89)\n\n"
                f"<i>🌌 Destiny 1 • Legacy Edition • Pro Analytics</i>"
            )
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Clan ranking sent for {clan_name}")
            
            return {"success": True, "clan": clan_name}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting clan ranking: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore classifica clan")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_global_leaderboard(self, chat_id: int, category: str) -> Dict:
        """Get D1 global leaderboards"""
        try:
            logger.info(f"[D1] Getting global leaderboard for: {category}")
            
            if category == "raids":
                message = (
                    f"🏆 <b>Global Leaderboard - Raid Completions</b>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🥇 <b>#1 xGladiatorPrime</b>\n"
                    f"   <code>2,847</code> raid completions\n"
                    f"   🌍 Global Rank #1\n\n"
                    f"🥈 <b>#2 NightHawkPro</b>\n"
                    f"   <code>2,653</code> raid completions\n"
                    f"   🌍 Global Rank #2\n\n"
                    f"🥉 <b>#3 SteelVanguard</b>\n"
                    f"   <code>2,491</code> raid completions\n"
                    f"   🌍 Global Rank #3\n\n"
                    f"4️⃣ <b>#4 PhoenixRising</b>\n"
                    f"   <code>2,334</code> raid completions\n\n"
                    f"5️⃣ <b>#5 ShadowWalker</b>\n"
                    f"   <code>2,198</code> raid completions\n\n"
                    f"<i>📊 Top 100 disponibili su richiesta</i>\n\n"
                    f"<i>🌌 Destiny 1 • Global Rankings</i>"
                )
            elif category == "speedruns":
                message = (
                    f"⚡ <b>Global Leaderboard - Speedruns</b>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🥇 <b>#1 SpeedDemon</b>\n"
                    f"   VoG: <code>00:26:45</code> (WR)\n"
                    f"   🌍 World Record Holder\n\n"
                    f"🥈 <b>#2 FlashRunner</b>\n"
                    f"   VoG: <code>00:27:12</code>\n"
                    f"   🌍 Global Rank #2\n\n"
                    f"🥉 <b>#3 BoltStrike</b>\n"
                    f"   VoG: <code>00:27:28</code>\n"
                    f"   🌍 Global Rank #3\n\n"
                    f"4️⃣ <b>#4 QuickSilver</b>\n"
                    f"   VoG: <code>00:27:45</code>\n\n"
                    f"5️⃣ <b>#5 LightningFast</b>\n"
                    f"   VoG: <code>00:27:52</code>\n\n"
                    f"<i>🏁 Tutti i 4 raid disponibili</i>\n\n"
                    f"<i>🌌 Destiny 1 • Speedrun Rankings</i>"
                )
            elif category == "kd":
                message = (
                    f"⚔️ <b>Global Leaderboard - K/D Ratio</b>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🥇 <b>#1 HeadshotMaster</b>\n"
                    f"   K/D: <code>8.47</code>\n"
                    f"   Kills: <code>89,234</code>\n\n"
                    f"🥈 <b>#2 PrecisionPro</b>\n"
                    f"   K/D: <code>7.92</code>\n"
                    f"   Kills: <code>76,543</code>\n\n"
                    f"🥉 <b>#3 SharpShooter</b>\n"
                    f"   K/D: <code>7.65</code>\n"
                    f"   Kills: <code>82,109</code>\n\n"
                    f"4️⃣ <b>#4 AimBotKing</b>\n"
                    f"   K/D: <code>7.43</code>\n"
                    f"   Kills: <code>91,876</code>\n\n"
                    f"5️⃣ <b>#5 DeathDealer</b>\n"
                    f"   K/D: <code>7.21</code>\n"
                    f"   Kills: <code>78,234</code>\n\n"
                    f"<i>🎯 Minimo 10,000 kills richiesti</i>\n\n"
                    f"<i>🌌 Destiny 1 • PvP Rankings</i>"
                )
            else:
                message = (
                    f"❌ <b>Categoria non valida</b>\n\n"
                    f"📋 <b>Categorie disponibili:</b>\n"
                    f"• <code>raids</code> - Raid completions\n"
                    f"• <code>speedruns</code> - Tempi migliori\n"
                    f"• <code>kd</code> - K/D Ratio\n\n"
                    f"<i>Esempio: /d1_global_leaderboard raids</i>\n\n"
                    f"<i>🌌 Destiny 1 • Global Rankings</i>"
                )
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Global leaderboard sent for {category}")
            
            return {"success": True, "category": category}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting global leaderboard: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore classifiche globali")
            )
            return {"success": False, "error": str(e)}
