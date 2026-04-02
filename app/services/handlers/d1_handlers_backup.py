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
            
            logger.info(f"[D1] Player found: {display_name}")
            return {
                "success": True,
                "player": {
                    "display_name": display_name,
                    "membership_id": membership_id,
                    "membership_type": platform
                }
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error finding player {gamertag}: {e}")
            await self.telegram.send_message(
                chat_id, 
                Destiny1Formatter.error_message("Errore durante la ricerca")
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
    
    async def handle_raid_history(self, chat_id: int, gamertag: str) -> Dict:
        """Get Destiny 1 raid history for a player"""
        try:
            logger.info(f"[D1] Getting raid history: {gamertag}")
            
            # Search player
            player = Destiny1Service.search_player(gamertag)
            if not player:
                await self.telegram.send_message(
                    chat_id, 
                    Destiny1Formatter.player_not_found(gamertag)
                )
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            
            # Get account
            account = Destiny1Service.get_account(membership_id)
            if not account or not account.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    f"📭 Nessun account D1 trovato per <b>{display_name}</b>."
                )
                return {"success": False, "error": "No account data"}
            
            characters = account["Response"].get("data", {}).get("characters", [])
            if not characters:
                await self.telegram.send_message(
                    chat_id,
                    f"📭 Nessun personaggio D1 trovato."
                )
                return {"success": False, "error": "No characters"}
            
            first_char = characters[0]
            character_id = first_char.get("characterBase", {}).get("characterId")
            class_type = self._get_class_name(first_char.get("classType", 0))
            char_level = first_char.get("characterLevel", "N/A")
            
            # Get raid stats
            raid_data = Destiny1Service.get_raid_history(membership_id, character_id)
            
            # Build message
            message = Destiny1Formatter.raid_header(
                display_name, 
                first_char.get("characterBase", {}).get("classType", 0),
                char_level
            )
            
            raid_info = []
            total_completions = 0
            best_raid = None
            best_count = 0
            
            if raid_data and raid_data.get("Response"):
                activities = raid_data["Response"].get("data", {}).get("activities", [])
                
                # Sort by completions
                sorted_activities = sorted(
                    activities,
                    key=lambda x: x.get("values", {}).get("activityCompletions", {}).get("basic", {}).get("value", 0),
                    reverse=True
                )
                
                for activity in sorted_activities[:10]:
                    activity_hash = str(activity.get("activityHash", ""))
                    raid_name = D1_RAID_NAMES.get(activity_hash, f"🔍 Incursione ({activity_hash[:8]}...)")
                    
                    completions = activity.get("values", {}).get("activityCompletions", {}).get("basic", {}).get("value", 0)
                    best_time = activity.get("values", {}).get("fastestCompletionMs", {}).get("basic", {}).get("displayValue", "N/A")
                    kills = activity.get("values", {}).get("activityKills", {}).get("basic", {}).get("value", 0)
                    
                    if completions > 0:
                        total_completions += int(completions)
                        if int(completions) > best_count:
                            best_count = int(completions)
                            best_raid = raid_name
                        
                        raid_info.append(
                            Destiny1Formatter.raid_entry(raid_name, completions, best_time, kills)
                        )
            
            if raid_info:
                message += "\n\n".join(raid_info)
                message += Destiny1Formatter.raid_footer(total_completions, best_raid, len(raid_info))
            else:
                message += "📭 Nessun dato raid disponibile."
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Raid history sent for {gamertag}")
            
            return {"success": True, "raids_found": len(raid_info)}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting raid history: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero raid")
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
    
    async def handle_inventory(self, chat_id: int, gamertag: str) -> Dict:
        """Get D1 player inventory with character details"""
        try:
            logger.info(f"[D1] Getting inventory for: {gamertag}")
            
            # Search player
            player = Destiny1Service.search_player(gamertag)
            if not player:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.player_not_found(gamertag)
                )
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            
            # Get account for character info
            account = Destiny1Service.get_account(membership_id)
            if not account or not account.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    f"📭 Nessun personaggio trovato per <b>{display_name}</b>."
                )
                return {"success": False, "error": "No characters found"}
            
            characters = account["Response"].get("data", {}).get("characters", [])
            if not characters:
                await self.telegram.send_message(chat_id, "📭 Nessun personaggio D1 trovato.")
                return {"success": False, "error": "No characters"}
            
            # Get first character info
            character = characters[0]
            character_id = character.get("characterBase", {}).get("characterId")
            class_type = character.get("characterBase", {}).get("classType", 0)
            character_class = self._get_class_name(class_type)
            
            # Get character inventory and vault
            inventory_data = Destiny1Service.get_character_inventory(membership_id, character_id)
            vault_data = Destiny1Service.get_vault(membership_id)
            
            # Count items
            char_items = 0
            if inventory_data and inventory_data.get("Response"):
                buckets = inventory_data["Response"].get("data", {}).get("buckets", {})
                for bucket in buckets.values():
                    items = bucket.get("items", [])
                    char_items += len(items)
            
            vault_items = 0
            if vault_data and vault_data.get("Response"):
                vault_items = len(vault_data["Response"].get("data", {}).get("items", []))
            
            # Build message
            message = (
                f"🎒 <b>Inventario D1 di {display_name}</b>\n"
                f"🛡️ Classe: {character_class}\n\n"
                f"📦 Oggetti sul personaggio: ~{char_items}\n"
                f"🏦 Oggetti nel Vault: ~{vault_items}\n"
                f"📊 Totale approssimativo: ~{char_items + vault_items}\n\n"
                f"<i>Destiny 1 • PlayStation</i>"
            )
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Inventory sent for {gamertag}")
            
            return {
                "success": True,
                "player": display_name,
                "character_items": char_items,
                "vault_items": vault_items
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error getting inventory: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero inventario")
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
    
    async def handle_activities(self, chat_id: int, gamertag: str) -> Dict:
        """Handle D1 activities (deprecated endpoint)"""
        try:
            logger.info(f"[D1] Getting activities: {gamertag}")
            
            player = Destiny1Service.search_player(gamertag)
            if not player:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.player_not_found(gamertag)
                )
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            
            account = Destiny1Service.get_account(membership_id)
            if not account or not account.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    f"📭 Nessun account D1 trovato."
                )
                return {"success": False, "error": "No account"}
            
            characters = account["Response"].get("data", {}).get("characters", [])
            if not characters:
                await self.telegram.send_message(
                    chat_id,
                    "📭 Nessun personaggio D1 trovato."
                )
                return {"success": False, "error": "No characters"}
            
            first_char = characters[0]
            class_type = self._get_class_name(first_char.get("classType", 0))
            
            # Check if endpoint works
            activities_data = Destiny1Service.get_recent_activities(
                membership_id, 
                first_char.get("characterBase", {}).get("characterId")
            )
            
            # Endpoint deprecated - show alternatives
            if not activities_data or not activities_data.get("Response"):
                message = Destiny1Formatter.activities_deprecated(
                    display_name, class_type, gamertag
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
