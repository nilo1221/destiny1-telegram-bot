from app.services.base import BaseService
from app.infrastructure.http_client import HttpClient
from app.infrastructure.cache import cache
from app.infrastructure.circuit_breaker import CircuitBreakerRegistry
from app.core.config import get_settings
from app.core.exceptions import PlayerNotFoundError, ServiceUnavailableError
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger("bungie_adapter")


class BungieAdapter(BaseService):
    """Adapter for Bungie.net API with caching and circuit breaker"""
    
    def __init__(self):
        super().__init__("bungie")
        self.client = HttpClient(
            base_url=settings.bungie_base_url,
            headers={
                "X-API-Key": settings.bungie_api_key,
                "Content-Type": "application/json"
            }
        )
        self.circuit_breaker = CircuitBreakerRegistry.get("bungie")
    
    async def initialize(self):
        logger.info("Bungie adapter initialized")
    
    async def shutdown(self):
        await self.client.close()
        logger.info("Bungie adapter shutdown")
    
    async def health_check(self) -> dict:
        try:
            response = await self.client.get("/Destiny2/Manifest/")
            return {"status": "healthy", "latency_ms": 0}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def search_player(self, membership_type: int, gamertag: str) -> dict:
        """Search for a Destiny 2 player by gamertag"""
        cache_key = f"bungie:player:{membership_type}:{gamertag.lower()}"
        
        # Check cache first
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        # Call API with circuit breaker
        try:
            result = await self.circuit_breaker.call(
                self._fetch_player,
                membership_type,
                gamertag
            )
            
            # Cache successful result
            await cache.set(cache_key, result, ttl=600)
            return result
            
        except Exception as e:
            logger.error(f"Failed to search player {gamertag}: {e}")
            raise
    
    async def _fetch_player(self, membership_type: int, gamertag: str) -> dict:
        """Internal method to fetch player from API"""
        url = f"/Destiny2/SearchDestinyPlayer/{membership_type}/{gamertag}/"
        
        response = await self.client.get(url)
        data = response.json()
        
        if not data.get("Response"):
            raise PlayerNotFoundError(f"Player '{gamertag}' not found")
        
        return data
    
    async def get_profile(self, membership_type: int, membership_id: str, components: list = None) -> dict:
        """Get player profile with optional components"""
        if components is None:
            components = [100, 200]  # Basic profile and characters
        
        components_str = ",".join(map(str, components))
        cache_key = f"bungie:profile:{membership_type}:{membership_id}:{components_str}"
        
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        try:
            result = await self.circuit_breaker.call(
                self._fetch_profile,
                membership_type,
                membership_id,
                components_str
            )
            
            await cache.set(cache_key, result, ttl=300)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get profile {membership_id}: {e}")
            raise
    
    async def _fetch_profile(self, membership_type: int, membership_id: str, components: str) -> dict:
        url = f"/Destiny2/{membership_type}/Profile/{membership_id}/?components={components}"
        response = await self.client.get(url)
        return response.json()
    
    async def get_character_activities(self, membership_type: int, membership_id: str, character_id: str) -> dict:
        """Get recent activities for a character"""
        cache_key = f"bungie:activities:{membership_type}:{membership_id}:{character_id}"
        
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        try:
            result = await self.circuit_breaker.call(
                self._fetch_activities,
                membership_type,
                membership_id,
                character_id
            )
            
            await cache.set(cache_key, result, ttl=180)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get activities for {character_id}: {e}")
            raise
    
    async def _fetch_activities(self, membership_type: int, membership_id: str, character_id: str) -> dict:
        url = f"/Destiny2/{membership_type}/Account/{membership_id}/Character/{character_id}/Stats/Activities/?count=10&mode=0"
        response = await self.client.get(url)
        return response.json()

    # ============================================================================
    # ACCOUNT / PROFILE ENDPOINTS (D1 & D2)
    # ============================================================================

    async def get_account_summary(self, membership_type: int, membership_id: str, game_version: str = "d2") -> dict:
        """Get account summary with characters info (D1 or D2)"""
        cache_key = f"bungie:summary:{game_version}:{membership_type}:{membership_id}"
        
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        try:
            if game_version == "d1":
                result = await self.circuit_breaker.call(
                    self._fetch_d1_account_summary,
                    membership_type,
                    membership_id
                )
            else:
                # D2 uses Profile endpoint with components
                result = await self.get_profile(
                    membership_type,
                    membership_id,
                    components=[100, 200, 202]  # Profile, Characters, CharacterProgressions
                )
            
            await cache.set(cache_key, result, ttl=300)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get account summary {membership_id}: {e}")
            raise

    async def _fetch_d1_account_summary(self, membership_type: int, membership_id: str) -> dict:
        """D1 Account Summary endpoint"""
        url = f"/D1/Platform/Destiny/{membership_type}/Account/{membership_id}/Summary/"
        response = await self.client.get(url)
        return response.json()

    # ============================================================================
    # CHARACTER ENDPOINTS
    # ============================================================================

    async def get_character_advisors(self, membership_type: int, membership_id: str, character_id: str, game_version: str = "d2") -> dict:
        """Get character advisors/activities (Xur, weekly reset info, etc.)"""
        cache_key = f"bungie:advisors:{game_version}:{membership_type}:{membership_id}:{character_id}"
        
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        try:
            if game_version == "d1":
                result = await self.circuit_breaker.call(
                    self._fetch_d1_character_advisors,
                    membership_type,
                    membership_id,
                    character_id
                )
            else:
                # D2 uses different endpoints for advisors
                result = await self.circuit_breaker.call(
                    self._fetch_d2_character_advisors,
                    membership_type,
                    membership_id,
                    character_id
                )
            
            await cache.set(cache_key, result, ttl=180)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get character advisors {character_id}: {e}")
            raise

    async def _fetch_d1_character_advisors(self, membership_type: int, membership_id: str, character_id: str) -> dict:
        url = f"/D1/Platform/Destiny/{membership_type}/Account/{membership_id}/Character/{character_id}/Advisors/V2/"
        response = await self.client.get(url)
        return response.json()

    async def _fetch_d2_character_advisors(self, membership_type: int, membership_id: str, character_id: str) -> dict:
        # D2 uses Profile endpoint with CharacterActivities component
        url = f"/Destiny2/{membership_type}/Profile/{membership_id}/Character/{character_id}/?components=204"
        response = await self.client.get(url)
        return response.json()

    # ============================================================================
    # ACTIVITY HISTORY WITH MODE FILTER
    # ============================================================================

    async def get_activity_history(
        self,
        membership_type: int,
        membership_id: str,
        character_id: str,
        mode: int = 0,
        count: int = 25,
        page: int = 0
    ) -> dict:
        """
        Get activity history filtered by mode
        
        Common modes:
        - 0 = All activities
        - 2 = Story
        - 3 = Strike
        - 4 = Raid
        - 5 = Crucible (D1) / AllPvP (D2)
        - 6 = Patrol
        - 16 = Nightfall
        - 17 = PvP (All)
        - 18 = PvE (Strikes)
        - 19 = Trials of Osiris
        - 63 = Onslaught
        - 64 = Spire of the Watcher
        - 65 = Root of Nightmares
        - 66 = Ghost of the Deep
        - 67 = Crota's End
        - 68 = Warlord's Ruin
        - 69 = Vesper's Host
        - 70 = Onslaught
        - 71 = Salvation's Edge
        - 84 = Prophecy
        - 85 = Grasp of Avarice
        - 86 = Duality
        - 87 = Spire of the Watcher
        - 88 = Ghost of the Deep
        - 89 = Salvation's Edge
        - 90 = Crota's End
        - 91 = Warlord's Ruin
        - 92 = Vesper's Host
        - 93 = Onslaught
        - 94 = Exotic Mission
        - 95 = Strike Playlist
        - 96 = Nightfall
        - 97 = Grandmaster Nightfall
        - 98 = Lost Sector
        - 99 = Master Lost Sector
        - 100 = Legendary Lost Sector
        """
        cache_key = f"bungie:history:{membership_type}:{membership_id}:{character_id}:mode{mode}:page{page}"
        
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        try:
            result = await self.circuit_breaker.call(
                self._fetch_activity_history,
                membership_type,
                membership_id,
                character_id,
                mode,
                count,
                page
            )
            
            await cache.set(cache_key, result, ttl=180)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get activity history for {character_id}: {e}")
            raise

    async def _fetch_activity_history(
        self,
        membership_type: int,
        membership_id: str,
        character_id: str,
        mode: int,
        count: int,
        page: int
    ) -> dict:
        url = f"/Destiny2/{membership_type}/Account/{membership_id}/Character/{character_id}/Stats/Activities/?mode={mode}&count={count}&page={page}"
        response = await self.client.get(url)
        return response.json()

    # ============================================================================
    # INVENTORY & ITEMS
    # ============================================================================

    async def get_account_items(self, membership_type: int, membership_id: str, game_version: str = "d2") -> dict:
        """Get all items for an account"""
        cache_key = f"bungie:items:{game_version}:{membership_type}:{membership_id}"
        
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        try:
            if game_version == "d1":
                result = await self.circuit_breaker.call(
                    self._fetch_d1_account_items,
                    membership_type,
                    membership_id
                )
            else:
                # D2 uses Profile endpoint with Inventory component
                result = await self.get_profile(
                    membership_type,
                    membership_id,
                    components=[102, 201, 205, 300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310]  # Inventory, ItemInstances, etc.
                )
            
            await cache.set(cache_key, result, ttl=300)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get account items {membership_id}: {e}")
            raise

    async def _fetch_d1_account_items(self, membership_type: int, membership_id: str) -> dict:
        url = f"/D1/Platform/Destiny/{membership_type}/Account/{membership_id}/Items/"
        response = await self.client.get(url)
        return response.json()

    async def get_manifest_item(self, hash_id: int) -> dict:
        """Get item definition from manifest"""
        cache_key = f"bungie:manifest:item:{hash_id}"
        
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        try:
            result = await self.circuit_breaker.call(
                self._fetch_manifest_item,
                hash_id
            )
            
            await cache.set(cache_key, result, ttl=86400)  # 24h cache for manifest
            return result
            
        except Exception as e:
            logger.error(f"Failed to get manifest item {hash_id}: {e}")
            raise

    async def _fetch_manifest_item(self, hash_id: int) -> dict:
        url = f"/Destiny2/Manifest/InventoryItem/{hash_id}/"
        response = await self.client.get(url)
        return response.json()

    # ============================================================================
    # ADVISORS (Xur, Weekly Reset, Vendors)
    # ============================================================================

    async def get_account_advisors(self, membership_type: int, membership_id: str) -> dict:
        """Get account-level advisors (Xur, weekly milestones, etc.) - D1 only"""
        cache_key = f"bungie:advisors:account:{membership_type}:{membership_id}"
        
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        try:
            result = await self.circuit_breaker.call(
                self._fetch_account_advisors,
                membership_type,
                membership_id
            )
            
            await cache.set(cache_key, result, ttl=300)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get account advisors {membership_id}: {e}")
            raise

    async def _fetch_account_advisors(self, membership_type: int, membership_id: str) -> dict:
        url = f"/D1/Platform/Destiny/{membership_type}/Account/{membership_id}/Advisors/"
        response = await self.client.get(url)
        return response.json()

    async def get_xur_items(self) -> dict:
        """Get Xur's current inventory - D2 uses different endpoint"""
        # For D2, Xur data comes from the Vendor API
        cache_key = "bungie:xur:current"
        
        cached = await cache.get(cache_key)
        if cached:
            return cached
        
        try:
            result = await self.circuit_breaker.call(
                self._fetch_xur_vendor
            )
            
            await cache.set(cache_key, result, ttl=3600)  # 1h cache
            return result
            
        except Exception as e:
            logger.error(f"Failed to get Xur items: {e}")
            raise

    async def _fetch_xur_vendor(self) -> dict:
        # Xur vendor hash in D2: 2190858386
        # This requires OAuth for D2 vendor access
        url = "/Destiny2/Vendors/?components=400,401,402"  # VendorCategories, VendorSales, VendorItems
        response = await self.client.get(url)
        return response.json()

    # ============================================================================
    # EQUIPMENT ACTIONS (Require OAuth)
    # ============================================================================

    async def equip_item(
        self,
        membership_type: int,
        membership_id: str,
        character_id: str,
        item_instance_id: str,
        access_token: str
    ) -> dict:
        """Equip an item on a character (requires OAuth)"""
        try:
            return await self.circuit_breaker.call(
                self._equip_item_request,
                membership_type,
                character_id,
                item_instance_id,
                access_token
            )
        except Exception as e:
            logger.error(f"Failed to equip item {item_instance_id}: {e}")
            raise

    async def _equip_item_request(
        self,
        membership_type: int,
        character_id: str,
        item_instance_id: str,
        access_token: str
    ) -> dict:
        url = "/Destiny2/Actions/Items/EquipItem/"
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        payload = {
            "itemId": item_instance_id,
            "characterId": character_id,
            "membershipType": membership_type
        }
        
        response = await self.client.post(url, json=payload, headers=headers)
        return response.json()

    async def equip_items(
        self,
        membership_type: int,
        character_id: str,
        item_instance_ids: list[str],
        access_token: str
    ) -> dict:
        """Equip multiple items (requires OAuth)"""
        try:
            return await self.circuit_breaker.call(
                self._equip_items_request,
                membership_type,
                character_id,
                item_instance_ids,
                access_token
            )
        except Exception as e:
            logger.error(f"Failed to equip items: {e}")
            raise

    async def _equip_items_request(
        self,
        membership_type: int,
        character_id: str,
        item_instance_ids: list[str],
        access_token: str
    ) -> dict:
        url = "/Destiny2/Actions/Items/EquipItems/"
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        payload = {
            "itemIds": item_instance_ids,
            "characterId": character_id,
            "membershipType": membership_type
        }
        
        response = await self.client.post(url, json=payload, headers=headers)
        return response.json()
