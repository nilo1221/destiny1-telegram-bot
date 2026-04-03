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
    def get_account(membership_id: str, access_token: str = None) -> Optional[Dict]:
        url = f"https://www.bungie.net/Platform/Destiny/{MEMBERSHIP_TYPE_PSN}/Account/{membership_id}/Summary/"
        try:
            logger.info(f"[D1] Getting account: {membership_id}")
            
            # Prepare headers with OAuth if provided
            headers = HEADERS.copy()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
            
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            # Check if API returned error
            if data.get("ErrorCode") != 1:
                logger.error(f"[D1] API error: {data.get('Message', 'Unknown error')}")
                return None
                
            return data
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
    def get_account_items(membership_id: str, access_token: str = None) -> Optional[Dict]:
        """Get D1 account items (inventory across all characters)"""
        url = f"https://www.bungie.net/Platform/Destiny/{MEMBERSHIP_TYPE_PSN}/Account/{membership_id}/Items/"
        try:
            logger.info(f"[D1] Getting account items: {membership_id}")
            
            # Prepare headers with OAuth if provided
            headers = HEADERS.copy()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                logger.info("[D1] Using OAuth token for account items")
            
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"[D1] Error getting account items: {e}")
            return None

    @staticmethod
    def get_character_inventory(membership_id: str, character_id: str, access_token: str = None) -> Optional[Dict]:
        """Get D1 character inventory (items equipped and in inventory)"""
        url = (
            f"https://www.bungie.net/Platform/Destiny/{MEMBERSHIP_TYPE_PSN}/"
            f"Account/{membership_id}/Character/{character_id}/Inventory/"
        )
        try:
            logger.info(f"[D1] Getting character inventory: {membership_id}/{character_id}")
            
            # Prepare headers with OAuth if provided
            headers = HEADERS.copy()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                logger.info("[D1] Using OAuth token for character inventory")
            
            r = requests.get(url, headers=headers, timeout=10)
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
    def get_vendors(access_token: str) -> Optional[Dict]:
        """Get D1 vendors with OAuth token - requires authentication"""
        url = "https://www.bungie.net/Platform/Destiny/Advisors/Vendors/?definitions=true"
        try:
            logger.info("[D1] Getting vendors with OAuth token")
            headers = HEADERS.copy()
            headers["Authorization"] = f"Bearer {access_token}"
            r = requests.get(url, headers=headers, timeout=10)
            logger.info(f"[D1] Vendors HTTP status: {r.status_code}")
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"[D1] HTTP Error getting vendors: {e} - Status: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"[D1] Error getting vendors: {e}")
            return None

    @staticmethod
    def get_character_stats(membership_type: int, membership_id: str, character_id: str) -> Optional[Dict]:
        """Get detailed character statistics - all PvE and PvP modes"""
        url = (
            f"https://www.bungie.net/Platform/Destiny/Stats/CharacterStats/"
            f"{membership_type}/{membership_id}/{character_id}/?modes=7"
        )
        try:
            logger.info(f"[D1] Getting character stats: {membership_type}/{membership_id}/{character_id}")
            logger.info(f"[D1] URL: {url}")
            r = requests.get(url, headers=HEADERS, timeout=10)
            logger.info(f"[D1] Character stats HTTP status: {r.status_code}")
            r.raise_for_status()
            data = r.json()
            # DEBUG: Log the response structure
            logger.info(f"[D1] Character stats response: {json.dumps(data, indent=2)[:500]}")
            return data
        except requests.exceptions.HTTPError as e:
            logger.error(f"[D1] HTTP Error getting character stats: {e} - Status: {e.response.status_code}")
            logger.error(f"[D1] Response body: {e.response.text[:200]}")
            return None
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

    @staticmethod
    def search_clan(clan_name: str) -> Optional[Dict]:
        """Search for a clan by name using Bungie Group API - with ADVANCED flexible matching"""
        try:
            logger.info(f"[D1] Searching clan with advanced matching: {clan_name}")
            
            # Clean input
            clean_name = clan_name.strip()
            
            # Strategy 1: Try exact search first
            clan = Destiny1Service._search_clan_exact(clean_name)
            if clan:
                return clan
            
            # Strategy 2: Try with first word only (if multiple words)
            words = clean_name.split()
            if len(words) > 1:
                # Try first word
                clan = Destiny1Service._search_clan_exact(words[0])
                if clan:
                    logger.info(f"[D1] Clan found with first word: {words[0]}")
                    return clan
                
                # Try first 2 words
                if len(words) >= 2:
                    first_two = " ".join(words[:2])
                    clan = Destiny1Service._search_clan_exact(first_two)
                    if clan:
                        logger.info(f"[D1] Clan found with first two words: {first_two}")
                        return clan
            
            # Strategy 3: Try partial/fuzzy search
            clan = Destiny1Service._search_clan_flexible(clean_name)
            if clan:
                return clan
            
            # Strategy 4: Try variations
            variations = [
                clean_name.lower(),
                clean_name.upper(),
                clean_name.title(),
                clean_name.replace(" ", ""),
                clean_name.replace("-", " "),
                clean_name.replace("_", " "),
                clean_name.replace("[", "").replace("]", ""),
                clean_name.replace("(", "").replace(")", ""),
                # Remove common suffixes/prefixes
                clean_name.replace("Clan", "").strip(),
                clean_name.replace("Official", "").strip(),
            ]
            
            for variant in variations:
                if variant and variant != clean_name:
                    clan = Destiny1Service._search_clan_exact(variant)
                    if clan:
                        logger.info(f"[D1] Clan found with variation: '{variant}'")
                        return clan
            
            # Strategy 5: Try each word individually
            for word in words:
                if len(word) > 3:  # Skip short words
                    clan = Destiny1Service._search_clan_exact(word)
                    if clan:
                        # Verify it's a reasonable match
                        clan_full = clan.get("name", "").lower()
                        if word.lower() in clan_full:
                            logger.info(f"[D1] Clan found with word '{word}': {clan.get('name')}")
                            return clan
            
            # Strategy 6: Broad search with partial match
            if len(words) > 0:
                clan = Destiny1Service._search_clan_broad(words[0])
                if clan:
                    return clan
            
            logger.warning(f"[D1] No clan found matching: {clean_name} (tried all strategies)")
            return None
            
        except Exception as e:
            logger.error(f"[D1] Error searching clan: {e}")
            return None
    
    @staticmethod
    def _search_clan_broad(search_term: str) -> Optional[Dict]:
        """Broad search - returns any clan containing the search term"""
        try:
            url = "https://www.bungie.net/Platform/Group/Search/"
            params = {
                "name": search_term[:10],  # Limit to first 10 chars for broader results
                "groupType": 1,
                "platform": 0,
            }
            
            r = requests.get(url, headers=HEADERS, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            if data.get("Response") and data["Response"].get("results"):
                results = data["Response"]["results"]
                search_lower = search_term.lower()
                
                # Find best match
                for clan in results:
                    clan_name = clan.get("name", "").lower()
                    # Check if search term is in clan name
                    if search_lower in clan_name or any(word in clan_name for word in search_lower.split()):
                        logger.info(f"[D1] Clan found via broad search: {clan.get('name')}")
                        return clan
                
                # Return first result as fallback
                if results:
                    logger.info(f"[D1] Returning first clan from broad search: {results[0].get('name')}")
                    return results[0]
            return None
        except Exception as e:
            logger.debug(f"[D1] Broad search error: {e}")
            return None
    
    @staticmethod
    def _search_clan_exact(clan_name: str) -> Optional[Dict]:
        """Exact clan search"""
        try:
            url = "https://www.bungie.net/Platform/Group/Search/"
            params = {
                "name": clan_name,
                "groupType": 1,
                "platform": 0,
            }
            
            r = requests.get(url, headers=HEADERS, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            if data.get("Response") and data["Response"].get("results"):
                results = data["Response"]["results"]
                # Look for best match
                for clan in results:
                    clan_name_result = clan.get("name", "").lower()
                    search_lower = clan_name.lower()
                    if search_lower in clan_name_result or clan_name_result in search_lower:
                        logger.info(f"[D1] Clan found: {clan.get('name')} (ID: {clan.get('groupId')})")
                        return clan
                # Return first if no perfect match
                if results:
                    return results[0]
            return None
        except Exception as e:
            logger.debug(f"[D1] Exact search error: {e}")
            return None
    
    @staticmethod
    def _search_clan_flexible(clan_name: str) -> Optional[Dict]:
        """Flexible clan search with broader results"""
        try:
            # Try searching with partial name (first word only)
            words = clan_name.split()
            if len(words) > 1:
                first_word = words[0]
                url = "https://www.bungie.net/Platform/Group/Search/"
                params = {
                    "name": first_word,
                    "groupType": 1,
                    "platform": 0,
                }
                
                r = requests.get(url, headers=HEADERS, params=params, timeout=10)
                r.raise_for_status()
                data = r.json()
                
                if data.get("Response") and data["Response"].get("results"):
                    results = data["Response"]["results"]
                    # Filter results that contain our search term
                    search_lower = clan_name.lower()
                    for clan in results:
                        clan_full_name = clan.get("name", "").lower()
                        if search_lower in clan_full_name:
                            logger.info(f"[D1] Clan found via flexible search: {clan.get('name')}")
                            return clan
            return None
        except Exception as e:
            logger.debug(f"[D1] Flexible search error: {e}")
            return None
    
    @staticmethod
    def get_clan_members(clan_id: str) -> Optional[Dict]:
        """Get all members of a clan"""
        try:
            logger.info(f"[D1] Getting clan members: {clan_id}")
            
            url = f"https://www.bungie.net/Platform/Group/{clan_id}/Members/"
            
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            if data.get("Response") and data["Response"].get("results"):
                members = data["Response"]["results"]
                logger.info(f"[D1] Found {len(members)} clan members")
                return data["Response"]
            else:
                logger.warning(f"[D1] No members found for clan: {clan_id}")
                return None
                
        except Exception as e:
            logger.error(f"[D1] Error getting clan members: {e}")
            return None
    
    @staticmethod
    def get_clan_stats(clan_id: str) -> Optional[Dict]:
        """Get aggregated clan statistics"""
        try:
            logger.info(f"[D1] Getting clan stats: {clan_id}")
            
            # Get clan members first
            members_data = Destiny1Service.get_clan_members(clan_id)
            if not members_data:
                return None
            
            members = members_data.get("results", [])
            total_members = len(members)
            
            # Aggregate stats from each member
            total_raids = 0
            total_playtime = 0
            member_stats = []
            
            for member in members[:20]:  # Limit to top 20 to avoid rate limits
                try:
                    membership_id = member.get("destinyUserInfo", {}).get("membershipId")
                    if not membership_id:
                        continue
                    
                    # Get account summary for this member
                    account = Destiny1Service.get_account(membership_id)
                    if not account or not account.get("Response"):
                        continue
                    
                    characters = account["Response"].get("data", {}).get("characters", [])
                    member_raid_count = 0
                    
                    # Count raids across all characters
                    for char in characters:
                        char_id = char.get("characterBase", {}).get("characterId")
                        if char_id:
                            raid_data = Destiny1Service.get_raid_history(membership_id, char_id)
                            if raid_data and raid_data.get("Response"):
                                activities = raid_data["Response"].get("data", {}).get("activities", [])
                                for activity in activities:
                                    completions = activity.get("values", {}).get("activityCompletions", {}).get("basic", {}).get("value", 0)
                                    member_raid_count += int(completions)
                    
                    total_raids += member_raid_count
                    
                    # Get display name
                    display_name = member.get("destinyUserInfo", {}).get("displayName", "Unknown")
                    
                    member_stats.append({
                        "name": display_name,
                        "raids": member_raid_count,
                        "characters": len(characters)
                    })
                    
                except Exception as e:
                    logger.warning(f"[D1] Error getting stats for member: {e}")
                    continue
            
            # Sort by raid count
            member_stats.sort(key=lambda x: x["raids"], reverse=True)
            
            return {
                "total_members": total_members,
                "total_raids": total_raids,
                "avg_raids": round(total_raids / max(total_members, 1), 1),
                "top_performers": member_stats[:5],  # Top 5
                "active_members": len([m for m in member_stats if m["raids"] > 0])
            }
            
        except Exception as e:
            logger.error(f"[D1] Error getting clan stats: {e}")
            return None

    @staticmethod
    def equip_item(membership_type: int, membership_id: str, character_id: str, item_hash: str, item_instance_id: str = None, access_token: str = None) -> Dict:
        """Equip an item on a character via Bungie API"""
        try:
            logger.info(f"[D1] Equipping item {item_hash} on character {character_id}")
            
            # Bungie EquipItem endpoint
            url = "https://www.bungie.net/Platform/Destiny/EquipItem/"
            
            # Prepare headers - add OAuth token if provided
            headers = HEADERS.copy()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                logger.info("[D1] Using OAuth token for equip")
            else:
                logger.warning("[D1] No OAuth token provided for equip - may fail")
            
            payload = {
                "membershipType": membership_type,
                "characterId": character_id,
                "itemId": item_instance_id or item_hash,
                "itemHash": int(item_hash) if item_hash.isdigit() else 0
            }
            
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            
            # Log response for debugging
            logger.info(f"[D1] Equip response status: {r.status_code}")
            
            if r.status_code == 200:
                data = r.json()
                if data.get("ErrorCode") == 1:
                    logger.info(f"[D1] Item equipped successfully")
                    return {"success": True, "message": "Item equipped"}
                else:
                    error_msg = data.get("Message", "Unknown error")
                    logger.warning(f"[D1] Equip failed: {error_msg}")
                    return {"success": False, "error": error_msg}
            elif r.status_code == 404:
                logger.error(f"[D1] EquipItem endpoint not found - D1 API deprecated")
                return {"success": False, "error": "D1 EquipItem API discontinued"}
            elif r.status_code == 401:
                logger.error(f"[D1] EquipItem unauthorized - invalid or missing OAuth token")
                return {"success": False, "error": "OAuth token invalid or expired - please re-authenticate with /auth"}
            elif r.status_code == 403:
                logger.error(f"[D1] EquipItem forbidden - insufficient permissions")
                return {"success": False, "error": "Insufficient permissions (need OAuth)"}
            else:
                logger.error(f"[D1] EquipItem HTTP {r.status_code}")
                return {"success": False, "error": f"HTTP {r.status_code}"}
                
        except Exception as e:
            logger.error(f"[D1] Error equipping item: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def get_item_instance_id(membership_id: str, character_id: str, item_hash: str) -> Optional[str]:
        """Get item instance ID from character inventory"""
        try:
            # Get character inventory
            items = Destiny1Service.get_character_items(membership_id, character_id)
            if not items or not items.get("Response"):
                return None
            
            # Search for item with matching hash
            buckets = items["Response"].get("data", {}).get("buckets", {})
            for bucket_name, bucket_list in buckets.items():
                if isinstance(bucket_list, list):
                    for bucket in bucket_list:
                        for item in bucket.get("items", []):
                            if str(item.get("itemHash")) == item_hash:
                                return item.get("itemId")
            
            return None
            
        except Exception as e:
            logger.error(f"[D1] Error getting item instance: {e}")
            return None
