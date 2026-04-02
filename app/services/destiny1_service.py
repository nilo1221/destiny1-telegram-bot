import requests
import logging
from typing import Optional, Dict
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("destiny1")

HEADERS = {"X-API-Key": settings.bungie_api_key}
MEMBERSHIP_TYPE_PSN = 2


class Destiny1Service:
    """Destiny 1 Legacy API Service"""

    @staticmethod
    def normalize_gamertag(tag: str) -> str:
        return tag.strip().replace(" ", "_")

    @staticmethod
    def search_player(gamertag: str, membership_type: int = None) -> Optional[Dict]:
        """Search player across all platforms or specific platform"""
        gamertag = Destiny1Service.normalize_gamertag(gamertag)
        
        # Try specific platform first, then all platforms
        platforms = [membership_type] if membership_type else [2, 1, 3]  # PSN, Xbox, Steam
        
        for platform in platforms:
            url = f"https://www.bungie.net/Platform/Destiny/SearchDestinyPlayer/{platform}/{gamertag}/"
            
            try:
                logger.info(f"[D1] Searching player '{gamertag}' on platform {platform}")
                r = requests.get(url, headers=HEADERS, timeout=10)
                r.raise_for_status()
                data = r.json()
                
                # Debug logging
                logger.debug(f"[D1] API Response: {data}")
                
                if data.get("Response") and len(data["Response"]) > 0:
                    player = data["Response"][0]
                    logger.info(f"[D1] Player found on platform {platform}: {player.get('displayName')}")
                    return player
                else:
                    logger.debug(f"[D1] No results on platform {platform}")
                    
            except Exception as e:
                logger.error(f"[D1] Error searching platform {platform}: {e}")
                continue
        
        logger.warning(f"[D1] Player not found on any platform: {gamertag}")
        return None

    @staticmethod
    def get_account(membership_id: str) -> Optional[Dict]:
        url = f"https://www.bungie.net/Platform/Destiny/{MEMBERSHIP_TYPE_PSN}/Account/{membership_id}/Summary/"
        try:
            logger.info(f"[D1] Getting account: {membership_id}")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting account: {e}")
            return None

    @staticmethod
    def get_recent_activities(membership_id: str, character_id: str) -> Optional[Dict]:
        url = (
            f"https://www.bungie.net/Platform/Destiny/Stats/ActivityHistory/{MEMBERSHIP_TYPE_PSN}/"
            f"Account/{membership_id}/Character/{character_id}/?count=10"
        )
        try:
            logger.info(f"[D1] Getting activities: {membership_id}/{character_id}")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting activities: {e}")
            return None

    @staticmethod
    def get_raid_history(membership_id: str, character_id: str) -> Optional[Dict]:
        url = (
            f"https://www.bungie.net/Platform/Destiny/Stats/AggregateActivityStats/"
            f"{MEMBERSHIP_TYPE_PSN}/{membership_id}/{character_id}/"
        )
        try:
            logger.info(f"[D1] Getting raid history: {membership_id}/{character_id}")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting raid history: {e}")
            return None

    @staticmethod
    def get_account_items(membership_id: str) -> Optional[Dict]:
        """Get D1 account items (inventory across all characters)"""
        url = f"https://www.bungie.net/Platform/Destiny/{MEMBERSHIP_TYPE_PSN}/Account/{membership_id}/Items/"
        try:
            logger.info(f"[D1] Getting account items: {membership_id}")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting account items: {e}")
            return None

    @staticmethod
    def get_character_inventory(membership_id: str, character_id: str) -> Optional[Dict]:
        """Get D1 character inventory (items equipped and in inventory)"""
        url = (
            f"https://www.bungie.net/Platform/Destiny/{MEMBERSHIP_TYPE_PSN}/"
            f"Account/{membership_id}/Character/{character_id}/Inventory/"
        )
        try:
            logger.info(f"[D1] Getting character inventory: {membership_id}/{character_id}")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting character inventory: {e}")
            return None

    @staticmethod
    def get_vault(membership_id: str) -> Optional[Dict]:
        """Get D1 vault items (account-wide shared inventory)"""
        url = f"https://www.bungie.net/Platform/Destiny/{MEMBERSHIP_TYPE_PSN}/MyAccount/Vault/"
        try:
            logger.info(f"[D1] Getting vault: {membership_id}")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting vault: {e}")
            return None

    @staticmethod
    def get_advisors() -> Optional[Dict]:
        """Get weekly advisors including Xur, Nightfall, Trials"""
        url = "https://www.bungie.net/Platform/Destiny/Advisors/?definitions=true"
        try:
            logger.info("[D1] Getting advisors (Xur, Nightfall, Trials)")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting advisors: {e}")
            return None

    @staticmethod
    def get_character_stats(membership_id: str, character_id: str) -> Optional[Dict]:
        """Get detailed character statistics"""
        url = (
            f"https://www.bungie.net/Platform/Destiny/Stats/CharacterStats/"
            f"{MEMBERSHIP_TYPE_PSN}/{membership_id}/{character_id}/"
        )
        try:
            logger.info(f"[D1] Getting character stats: {membership_id}/{character_id}")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting character stats: {e}")
            return None

    @staticmethod
    def get_vault_inventory(membership_id: str) -> Optional[Dict]:
        """Get vault inventory"""
        url = f"https://www.bungie.net/Platform/Destiny/{MEMBERSHIP_TYPE_PSN}/Account/{membership_id}/Items/"
        try:
            logger.info(f"[D1] Getting vault inventory: {membership_id}")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting vault inventory: {e}")
            return None

    @staticmethod
    def get_item_definition(item_hash: str) -> Optional[Dict]:
        """Get item definition/details from manifest"""
        url = f"https://www.bungie.net/Platform/Destiny/Manifest/InventoryItem/{item_hash}/"
        try:
            logger.info(f"[D1] Getting item definition: {item_hash}")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting item definition: {e}")
            return None

    @staticmethod
    def get_manifest() -> Optional[Dict]:
        """Get D1 manifest (database interno)"""
        url = "https://www.bungie.net/Platform/Destiny/Manifest/"
        try:
            logger.info("[D1] Getting manifest")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting manifest: {e}")
            return None

    @staticmethod
    def get_character_progression(membership_id: str, character_id: str) -> Optional[Dict]:
        """Get character progression/factions"""
        url = f"https://www.bungie.net/Platform/Destiny/1/Account/{membership_id}/Character/{character_id}/Progression/"
        try:
            logger.info(f"[D1] Getting character progression: {membership_id}/{character_id}")
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting character progression: {e}")
            return None
