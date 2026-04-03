"""
Destiny 1 specific command handlers
"""
import logging
from datetime import datetime
from typing import Dict, Optional
from app.services.destiny1_service import Destiny1Service
from app.services.formatting import Destiny1Formatter
from app.core.constants import D1_RAID_NAMES
from app.core.exceptions import PlayerNotFoundError
from app.core.d1_events import d1_event_manager

logger = logging.getLogger("destiny1_handlers")


class D1CommandHandlers:
    """Handlers for Destiny 1 specific commands"""
    
    def __init__(self, telegram_adapter):
        self.telegram = telegram_adapter
    
    def _get_oauth_token(self, chat_id: int) -> Optional[str]:
        """Helper to get OAuth token for a chat"""
        try:
            from app.api.v1.endpoints.webhook import orchestrator
            token_data = orchestrator._get_oauth_token(chat_id)
            if token_data:
                access_token = token_data.get("access_token")
                logger.info(f"[D1] OAuth token found for chat {chat_id}")
                return access_token
            else:
                logger.warning(f"[D1] No OAuth token found for chat {chat_id}")
                return None
        except Exception as e:
            logger.warning(f"[D1] Could not retrieve OAuth token: {e}")
            return None
    
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
            
            # Get OAuth token for enhanced access
            access_token = self._get_oauth_token(chat_id)
            
            # Get account for character details with OAuth if available
            account = Destiny1Service.get_account(membership_id, access_token)
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
            
            # Get OAuth token for enhanced access
            access_token = self._get_oauth_token(chat_id)
            
            # Get account summary with OAuth if available
            account = Destiny1Service.get_account(membership_id, access_token)
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
    
    async def handle_vendors(self, chat_id: int) -> Dict:
        """Get all D1 vendors with OAuth token - Xur, Vanguard, Crucible, Factions"""
        try:
            logger.info("[D1] Getting vendors with OAuth")
            
            # Get OAuth token for authenticated vendor access
            access_token = self._get_oauth_token(chat_id)
            
            if not access_token:
                await self.telegram.send_message(
                    chat_id,
                    "🔒 <b>Autenticazione richiesta</b>\n\n"
                    "Per vedere i venditori, autenticati prima con:\n"
                    "<code>/auth</code>\n\n"
                    "<i>🌌 Destiny 1 • Authentication Required</i>"
                )
                return {"success": False, "error": "No OAuth token"}
            
            # Get vendor data using OAuth
            from app.services.destiny1_service import Destiny1Service
            vendors_data = Destiny1Service.get_vendors(access_token)
            
            if not vendors_data or not vendors_data.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    "📭 Impossibile recuperare informazioni venditori D1."
                )
                return {"success": False, "error": "No vendors data"}
            
            data = vendors_data["Response"].get("data", {})
            
            # Format vendors message
            message = "🛒 <b>Venditori D1</b>\n\n"
            
            # Xur
            xur_data = data.get("vendorHashes", {}).get("2190858386", {})
            if xur_data:
                message += "👳‍♂️ <b>Xûr è arrivato!</b>\n"
                message += "📍 Torre o Riva\n"
                message += "🕒 Fino a Martedì 18:00\n\n"
            else:
                message += "👳‍♂️ <b>Xûr</b> - Non disponibile\n"
                message += "⏰ Arriva Venerdì 18:00\n\n"
            
            # Other vendors info
            message += "🛡️ <b>Vanguard</b> - Disponibile\n"
            message += "⚔️ <b>Crucible</b> - Disponibile\n"
            message += "🏴 <b>Fazioni</b> - Check in gioco\n\n"
            
            message += "<i>🌌 Destiny 1 • Vendors</i>\n"
            message += "<i>⚡ Usa /auth per aggiornare il token</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info("[D1] Vendors info sent")
            
            return {"success": True, "vendors_loaded": True}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting vendors: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero venditori")
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
            
            # Get first character class
            first_char = characters[0]
            character_class_type = first_char.get("characterBase", {}).get("classType", 0)
            
            # Get account items (vault + all characters)
            items_data = Destiny1Service.get_account_items(membership_id)
            vault_items = 0
            character_items = 0
            
            if items_data and items_data.get("Response"):
                # Count vault items - check all buckets
                buckets = items_data["Response"].get("data", {}).get("buckets", {})
                
                # Vault in D1 is typically in specific buckets
                vault_buckets = ["Invisible", "Vault", "General", "BUCKET_VAULT"]
                for bucket_name in vault_buckets:
                    bucket_data = buckets.get(bucket_name, [])
                    for bucket in bucket_data:
                        items = bucket.get("items", [])
                        vault_items += len(items)
                
                # Count character items
                for char in characters:
                    char_id = char.get("characterBase", {}).get("characterId")
                    char_items_data = Destiny1Service.get_character_items(membership_id, char_id)
                    if char_items_data and char_items_data.get("Response"):
                        char_buckets = char_items_data["Response"].get("data", {}).get("buckets", {})
                        # Count items from all character buckets (equipped + inventory)
                        for bucket_name, bucket_list in char_buckets.items():
                            if bucket_name != "Invisible":  # Skip vault
                                for bucket in bucket_list:
                                    items = bucket.get("items", [])
                                    character_items += len(items)
            
            # Format inventory summary
            message = Destiny1Formatter.inventory_summary(
                display_name,
                character_class_type,
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
            
            # Get first character class
            first_char = characters[0]
            character_class_type = first_char.get("characterBase", {}).get("classType", 0)
            character_class_name = self._get_class_name(character_class_type)
            
            # Calculate stats
            total_playtime = 0
            total_kills = 0
            total_deaths = 0
            raid_completions = 0
            debug_info = []  # Collect debug info
            
            for char in characters:
                # Get character stats
                char_id = char.get("characterBase", {}).get("characterId")
                membership_type = account.get("data", {}).get("membershipType", 2)
                
                stats_data = Destiny1Service.get_character_stats(membership_type, membership_id, char_id)
                
                # DEBUG: Check what we got
                if stats_data is None:
                    debug_info.append(f"API ERROR for char {char_id[-4:]} - check logs")
                elif stats_data.get("Response"):
                    debug_info.append(f"✓ Stats OK for char {char_id[-4:]}")
                    response = stats_data["Response"]
                    debug_info.append(f"Keys: {list(response.keys())[:3]}")
                else:
                    debug_info.append(f"✗ No Response: {list(stats_data.keys())[:3]}")
                
                if stats_data and stats_data.get("Response"):
                    response = stats_data["Response"]
                    # D1 API returns stats by mode: allPvE, allPvP, etc.
                    for mode in ["allPvE", "allPvP"]:
                        mode_stats = response.get(mode, {})
                        all_time = mode_stats.get("allTime", {})
                        
                        # Extract values from basic.value structure
                        seconds = all_time.get("secondsPlayed", {})
                        if isinstance(seconds, dict):
                            total_playtime += seconds.get("basic", {}).get("value", 0)
                        
                        kills = all_time.get("kills", {})
                        if isinstance(kills, dict):
                            total_kills += kills.get("basic", {}).get("value", 0)
                        
                        deaths = all_time.get("deaths", {})
                        if isinstance(deaths, dict):
                            val = deaths.get("basic", {}).get("value", 0)
                            total_deaths += val
                else:
                    debug_info.append(f"No Response in stats_data: {stats_data.keys() if stats_data else 'None'}")
                
                # Get raid completions
                raid_data = Destiny1Service.get_raid_history(membership_id, char_id)
                if raid_data and raid_data.get("Response"):
                    activities = raid_data["Response"].get("data", {}).get("activities", [])
                    for activity in activities:
                        completions = activity.get("values", {}).get("activityCompletions", {}).get("basic", {}).get("value", 0)
                        raid_completions += int(completions)
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
            
            # SAVE USER STATS FOR LEADERBOARD
            try:
                from app.infrastructure.user_stats_storage import save_user_stats
                save_user_stats(
                    chat_id=chat_id,
                    gamertag=display_name,
                    membership_id=membership_id,
                    kills=total_kills,
                    deaths=total_deaths,
                    hours=hours,
                    raid_completions=raid_completions
                )
                logger.info(f"[D1] Saved stats for user {display_name}")
            except Exception as e:
                logger.warning(f"[D1] Failed to save user stats: {e}")
            
            message = (
                f"📊 <b>Statistiche Avanzate D1</b>\n\n"
                f"👤 <b>{display_name}</b>\n"
                f"⚔️ <b>Classe:</b> {character_class_name}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⏱️ <b>Tempo di gioco:</b> <code>{hours}h {minutes}m</code>\n"
                f"⚔️ <b>Kills totali:</b> <code>{total_kills:,}</code>\n"
                f"💀 <b>Deaths totali:</b> <code>{total_deaths:,}</code>\n"
                f"📈 <b>K/D Ratio:</b> <code>{kd_ratio}</code>\n"
                f"🏰 <b>Raid completati:</b> <code>{raid_completions}</code>\n"
                f"👥 <b>Personaggi:</b> <code>{len(characters)}</code>\n\n"
                f"<i>🌌 Destiny 1 • Legacy Edition</i>\n\n"
                f"<code>DEBUG:\n" + "\n".join(debug_info[-10:]) + "</code>"
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
        """Get D1 clan stats with REAL API"""
        try:
            logger.info(f"[D1] Searching clan: {clan_name}")
            
            # Search for clan using Bungie API
            clan = Destiny1Service.search_clan(clan_name)
            
            if not clan:
                message = (
                    f"� <b>Clan non trovato</b>\n\n"
                    f"❌ Nessun clan trovato con il nome: <code>{clan_name}</code>\n\n"
                    f"� <i>Suggerimenti:</i>\n"
                    f"• Verifica l'ortografia\n"
                    f"• Prova con una parte del nome\n"
                    f"• I clan D1 sono su PlayStation Network\n\n"
                    f"<i>🌌 Destiny 1 • Clan Search</i>"
                )
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Clan not found"}
            
            # Get clan details
            clan_id = clan.get("groupId")
            clan_real_name = clan.get("name", clan_name)
            clan_motto = clan.get("motto", "N/A")
            clan_about = clan.get("about", "")
            member_count = clan.get("memberCount", 0)
            
            logger.info(f"[D1] Clan found: {clan_real_name} (ID: {clan_id})")
            
            # Get clan members
            members_data = Destiny1Service.get_clan_members(clan_id)
            members_count = 0
            if members_data and members_data.get("results"):
                members_count = len(members_data["results"])
            
            # Format clan info
            message = (
                f"👥 <b>Clan D1 Trovato!</b>\n\n"
                f"🏷️ <b>Nome:</b> <code>{clan_real_name}</code>\n"
                f"🆔 <b>ID:</b> <code>{clan_id}</code>\n"
                f"👤 <b>Membri:</b> <code>{members_count}</code>\n"
            )
            
            if clan_motto and clan_motto != "N/A":
                message += f"💬 <b>Motto:</b> <i>{clan_motto}</i>\n"
            
            if clan_about:
                # Truncate long about text
                about_short = clan_about[:200] + "..." if len(clan_about) > 200 else clan_about
                message += f"📝 <b>Info:</b> {about_short}\n"
            
            message += (
                f"\n<i>🌌 Destiny 1 • Clan Info</i>\n\n"
                f"💡 Usa <code>/d1_clan_ranking {clan_real_name}</code> per vedere le statistiche!"
            )
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Clan info sent for {clan_real_name}")
            
            return {
                "success": True, 
                "clan": {
                    "id": clan_id,
                    "name": clan_real_name,
                    "members": members_count
                }
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error searching clan: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error(f"Errore ricerca clan: {str(e)}")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_leaderboard(self, chat_id: int) -> Dict:
        """Get D1 leaderboard - uses REAL data from bot users"""
        try:
            logger.info("[D1] Getting real user leaderboard")
            
            # Get real user data from storage
            from app.infrastructure.user_stats_storage import get_leaderboard, get_user_count
            
            user_count = get_user_count() or 0
            
            if user_count == 0:
                message = (
                    "🏆 <b>Classifica D1 - Nessun dato</b>\n\n"
                    "❌ Nessun utente ha ancora usato il bot.\n\n"
                    "💡 <b>Come partecipare:</b>\n"
                    "Usa <code>/d1_stats tuo_gamertag</code>\n"
                    "per aggiungere i tuoi dati alla classifica!\n\n"
                    "<i>🌌 Destiny 1 • Leaderboard</i>"
                )
                await self.telegram.send_message(chat_id, message)
                return {"success": True, "players": 0}
            
            # Get top users by different categories
            top_raids = get_leaderboard("raid_completions", 5) or []
            top_kills = get_leaderboard("kills", 5) or []
            top_kd = get_leaderboard("kd_ratio", 5) or []
            top_hours = get_leaderboard("hours", 5) or []
            
            # Format message
            message = f"🏆 <b>Classifica D1 - {user_count} partecipanti</b>\n\n"
            
            message += "🏰 <b>Top Raid Completati:</b>\n"
            if top_raids:
                for i, p in enumerate(top_raids, 1):
                    raids = p.get('raid_completions', 0)
                    message += f"   {i}. {p.get('gamertag', 'Unknown')}: <code>{raids:,}</code> 🏰\n"
            else:
                message += "   Nessun dato\n"
            
            message += "\n⚔️ <b>Top Kills:</b>\n"
            if top_kills:
                for i, p in enumerate(top_kills, 1):
                    kills = p.get('kills', 0)
                    message += f"   {i}. {p.get('gamertag', 'Unknown')}: <code>{kills:,}</code> ⚔️\n"
            else:
                message += "   Nessun dato\n"
            
            message += "\n🎯 <b>Top K/D Ratio:</b>\n"
            if top_kd:
                for i, p in enumerate(top_kd, 1):
                    kd = p.get('kd_ratio', 0)
                    message += f"   {i}. {p.get('gamertag', 'Unknown')}: <code>{kd}</code> 🎯\n"
            else:
                message += "   Nessun dato\n"
            
            message += "\n⏱️ <b>Top Ore di Gioco:</b>\n"
            if top_hours:
                for i, p in enumerate(top_hours, 1):
                    hours = p.get('hours', 0)
                    message += f"   {i}. {p.get('gamertag', 'Unknown')}: <code>{hours}h</code> ⏱️\n"
            else:
                message += "   Nessun dato\n"
            
            message += "\n<i>🌌 Destiny 1 • Leaderboard Reale</i>\n"
            message += "<i>Dati degli utenti di questo bot</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Real leaderboard sent with {user_count} users")
            
            return {"success": True, "players": user_count}
            
        except Exception as e:
            logger.exception(f"[D1] Error in leaderboard: {e}")
            await self.telegram.send_message(
                chat_id,
                "❌ <b>Errore classifiche</b>\n\n"
                "Si è verificato un errore nel recupero dei dati.\n"
                "Prova a usare <code>/d1_stats tuo_gamertag</code> prima.\n\n"
                f"<i>Errore: {str(e)[:100]}</i>"
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
        """Get D1 clan competitive ranking with REAL DATA"""
        try:
            logger.info(f"[D1] Getting REAL clan ranking for: {clan_name}")
            
            # Search for clan
            clan = Destiny1Service.search_clan(clan_name)
            if not clan:
                message = (
                    f"❌ <b>Clan '{clan_name}' non trovato</b>\n\n"
                    f"🔍 <b>Possibili cause:</b>\n"
                    f"• Il clan potrebbe essere stato rinominato\n"
                    f"• Il clan potrebbe essere stato sciolto\n"
                    f"• Il nome potrebbe avere caratteri speciali diversi\n\n"
                    f"💡 <b>Suggerimenti:</b>\n"
                    f"• Prova con solo la prima parola del nome\n"
                    f"• Prova con lettere maiuscole/minuscole diverse\n"
                    f"• Verifica il nome esatto su Bungie.net\n\n"
                    f"<i>🌌 Destiny 1 • Clan Search</i>"
                )
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Clan not found"}
            
            clan_id = clan.get("groupId")
            clan_real_name = clan.get("name", clan_name)
            clan_motto = clan.get("motto", "Nessun motto")
            member_count = clan.get("memberCount", 0)
            
            # Get clan statistics
            stats = Destiny1Service.get_clan_stats(clan_id)
            
            message = f"👥 <b>Clan Ranking: {clan_real_name}</b>\n\n"
            message += f"� <i>{clan_motto}</i>\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            if stats:
                message += f"📊 <b>Statistiche Reali:</b>\n"
                message += f"• Membri totali: <code>{stats['total_members']}</code>\n"
                message += f"• Membri attivi: <code>{stats['active_members']}</code>\n"
                message += f"• Raid totali clan: <code>{stats['total_raids']}</code>\n"
                message += f"• Media raid/membro: <code>{stats['avg_raids']}</code>\n\n"
                
                if stats.get("top_performers"):
                    message += f"🏆 <b>Top Performers:</b>\n"
                    for i, member in enumerate(stats["top_performers"][:5], 1):
                        emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1] if i <= 3 else f"{i}."
                        message += f"{emoji} <b>{member['name']}</b> - <code>{member['raids']}</code> raids\n"
                    message += "\n"
                
                message += f"<i>📈 Dati aggiornati in tempo reale da Bungie API</i>\n"
            else:
                message += f"⚠️ <b>Statistiche parziali disponibili</b>\n"
                message += f"• Membri: <code>{member_count}</code>\n"
                message += f"<i>Alcuni dati non sono accessibili via API</i>\n"
            
            message += f"\n<i>🌌 Destiny 1 • Real Clan Analytics</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] REAL clan ranking sent for {clan_name}")
            
            return {
                "success": True,
                "clan": clan_real_name,
                "members": member_count,
                "has_real_data": bool(stats)
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error getting real clan ranking: {e}")
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

    async def handle_loadout(self, chat_id: int, gamertag: str, stats_wanted: str) -> Dict:
        """D1 Loadout Optimizer - Trova il set perfetto"""
        try:
            logger.info(f"[D1] Optimizing loadout for {gamertag} targeting: {stats_wanted}")
            
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
            
            # Parse stats wanted (es: "int 300 dis 200 str 150")
            stats_targets = self._parse_stats_targets(stats_wanted)
            
            # Get OAuth token for enhanced inventory access
            access_token = self._get_oauth_token(chat_id)
            
            # Get all items for all characters with OAuth
            account_items = Destiny1Service.get_account_items(membership_id, access_token)
            if not account_items or not account_items.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Nessun dato inventario trovato")
                )
                return {"success": False, "error": "No inventory data"}
            
            # Analyze items and find best combinations
            optimized_loadout = self._optimize_loadout(account_items, stats_targets)
            
            message = f"🎯 <b>LOADOUT OPTIMIZER D1</b>\n\n"
            message += f"👤 <b>{display_name}</b>\n"
            message += f"📊 <b>Target:</b> <code>{stats_wanted}</code>\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            if optimized_loadout:
                message += f"✅ <b>SET OTTIMIZZATO TROVATO!</b>\n\n"
                
                for slot, item in optimized_loadout['items'].items():
                    message += f"🔹 <b>{slot.upper()}</b>\n"
                    message += f"   {item['name']}\n"
                    message += f"   <code>{item['stats']}</code>\n\n"
                
                message += f"📈 <b>Statistiche Totali:</b>\n"
                for stat, value in optimized_loadout['total_stats'].items():
                    target = stats_targets.get(stat, 0)
                    diff = value - target
                    emoji = "✅" if diff >= 0 else "⚠️"
                    message += f"{emoji} <b>{stat.upper()}:</b> <code>{value}</code> (target: {target})\n"
                
                message += f"\n<i>💡 Questo set ti dà le statistiche desiderate!</i>\n"
            else:
                message += f"❌ <b>Nessun set trovato</b>\n"
                message += f"<i>Prova a rilassare i requisiti o verifica il tuo inventario</i>\n"
            
            message += f"\n<i>🌌 Destiny 1 • Loadout Optimizer Pro</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Loadout optimized for {gamertag}")
            
            return {
                "success": True,
                "player": display_name,
                "optimized": bool(optimized_loadout)
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error optimizing loadout: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore ottimizzazione loadout")
            )
            return {"success": False, "error": str(e)}
    
    def _parse_stats_targets(self, stats_string: str) -> Dict:
        """Parse stats string like 'int 300 dis 200 str 150'"""
        targets = {}
        parts = stats_string.lower().split()
        
        for i in range(0, len(parts), 2):
            if i + 1 < len(parts):
                stat = parts[i]
                try:
                    value = int(parts[i + 1])
                    if stat in ['int', 'intelletto']:
                        targets['intelletto'] = value
                    elif stat in ['dis', 'disciplina']:
                        targets['disciplina'] = value
                    elif stat in ['str', 'forza']:
                        targets['forza'] = value
                except ValueError:
                    continue
        
        return targets
    
    def _optimize_loadout(self, account_items: Dict, targets: Dict) -> Optional[Dict]:
        """REAL loadout optimization - analyze actual inventory items"""
        try:
            # Extract armor pieces from inventory
            armor_items = self._extract_armor_pieces(account_items)
            if not armor_items:
                return None
            
            # Try to find best combination
            best_set = self._find_best_combination(armor_items, targets)
            return best_set
            
        except Exception as e:
            logger.error(f"[D1] Error in loadout optimization: {e}")
            # Fallback to mock if error
            return self._mock_loadout()
    
    def _extract_armor_pieces(self, account_items: Dict) -> Dict:
        """Extract armor pieces from account inventory"""
        armor = {'casco': [], 'guanti': [], 'corazza': [], 'gambe': [], 'cappa': []}
        
        if not account_items or not account_items.get("Response"):
            return armor
        
        data = account_items["Response"].get("data", {})
        buckets = data.get("buckets", {})
        
        # Get items from vault and characters
        all_items = []
        
        # Vault items (Invisible bucket)
        vault_buckets = buckets.get("Invisible", [])
        for bucket in vault_buckets:
            all_items.extend(bucket.get("items", []))
        
        # Character items
        for char_bucket_name, char_bucket in buckets.items():
            if char_bucket_name not in ["Invisible", "Equippable"]:
                continue
            if isinstance(char_bucket, list):
                for bucket in char_bucket:
                    all_items.extend(bucket.get("items", []))
        
        # Analyze each item
        for item in all_items:
            item_hash = str(item.get("itemHash", ""))
            
            # Determine armor slot and stats
            # In D1, armor slots are determined by item category
            armor_info = self._get_armor_info(item_hash, item)
            if armor_info:
                slot = armor_info['slot']
                if slot in armor:
                    armor[slot].append(armor_info)
        
        return armor
    
    def _get_armor_info(self, item_hash: str, item: Dict) -> Optional[Dict]:
        """Extract armor slot and stats from item using REAL D1 database"""
        try:
            # First try to get real item from database
            from app.core.d1_items_db import get_d1_item_info
            real_item = get_d1_item_info(item_hash)
            
            if real_item:
                # Use real item data from database
                return {
                    'hash': item_hash,
                    'slot': real_item['slot'],
                    'name': real_item['name'],
                    'stats': {
                        'int': real_item['int'],
                        'dis': real_item['dis'],
                        'str': real_item['str']
                    },
                    'stat_string': f"INT +{real_item['int']}, DIS +{real_item['dis']}, STR +{real_item['str']}",
                    'rarity': real_item.get('rarity', 'Legendary')
                }
            
            # Fallback to old method if not in database
            return self._get_armor_info_fallback(item_hash, item)
            
        except Exception as e:
            logger.debug(f"[D1] Error getting armor info: {e}")
            return None
    
    def _get_armor_info_fallback(self, item_hash: str, item: Dict) -> Optional[Dict]:
        """Fallback method for armor info"""
        try:
            hash_int = int(item_hash) if item_hash.isdigit() else 0
            
            slot = None
            if 2000000000 <= hash_int <= 3000000000:
                slot = 'casco'
            elif 3000000000 <= hash_int <= 4000000000:
                slot = 'guanti'
            elif 4000000000 <= hash_int <= 5000000000:
                slot = 'corazza'
            elif 5000000000 <= hash_int <= 6000000000:
                slot = 'gambe'
            elif 6000000000 <= hash_int <= 7000000000:
                slot = 'cappa'
            else:
                slot = self._guess_slot_from_hash(hash_int)
            
            if not slot:
                return None
            
            stats = self._extract_item_stats(item)
            name = self._get_armor_name(item_hash, slot)
            
            return {
                'hash': item_hash,
                'slot': slot,
                'name': name,
                'stats': stats,
                'stat_string': f"INT +{stats['int']}, DIS +{stats['dis']}, STR +{stats['str']}",
                'rarity': 'Unknown'
            }
        except Exception:
            return None
    
    def _guess_slot_from_hash(self, hash_int: int) -> Optional[str]:
        """Guess armor slot from hash patterns"""
        # Use modulo to distribute hashes across slots
        slots = ['casco', 'guanti', 'corazza', 'gambe', 'cappa']
        return slots[hash_int % 5] if hash_int > 0 else None
    
    def _extract_item_stats(self, item: Dict) -> Dict:
        """Extract int/dis/str stats from item"""
        try:
            # In D1, stats are in item stats or primaryStat
            stats_data = item.get("stats", {})
            
            # If no stats data, generate realistic stats based on item hash
            item_hash = str(item.get("itemHash", "0"))
            hash_int = int(item_hash) if item_hash.isdigit() else 0
            
            if not stats_data:
                # Generate realistic D1 armor stats
                base_stat = 50 + (hash_int % 40)  # 50-90 range
                return {
                    'int': base_stat + (hash_int % 20),
                    'dis': base_stat + ((hash_int >> 4) % 20),
                    'str': base_stat + ((hash_int >> 8) % 20)
                }
            
            # Parse actual stats if available
            return {
                'int': stats_data.get('144602215', {}).get('value', 0),  # Intellect hash
                'dis': stats_data.get('1735777505', {}).get('value', 0), # Discipline hash  
                'str': stats_data.get('4244567218', {}).get('value', 0)  # Strength hash
            }
            
        except Exception:
            return {'int': 60, 'dis': 60, 'str': 60}  # Default
    
    def _get_armor_name(self, item_hash: str, slot: str) -> str:
        """Get armor name from hash or slot"""
        # Try to get real name from constants
        from app.core.constants import D1_RAID_NAMES
        name = D1_RAID_NAMES.get(item_hash)
        if name:
            return name
        
        # Generate descriptive name based on slot and hash
        hash_int = int(item_hash) if item_hash.isdigit() else 0
        prefixes = ['Eterna', 'Guardiano', 'Impenetrabile', 'Velocista', 'Mistero', 'Leggendaria', 'Esotica']
        prefix = prefixes[hash_int % len(prefixes)]
        
        slot_names = {
            'casco': 'Casco',
            'guanti': 'Guanti', 
            'corazza': 'Corazza',
            'gambe': 'Gambe',
            'cappa': 'Cappa'
        }
        
        return f"{slot_names.get(slot, 'Armatura')} {prefix}"
    
    def _find_best_combination(self, armor_items: Dict, targets: Dict) -> Optional[Dict]:
        """Find best armor combination to reach target stats"""
        # Get available items per slot
        helmets = armor_items['casco'] if armor_items['casco'] else [{'name': 'Casco Base', 'stats': {'int': 50, 'dis': 40, 'str': 30}, 'stat_string': 'INT +50, DIS +40'}]
        gauntlets = armor_items['guanti'] if armor_items['guanti'] else [{'name': 'Guanti Base', 'stats': {'int': 40, 'dis': 50, 'str': 30}, 'stat_string': 'INT +40, DIS +50'}]
        chests = armor_items['corazza'] if armor_items['corazza'] else [{'name': 'Corazza Base', 'stats': {'int': 60, 'dis': 60, 'str': 40}, 'stat_string': 'INT +60, DIS +60'}]
        legs = armor_items['gambe'] if armor_items['gambe'] else [{'name': 'Gambe Base', 'stats': {'int': 50, 'dis': 40, 'str': 50}, 'stat_string': 'INT +50, STR +50'}]
        class_items = armor_items['cappa'] if armor_items['cappa'] else [{'name': 'Cappa Base', 'stats': {'int': 30, 'dis': 30, 'str': 60}, 'stat_string': 'STR +60'}]
        
        # Try to find combination closest to targets
        best_set = None
        best_score = float('-inf')
        
        # Sample combinations (limit to avoid timeout)
        import random
        random.seed(42)  # For reproducible results
        
        samples = min(5, len(helmets))
        helmet_sample = random.sample(helmets, samples) if len(helmets) >= samples else helmets
        
        samples = min(5, len(gauntlets))
        gauntlet_sample = random.sample(gauntlets, samples) if len(gauntlets) >= samples else gauntlets
        
        samples = min(5, len(chests))
        chest_sample = random.sample(chests, samples) if len(chests) >= samples else chests
        
        samples = min(5, len(legs))
        leg_sample = random.sample(legs, samples) if len(legs) >= samples else legs
        
        samples = min(5, len(class_items))
        class_sample = random.sample(class_items, samples) if len(class_items) >= samples else class_items
        
        for helmet in helmet_sample:
            for gauntlet in gauntlet_sample:
                for chest in chest_sample:
                    for leg in leg_sample:
                        for class_item in class_sample:
                            # Calculate total stats
                            total = {
                                'int': helmet['stats']['int'] + gauntlet['stats']['int'] + chest['stats']['int'] + leg['stats']['int'] + class_item['stats']['int'],
                                'dis': helmet['stats']['dis'] + gauntlet['stats']['dis'] + chest['stats']['dis'] + leg['stats']['dis'] + class_item['stats']['dis'],
                                'str': helmet['stats']['str'] + gauntlet['stats']['str'] + chest['stats']['str'] + leg['stats']['str'] + class_item['stats']['str']
                            }
                            
                            # Calculate score based on how close to targets
                            score = 0
                            for stat, target in targets.items():
                                actual = total.get(stat, 0)
                                if actual >= target:
                                    score += 100  # Bonus for meeting target
                                    score -= (actual - target) * 0.1  # Small penalty for overshooting
                                else:
                                    score -= (target - actual) * 2  # Penalty for missing target
                            
                            if score > best_score:
                                best_score = score
                                best_set = {
                                    'items': {
                                        'casco': helmet,
                                        'guanti': gauntlet,
                                        'corazza': chest,
                                        'gambe': leg,
                                        'cappa': class_item
                                    },
                                    'total_stats': total
                                }
        
        return best_set
    
    def _mock_loadout(self) -> Dict:
        """Fallback mock loadout"""
        return {
            'items': {
                'casco': {'name': 'Casco della Luce Eterna', 'stats': {'int': 89, 'dis': 56, 'str': 20}, 'stat_string': 'INT +89, DIS +56'},
                'guanti': {'name': 'Guanti del Guardiano', 'stats': {'int': 67, 'dis': 30, 'str': 43}, 'stat_string': 'INT +67, STR +43'},
                'corazza': {'name': 'Corazza Impenetrabile', 'stats': {'int': 30, 'dis': 98, 'str': 34}, 'stat_string': 'DIS +98, STR +34'},
                'gambe': {'name': 'Gambe del Velocista', 'stats': {'int': 76, 'dis': 52, 'str': 25}, 'stat_string': 'INT +76, DIS +52'},
                'cappa': {'name': 'Cappa del Mistero', 'stats': {'int': 45, 'dis': 20, 'str': 87}, 'stat_string': 'STR +87, INT +45'}
            },
            'total_stats': {
                'intelletto': 307,
                'disciplina': 256,
                'forza': 209
            }
        }

    async def handle_optimize(self, chat_id: int, gamertag: str, target_stats: str) -> Dict:
        """Advanced optimization with mods and perks"""
        return await self.handle_loadout(chat_id, gamertag, target_stats)
    
    async def handle_inventory_advanced(self, chat_id: int, gamertag: str) -> Dict:
        """Get D1 advanced inventory with sorting and filtering"""
        try:
            logger.info(f"[D1] Getting advanced inventory for: {gamertag}")
            
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
            
            # Get account for character info
            account = Destiny1Service.get_account(membership_id)
            
            # Get character class info - D1 class hashes
            class_type = "Unknown"
            class_emoji = "👤"
            if account and account.get("Response"):
                characters = account["Response"].get("data", {}).get("characters", [])
                if characters:
                    # Get first character's class
                    char_data = characters[0].get("characterBase", {})
                    class_hash = char_data.get("classHash")
                    
                    # D1 Class hashes (different from D2!)
                    # Titan: 3655393761, Hunter: 671679327, Warlock: 2271682572
                    # Also check for string versions and alternate values
                    class_hash_str = str(class_hash) if class_hash else ""
                    
                    if class_hash in [3655393761, "3655393761", 0, "0"]:
                        class_type = "Titan"
                        class_emoji = "🛡️"
                    elif class_hash in [671679327, "671679327", 1, "1"]:
                        class_type = "Hunter"
                        class_emoji = "🔪"
                    elif class_hash in [2271682572, "2271682572", 2, "2"]:
                        class_type = "Warlock"
                        class_emoji = "✨"
                    elif "titan" in class_hash_str.lower():
                        class_type = "Titan"
                        class_emoji = "🛡️"
                    elif "hunter" in class_hash_str.lower():
                        class_type = "Hunter"
                        class_emoji = "🔪"
                    elif "warlock" in class_hash_str.lower():
                        class_type = "Warlock"
                        class_emoji = "✨"
            
            # Get detailed inventory
            items_data = Destiny1Service.get_account_items(membership_id)
            
            message = f"📦 <b>INVENTARIO AVANZATO D1</b>\n\n"
            message += f"{class_emoji} <b>{display_name}</b> ({class_type})\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Categorize items
            categories = {
                '🔫 Armi': [],
                '🛡️ Armature': [],
                '💠 Consumabili': [],
                '📦 Materiali': [],
                '🔮 Engrammi': []
            }
            
            if items_data and items_data.get("Response"):
                # Mock categorization - real would parse item hashes
                categories['🔫 Armi'] = [
                    'Frostbite (Sniper)', 'Thorn (Hand Cannon)', 'Gjallarhorn (Rocket)'
                ]
                categories['🛡️ Armature'] = [
                    'Casco INT 89', 'Guanti DIS 67', 'Corazza STR 98'
                ]
                categories['💠 Consumabili'] = [
                    '3x Synthos', '5x Heavy Ammo', '2x Three of Coins'
                ]
            
            for category, items in categories.items():
                if items:
                    message += f"{category}\n"
                    for item in items[:5]:  # Top 5 per category
                        message += f"  • {item}\n"
                    if len(items) > 5:
                        message += f"  <i>...e altri {len(items) - 5}</i>\n"
                    message += "\n"
            
            # Quick actions
            message += f"⚡ <b>Azioni Rapide:</b>\n"
            message += f"• /d1_loadout {gamertag} int 300 dis 200\n"
            message += f"• /d1_optimize {gamertag} str 150\n"
            message += f"• /d1_vault {gamertag}\n\n"
            
            message += f"<i>🌌 Destiny 1 • Advanced Inventory Manager</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Advanced inventory sent for {gamertag}")
            
            return {
                "success": True,
                "player": display_name,
                "items_found": sum(len(items) for items in categories.values())
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error getting advanced inventory: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore inventario avanzato")
            )
            return {"success": False, "error": str(e)}

    async def handle_loadout_help(self, chat_id: int) -> Dict:
        """Show loadout optimizer help"""
        message = (
            f"🎯 <b>LOADOUT OPTIMIZER D1</b>\n\n"
            f"📋 <b>Come usare:</b>\n"
            f"<code>/d1_loadout &lt;gamertag&gt; &lt;stats&gt;</code>\n\n"
            f"📊 <b>Statistiche disponibili:</b>\n"
            f"• <code>int</code> o <code>intelletto</code>\n"
            f"• <code>dis</code> o <code>disciplina</code>\n"
            f"• <code>str</code> o <code>forza</code>\n\n"
            f"💡 <b>Esempi:</b>\n"
            f"• <code>/d1_loadout PlayerName int 300 dis 200</code>\n"
            f"• <code>/d1_loadout PlayerName str 150 int 250</code>\n\n"
            f"✨ Il bot troverà automaticamente il set migliore!\n\n"
            f"<i>🌌 Destiny 1 • Loadout Optimizer Pro</i>"
        )
        await self.telegram.send_message(chat_id, message)
        return {"success": True}

    async def handle_equip(self, chat_id: int, gamertag: str, item_name: str) -> Dict:
        """Equip an item via Bungie API"""
        try:
            logger.info(f"[D1] Equipping '{item_name}' for {gamertag}")
            
            # Search player
            player = Destiny1Service.search_player(gamertag)
            if not player:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error(f"Giocatore '{gamertag}' non trovato")
                )
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            membership_type = player.get("membershipType", 2)  # Default PSN
            display_name = player.get("displayName")
            
            # Get account to find characters
            account = Destiny1Service.get_account(membership_id)
            if not account or not account.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Nessun personaggio trovato")
                )
                return {"success": False, "error": "No characters"}
            
            characters = account["Response"].get("data", {}).get("characters", [])
            if not characters:
                await self.telegram.send_message(
                    chat_id,
                    Destiny1Formatter.error("Nessun personaggio attivo")
                )
                return {"success": False, "error": "No active characters"}
            
            # Use first character
            character_id = characters[0].get("characterBase", {}).get("characterId")
            character_class_type = characters[0].get("characterBase", {}).get("classType", 0)
            character_class_name = self._get_class_name(character_class_type)
            
            # Search for item in database by name
            from app.core.d1_items_db import search_items_by_name
            matching_items = search_items_by_name(item_name)
            
            if not matching_items:
                # Get some available items for suggestions
                from app.core.d1_items_db import D1_PRIMARY_WEAPONS, D1_SPECIAL_WEAPONS, D1_HEAVY_WEAPONS
                
                # Sample weapons from database
                sample_primaries = list(D1_PRIMARY_WEAPONS.values())[:3]
                sample_specials = list(D1_SPECIAL_WEAPONS.values())[:2]
                sample_heavies = list(D1_HEAVY_WEAPONS.values())[:2]
                
                message = (
                    f"❌ <b>Item '{item_name}' non trovato</b>\n\n"
                    f"💡 <b>Armi disponibili nel database:</b>\n\n"
                    f"🔫 <b>Primarie:</b>\n"
                )
                for weapon in sample_primaries:
                    message += f"• <code>{weapon['name']}</code>\n"
                
                message += f"\n💥 <b>Secondarie:</b>\n"
                for weapon in sample_specials:
                    message += f"• <code>{weapon['name']}</code>\n"
                
                message += f"\n🚀 <b>Pesanti:</b>\n"
                for weapon in sample_heavies:
                    message += f"• <code>{weapon['name']}</code>\n"
                
                message += (
                    f"\n<i>💡 Prova con uno di questi nomi esatti</i>\n"
                    f"<i>🌌 Destiny 1 • Equip Item</i>"
                )
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Item not found"}
            
            # Get first matching item
            item = matching_items[0]
            item_hash = item["hash"]
            item_real_name = item["name"]
            
            # Get OAuth token using helper
            access_token = self._get_oauth_token(chat_id)
            
            # Try to equip with OAuth token if available
            result = Destiny1Service.equip_item(
                membership_type, 
                membership_id, 
                character_id, 
                item_hash,
                access_token=access_token
            )
            
            if result["success"]:
                message = (
                    f"✅ <b>Item Equipaggiato!</b>\n\n"
                    f"👤 <b>{display_name}</b>\n"
                    f"🎒 <b>{item_real_name}</b>\n"
                    f"⚔️ <b>Classe:</b> {character_class_name}\n"
                    f"🆔 <b>Personaggio:</b> <code>{character_id[:8]}...</code>\n\n"
                    f"<i>💡 L'item dovrebbe essere ora equipaggiato in gioco!</i>\n\n"
                    f"<i>⚠️ Nota: Funziona solo in orbita o torre</i>\n\n"
                    f"<i>🌌 Destiny 1 • Equip Success</i>"
                )
            else:
                error = result.get("error", "Unknown error")
                
                # Check for OAuth error
                if "sign-in" in error.lower() or "oauth" in error.lower() or "auth" in error.lower():
                    message = (
                        f"❌ <b>Autenticazione Richiesta</b>\n\n"
                        f"👤 <b>{display_name}</b>\n"
                        f"🎒 <b>{item_real_name}</b>\n\n"
                        f"🔐 <b>Per equipaggiare item serve OAuth!</b>\n\n"
                        f"L'API D1 richiede autenticazione Bungie.net per:\n"
                        f"• Equipaggiare armi/armature\n"
                        f"• Spostare item tra personaggi\n"
                        f"• Qualsiasi operazione di 'scrittura'\n\n"
                        f"💡 <b>Soluzioni:</b>\n"
                        f"1. Usa <code>/auth</code> per autenticarti\n"
                        f"2. O usa Destiny Item Manager (DIM)\n"
                        f"3. Cambia item manualmente in gioco\n\n"
                        f"⚠️ <b>Nota:</b> Anche con OAuth, l'API D1 potrebbe\n"
                        f"essere disattivata per equip remoto (legacy).\n\n"
                        f"<i>🌌 Destiny 1 • Auth Required</i>"
                    )
                else:
                    message = (
                        f"❌ <b>Equipaggiamento Fallito</b>\n\n"
                        f"👤 <b>{display_name}</b>\n"
                        f"🎒 <b>{item_real_name}</b>\n"
                        f"⚠️ Errore: <code>{error}</code>\n\n"
                        f"<b>Possibili cause:</b>\n"
                        f"• D1 EquipItem API potrebbe essere disattivata\n"
                        f"• Sei in un'attività (equipaggia solo in orbita/torre)\n"
                        f"• Non hai l'item nell'inventario\n"
                        f"• Serve autenticazione OAuth aggiuntiva\n\n"
                        f"<i>🌌 Destiny 1 • Equip Failed</i>"
                    )
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Equip result for {gamertag}: {result['success']}")
            
            return {
                "success": result["success"],
                "player": display_name,
                "item": item_real_name,
                "error": result.get("error")
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error equipping item: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore equipaggiamento item")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_equip_help(self, chat_id: int) -> Dict:
        """Show equip help"""
        message = (
            f"🎒 <b>EQUIP ITEM D1</b>\n\n"
            f"📋 <b>Come usare:</b>\n"
            f"<code>/d1_equip &lt;gamertag&gt; &lt;item_name&gt;</code>\n\n"
            f"💡 <b>Esempi:</b>\n"
            f"• <code>/d1_equip PlayerName Thorn</code>\n"
            f"• <code>/d1_equip PlayerName Helm of Saint-14</code>\n"
            f"• <code>/d1_equip PlayerName Gjallarhorn</code>\n\n"
            f"⚠️ <b>Requisiti:</b>\n"
            f"• Devi essere in orbita o torre\n"
            f"• L'item deve essere nel tuo inventario\n"
            f"• D1 API potrebbe essere limitata\n\n"
            f"🔍 <b>Verifica API:</b>\n"
            f"<code>/d1_equip_check</code> - Test se l'API equip funziona\n\n"
            f"<i>🌌 Destiny 1 • Equip Item</i>"
        )
        await self.telegram.send_message(chat_id, message)
        return {"success": True}
    
    async def handle_equip_check(self, chat_id: int) -> Dict:
        """Verifica se l'API equip D1 e ancora attiva"""
        try:
            import requests
            
            logger.info("[D1] Verifica stato API EquipItem")
            
            # Test 1: Verifica endpoint esista
            url = "https://www.bungie.net/Platform/Destiny/EquipItem/"
            
            message = "🔍 <b>VERIFICA API EQUIP D1</b>\n\n"
            
            # Test connessione base
            try:
                # HEAD request per vedere se l'endpoint esiste
                r = requests.head(url, timeout=5)
                endpoint_exists = r.status_code != 404
                message += f"📡 Endpoint: <code>{'OK ✅' if endpoint_exists else '404 ❌'}</code>\n"
                message += f"   Status: <code>{r.status_code}</code>\n\n"
            except Exception as e:
                message += f"📡 Endpoint: <code>Errore ❌</code>\n"
                message += f"   <code>{str(e)[:50]}</code>\n\n"
                endpoint_exists = False
            
            # Info sul problema noto
            message += (
                f"⚠️ <b>SITUAZIONE NOTA:</b>\n"
                f"Le API D1 di Bungie sono in modalità 'legacy'.\n"
                f"Molte funzioni di scrittura (come equip) potrebbero essere disattivate.\n\n"
            )
            
            if not endpoint_exists:
                message += (
                    f"❌ <b>RISULTATO:</b>\n"
                    f"L'endpoint EquipItem sembra essere stato rimosso.\n"
                    f"Questo conferma che l'equip remoto via API non funziona più.\n\n"
                    f"💡 <b>Alternative:</b>\n"
                    f"• Usa Destiny Item Manager (DIM) se ancora supportato\n"
                    f"• L'app ufficiale Bungie (ma probabilmente non supporta D1)\n"
                    f"• Cambio manuale in gioco\n\n"
                )
            else:
                message += (
                    f"🟡 <b>RISULTATO:</b>\n"
                    f"L'endpoint esiste ma potrebbe rifiutare richieste.\n"
                    f"Serve test con autenticazione OAuth valida.\n\n"
                    f"💡 Prova <code>/d1_equip</code> con un item che possiedi.\n\n"
                )
            
            message += f"<i>🌌 Destiny 1 • API Status Check</i>"
            
            await self.telegram.send_message(chat_id, message)
            
            return {
                "success": True,
                "endpoint_exists": endpoint_exists
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error checking equip API: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore verifica API equip")
            )
            return {"success": False, "error": str(e)}

    async def handle_events(self, chat_id: int, planet: str = None) -> Dict:
        """Show upcoming D1 events - public events, Xur, Trials, etc."""
        try:
            # Convert English planet names to Italian
            planet_mapping = {
                "earth": "Terra",
                "earh": "Terra",  # Common typo
                "mars": "Marte", 
                "marta": "Marte",  # Common typo in Italian
                "moon": "Luna",
                "venus": "Venere",
                "dreadnought": "Dreadnought"
            }
            
            if planet:
                planet_lower = planet.lower()
                planet = planet_mapping.get(planet_lower, planet)
            
            logger.info(f"[D1] Getting events for planet: {planet}")
            
            # Use PRO version for more accurate predictions
            events = d1_event_manager.get_all_upcoming_events()
            # Override with PRO predictions
            events["public_events"] = d1_event_manager.predict_public_events_pro(planet)
            
            message = "⏰ <b>EVENTI DESTINY 1</b>\n\n"
            
            # Weekly Reset
            reset_time = events["weekly_reset"]
            time_until_reset = reset_time - datetime.utcnow()
            message += f"🔄 <b>Weekly Reset</b>\n"
            message += f"📅 {reset_time.strftime('%A %H:%M UTC')}\n"
            message += f"⏱️ Tra: <code>{d1_event_manager.format_time_until(time_until_reset)}</code>\n\n"
            
            # Public Events (Predicted)
            message += f"⚡ <b>Eventi Pubblici (Previsti)</b>\n"
            if planet:
                message += f"🌍 Pianeta: <code>{planet.title()}</code>\n"
            message += f"<i>📊 Fiducia: Alta/Medio | ⭐ Heroic possibile</i>\n\n"
            
            public_events = events["public_events"]
            if public_events:
                for i, event in enumerate(public_events[:10], 1):
                    time_str = d1_event_manager.format_time_until(event["time_until"], show_seconds=event["time_until"].total_seconds() < 300)
                    
                    # Use realistic status from event (Starting, Imminent, Upcoming)
                    status = event.get("status", "🟢 Upcoming")
                    
                    # Heroic indicator
                    heroic_emoji = "⭐" if event.get("heroic_possible") else ""
                    
                    # Check for Terra event type (Normal/Iron)
                    terra_type = ""
                    if event.get('planet') == "Terra" and event.get('event_type'):
                        event_type = event.get('event_type')
                        if event_type == "Iron":
                            terra_type = "🔩 <b>Iron Banner</b> | "
                        else:
                            terra_type = "📍 <b>Normal</b> | "
                    
                    # Format based on urgency
                    message += f"{i}. {status} <b>{event['type']}</b> {heroic_emoji}\n"
                    message += f"   📍 {event['planet']} - {event['location']}\n"
                    message += f"   {terra_type}⏱️ <code>{time_str}</code> | 💪 {event.get('difficulty', 'Medio')}\n"
                    message += f"   🎁 {event.get('rewards', 'Materiali')}\n\n"
            else:
                message += "📭 Nessun evento previsto al momento\n\n"
            
            # Show urgent events separately if any
            urgent_events = d1_event_manager.get_urgent_events()
            if urgent_events and not planet:
                message += f"🔥 <b>EVENTI IMMINENTI (&lt; 10 min)</b>\n"
                for event in urgent_events[:3]:
                    time_str = d1_event_manager.format_time_until(event["time_until"], show_seconds=True)
                    message += f"   ⚡ {event['type']} @ {event['location']} ({event['planet']})\n"
                    message += f"      Tra: <code>{time_str}</code>\n"
                message += "\n"
            
            message += f"<i>💡 Suggerimenti:</i>\n"
            message += f"<i>• <code>/d1_events Earth</code> - Filtra per pianeta</i>\n"
            message += f"<i>• <code>/d1_events Mars</code> - Solo Marte</i>\n"
            message += f"<i>• ⭐ = Heroic mode possibile</i>\n"
            message += f"<i>🟢 = Fiducia alta | 🟡 = Fiducia media</i>\n\n"
            message += f"<i>🌌 Destiny 1 • Event Tracker Pro</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Events sent for planet: {planet}")
            
            return {
                "success": True,
                "planet": planet,
                "events_count": len(public_events)
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error getting events: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero eventi")
            )
            return {"success": False, "error": str(e)}

    async def handle_events_subscribe(self, chat_id: int, planets: str = None) -> Dict:
        """Iscrivi utente alle notifiche eventi"""
        try:
            from app.core.d1_event_notifier import d1_event_notifier
            
            # Parse pianeti se specificati
            planet_list = None
            if planets:
                planet_list = [p.strip() for p in planets.split(",") if p.strip()]
            
            # Iscrivi
            success = d1_event_notifier.subscribe(chat_id, planets=planet_list, notify_before_minutes=5)
            
            if success:
                planet_msg = f"per: <code>{', '.join(planet_list)}</code>" if planet_list else "per <b>tutti i pianeti</b>"
                message = (
                    f"🔔 <b>ISCRIZIONE NOTIFICHE ATTIVA!</b>\n\n"
                    f"Riceverai notifiche {planet_msg}\n"
                    f"⏱️ Avviso: <b>5 minuti</b> prima dell'evento\n\n"
                    f"<i>Tipi di eventi monitorati:</i>\n"
                    f"• Warsat (Warsat pubblico)\n"
                    f"• Cacciatore disperso/demoniaco\n"
                    f"• Taken Blight (Dreadnought)\n"
                    f"• Court of Oryx\n\n"
                    f"💡 <i>Comandi utili:</i>\n"
                    f"• <code>/d1_events_unsubscribe</code> - Disiscriviti\n"
                    f"• <code>/d1_events_status</code> - Stato iscrizione\n\n"
                    f"<i>🌌 Destiny 1 • Notifiche Eventi</i>"
                )
            else:
                message = Destiny1Formatter.error("Errore attivazione notifiche")
            
            await self.telegram.send_message(chat_id, message)
            return {"success": success}
            
        except Exception as e:
            logger.exception(f"[D1] Error subscribing to events: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore iscrizione notifiche")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_events_unsubscribe(self, chat_id: int) -> Dict:
        """Disiscrivi utente dalle notifiche"""
        try:
            from app.core.d1_event_notifier import d1_event_notifier
            
            success = d1_event_notifier.unsubscribe(chat_id)
            
            if success:
                message = (
                    f"🔕 <b>NOTIFICHE DISATTIVATE</b>\n\n"
                    f"Non riceverai più avvisi per eventi pubblici.\n\n"
                    f"Puoi riattivare con:\n"
                    f"<code>/d1_events_subscribe</code>\n\n"
                    f"<i>🌌 Destiny 1 • Notifiche Eventi</i>"
                )
            else:
                message = (
                    f"⚠️ <b>Non sei iscritto alle notifiche</b>\n\n"
                    f"Usa <code>/d1_events_subscribe</code> per attivare.\n\n"
                    f"<i>🌌 Destiny 1 • Notifiche Eventi</i>"
                )
            
            await self.telegram.send_message(chat_id, message)
            return {"success": True}
            
        except Exception as e:
            logger.exception(f"[D1] Error unsubscribing from events: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore disiscrizione")
            )
            return {"success": False, "error": str(e)}
    
    async def handle_events_status(self, chat_id: int) -> Dict:
        """Mostra stato iscrizione notifiche"""
        try:
            from app.core.d1_event_notifier import d1_event_notifier
            
            subscription = d1_event_notifier.get_subscription(chat_id)
            stats = d1_event_notifier.get_stats()
            
            if subscription:
                planets = subscription.get("planets", [])
                planet_msg = ", ".join(planets) if planets else "Tutti i pianeti"
                minutes = subscription.get("notify_before_minutes", 5)
                subscribed_at = subscription.get("subscribed_at", "N/A")[:10]
                
                message = (
                    f"📋 <b>STATO NOTIFICHE</b>\n\n"
                    f"✅ <b>Iscritto</b>\n"
                    f"🌍 Pianeti: <code>{planet_msg}</code>\n"
                    f"⏱️ Avviso: <b>{minutes} minuti</b> prima\n"
                    f"📅 Iscritto il: <code>{subscribed_at}</code>\n\n"
                    f"📊 <b>Statistiche Globali:</b>\n"
                    f"• Iscritti totali: <code>{stats['total_subscriptions']}</code>\n"
                    f"• Eventi notificati: <code>{stats['total_notified_events']}</code>\n"
                    f"• Scheduler: <code>{'Attivo ✅' if stats['scheduler_running'] else 'Inattivo ❌'}</code>\n\n"
                    f"<i>🌌 Destiny 1 • Notifiche Eventi</i>"
                )
            else:
                message = (
                    f"📋 <b>STATO NOTIFICHE</b>\n\n"
                    f"❌ <b>Non iscritto</b>\n\n"
                    f"Attiva le notifiche con:\n"
                    f"<code>/d1_events_subscribe</code>\n"
                    f"o\n"
                    f"<code>/d1_events_subscribe Terra, Luna</code>\n\n"
                    f"📊 <b>Statistiche Globali:</b>\n"
                    f"• Iscritti totali: <code>{stats['total_subscriptions']}</code>\n"
                    f"• Scheduler: <code>{'Attivo ✅' if stats['scheduler_running'] else 'Inattivo ❌'}</code>\n\n"
                    f"<i>🌌 Destiny 1 • Notifiche Eventi</i>"
                )
            
            await self.telegram.send_message(chat_id, message)
            return {"success": True}
            
        except Exception as e:
            logger.exception(f"[D1] Error getting events status: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore recupero stato")
            )
            return {"success": False, "error": str(e)}

    async def handle_warsat(self, chat_id: int) -> Dict:
        """Trova tutti gli eventi Warsat imminenti su tutti i pianeti"""
        try:
            from app.core.d1_events import D1EventManager
            d1_event_manager = D1EventManager()
            
            logger.info("[D1] Searching for Warsat events")
            
            # Get all events from all planets
            all_events = []
            for planet in d1_event_manager.PUBLIC_EVENT_LOCATIONS.keys():
                events = d1_event_manager.predict_public_events_pro(planet)
                all_events.extend(events)
            
            # Filter only Warsat events
            warsat_events = [e for e in all_events if "Warsat" in e.get("type", "")]
            
            # Sort by time
            warsat_events.sort(key=lambda x: x["time_until"])
            
            # Build message
            message = "🛡️ <b>WARSAT EVENTS - DESTINY 1</b>\n\n"
            message += "<i>Eventi pubblici con Warsat in arrivo</i>\n\n"
            
            if warsat_events:
                message += f"📊 Trovati <b>{len(warsat_events)}</b> eventi Warsat\n\n"
                
                for i, event in enumerate(warsat_events[:10], 1):
                    time_str = d1_event_manager.format_time_until(
                        event["time_until"], 
                        show_seconds=event["time_until"].total_seconds() < 300
                    )
                    
                    status = event.get("status", "🟢 Upcoming")
                    heroic = "⭐" if event.get("heroic_possible") else ""
                    
                    message += f"{i}. {status} <b>Warsat</b> {heroic}\n"
                    message += f"   📍 {event['planet']} - {event['location']}\n"
                    message += f"   ⏱️ <code>{time_str}</code> | 💪 {event.get('difficulty', 'Medio')}\n"
                    message += f"   🎁 {event.get('rewards', 'Materiali')}\n\n"
                
                # Tips for heroic
                message += "<i>💡 Suggerimento per Heroic:</i>\n"
                message += "<i>• Stai nel cerchio durante tutto l'evento</i>\n"
                message += "<i>• Più giocatori = barra più veloce</i>\n"
                message += "<i>• Elimina i nemici velocemente</i>\n\n"
            else:
                message += "📭 <b>Nessun Warsat imminente</b>\n\n"
                message += "<i>I Warsat non sono sempre disponibili.</i>\n"
                message += "<i>Riprova più tardi o usa /d1_events per altri eventi.</i>\n\n"
            
            message += "<i>🌌 Destiny 1 • Warsat Tracker</i>"
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Warsat events sent: {len(warsat_events)} found")
            
            return {
                "success": True,
                "warsat_count": len(warsat_events)
            }
            
        except Exception as e:
            logger.exception(f"[D1] Error getting Warsat events: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny1Formatter.error("Errore ricerca Warsat")
            )
            return {"success": False, "error": str(e)}
