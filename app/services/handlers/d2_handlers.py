"""
Destiny 2 specific command handlers
"""
import logging
from typing import Dict
from app.services.adapters import BungieAdapter, TelegramAdapter
from app.services.formatting import Destiny2Formatter
from app.core.constants import MembershipType

logger = logging.getLogger("destiny2_handlers")


class D2CommandHandlers:
    """Handlers for Destiny 2 specific commands"""
    
    def __init__(self, bungie: BungieAdapter, telegram: TelegramAdapter):
        self.bungie = bungie
        self.telegram = telegram
    
    async def handle_find_player(self, chat_id: int, gamertag: str) -> Dict:
        """
        Search for a Destiny 2 player on Steam
        
        Args:
            chat_id: Telegram chat ID
            gamertag: Player gamertag to search
            
        Returns:
            Dict with success status and player info
        """
        try:
            logger.info(f"[D2] Searching player: {gamertag}")
            
            search_data = await self.bungie.search_player(
                membership_type=MembershipType.STEAM,
                display_name=gamertag
            )
            
            if not search_data.get("Response"):
                message = Destiny2Formatter.player_not_found(gamertag, "Steam")
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Player not found"}
            
            player = search_data["Response"][0]
            
            message = Destiny2Formatter.player_found(
                player["displayName"],
                player["membershipId"],
                "Steam"
            )
            await self.telegram.send_message(chat_id, message)
            
            logger.info(f"[D2] Player found: {player['displayName']}")
            return {
                "success": True,
                "player": {
                    "display_name": player["displayName"],
                    "membership_id": player["membershipId"],
                    "membership_type": MembershipType.STEAM
                }
            }
            
        except Exception as e:
            logger.exception(f"[D2] Error finding player {gamertag}: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny2Formatter.internal_error()
            )
            return {"success": False, "error": str(e)}
    
    async def handle_get_activities(self, chat_id: int, gamertag: str, mode: int = 0) -> Dict:
        """Get Destiny 2 activity history"""
        try:
            logger.info(f"[D2] Getting activities for: {gamertag}, mode: {mode}")
            
            # Search player
            search_data = await self.bungie.search_player(
                membership_type=MembershipType.STEAM,
                display_name=gamertag
            )
            
            if not search_data.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    Destiny2Formatter.player_not_found(gamertag)
                )
                return {"success": False, "error": "Player not found"}
            
            player = search_data["Response"][0]
            membership_id = player["membershipId"]
            display_name = player["displayName"]
            
            # Get profile to find characters
            profile_data = await self.bungie.get_profile(
                membership_type=MembershipType.STEAM,
                membership_id=membership_id,
                components=["characters"]
            )
            
            characters = profile_data.get("Response", {}).get("characters", {}).get("data", {})
            if not characters:
                await self.telegram.send_message(
                    chat_id,
                    f"📭 Nessun personaggio trovato per {display_name}."
                )
                return {"success": False, "error": "No characters"}
            
            # Use first character
            character_id = list(characters.keys())[0]
            
            # Get activity history
            activities_data = await self.bungie.get_activity_history(
                membership_type=MembershipType.STEAM,
                membership_id=membership_id,
                character_id=character_id,
                mode=mode,
                count=10
            )
            
            activities = activities_data.get("Response", {}).get("activities", [])
            
            if activities:
                activity_list = []
                for i, activity in enumerate(activities[:10], 1):
                    period = activity.get("period", "Unknown")[:10]
                    mode_name = activity.get("activityDetails", {}).get("mode", "Unknown")
                    activity_list.append(f"{i}. 📅 {period} - {mode_name}")
                
                activities_text = "\n".join(activity_list)
            else:
                activities_text = "📭 Nessuna attività recente"
            
            message = (
                f"📊 <b>Attività recenti di {display_name}</b>\n\n"
                f"{activities_text}\n\n"
                f"<i>Destiny 2</i>"
            )
            await self.telegram.send_message(chat_id, message)
            
            logger.info(f"[D2] Activities sent for {gamertag}")
            return {"success": True, "activities_count": len(activities)}
            
        except Exception as e:
            logger.exception(f"[D2] Error getting activities: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny2Formatter.internal_error()
            )
            return {"success": False, "error": str(e)}
    
    async def handle_raid_history(self, chat_id: int, gamertag: str) -> Dict:
        """Get Destiny 2 raid history and stats"""
        try:
            logger.info(f"[D2] Getting raid history: {gamertag}")
            
            # Search player
            search_data = await self.bungie.search_player(
                membership_type=MembershipType.STEAM,
                display_name=gamertag
            )
            
            if not search_data.get("Response"):
                await self.telegram.send_message(
                    chat_id,
                    Destiny2Formatter.player_not_found(gamertag)
                )
                return {"success": False, "error": "Player not found"}
            
            player = search_data["Response"][0]
            membership_id = player["membershipId"]
            display_name = player["displayName"]
            
            # Get raid stats (simplified - actual implementation would use specific endpoints)
            message = (
                f"🎮 <b>Storico Raid D2 - {display_name}</b>\n\n"
                f"📭 Funzionalità in sviluppo per D2.\n\n"
                f"<i>Destiny 2 - Steam</i>"
            )
            await self.telegram.send_message(chat_id, message)
            
            return {"success": True}
            
        except Exception as e:
            logger.exception(f"[D2] Error getting raid history: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny2Formatter.internal_error()
            )
            return {"success": False, "error": str(e)}
    
    async def handle_xur(self, chat_id: int) -> Dict:
        """Get Xur inventory for D2"""
        try:
            logger.info("[D2] Getting Xur status")
            
            # D2 Xur endpoint would be implemented here
            message = (
                "👳‍♂️ <b>Xûr (Destiny 2)</b>\n\n"
                "📍 Funzionalità in sviluppo.\n\n"
                "<i>Destiny 2</i>"
            )
            await self.telegram.send_message(chat_id, message)
            
            return {"success": True}
            
        except Exception as e:
            logger.exception(f"[D2] Error getting Xur: {e}")
            await self.telegram.send_message(
                chat_id,
                Destiny2Formatter.internal_error()
            )
            return {"success": False, "error": str(e)}
