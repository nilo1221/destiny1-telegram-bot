from app.services.adapters import BungieAdapter, TelegramAdapter
from app.services.oauth_handler import get_oauth_handler
from app.services.handlers.d1_handlers import D1CommandHandlers
from app.services.handlers.d2_handlers import D2CommandHandlers
from app.services.formatting import Destiny1Formatter
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.registry import ServiceRegistry
from app.infrastructure.cache import cache
from app.core.exceptions import PlayerNotFoundError, CommandError
from app.core.constants import D1_RAID_NAMES
import redis
import json
import re
import jwt
import os
from cryptography.fernet import Fernet

settings = get_settings()
logger = get_logger("orchestrator")


class ServiceOrchestrator:
    """
    Orchestrates calls between multiple external services.
    Coordinates data flow: Bungie API -> Transform -> Telegram
    """
    
    def __init__(self):
        self.bungie = None
        self.telegram = TelegramAdapter()
        self.oauth_handler = None
        
        # Initialize modular command handlers
        self.d1_handlers = D1CommandHandlers(self.telegram)
        self.d2_handlers = None  # Initialized when Bungie adapter is ready
        
        # Initialize Redis client for secure token storage
        try:
            self.redis_client = redis.Redis(
                host=settings.redis_url.split('://')[1].split(':')[0],
                port=int(settings.redis_url.split(':')[-1].split('/')[0]),
                decode_responses=True
            )
            logger.info("Redis client initialized successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed, using memory storage: {e}")
            self.redis_client = None
        
        # Initialize encryption for token security
        encryption_key = os.getenv('TOKEN_ENCRYPTION_KEY')
        if not encryption_key:
            raise RuntimeError("TOKEN_ENCRYPTION_KEY environment variable is required for secure token storage. Please set it in your .env file.")
        self.cipher_suite = Fernet(encryption_key.encode())
        
        # Initialize OAuth tokens storage (legacy, will be removed)
        self._oauth_tokens = {}
    
    def _validate_token_format(self, token: str) -> bool:
        """Validate OAuth token format"""
        try:
            # Basic format check
            if not token or len(token) < 50:
                return False
            
            # JWT structure validation if applicable
            if '.' in token:  # JWT token
                decoded = jwt.decode(token, options={"verify_signature": False})
                return bool(decoded.get('exp'))
            
            return True
        except:
            return False
    
    def _secure_store_token(self, chat_id: int, token_data: dict) -> bool:
        """Securely store OAuth token in Redis with encryption"""
        try:
            if self.redis_client:
                # Encrypt token data
                token_json = json.dumps(token_data)
                encrypted_token = self.cipher_suite.encrypt(token_json.encode())
                
                # Store in Redis with TTL
                self.redis_client.setex(
                    f"oauth_token:{chat_id}",
                    token_data.get("expires_in", 3600),
                    encrypted_token
                )
                logger.info(f"Token securely stored in Redis for chat {chat_id}")
                return True
            else:
                # Fallback to memory storage if Redis unavailable
                self._oauth_tokens[str(chat_id)] = token_data
                logger.warning(f"Using memory storage for OAuth token (chat {chat_id})")
                return True
        except Exception as e:
            logger.error(f"Failed to store OAuth token: {e}")
            return False
    
    def _secure_get_token(self, chat_id: int) -> dict:
        """Securely retrieve OAuth token from Redis with decryption"""
        try:
            if self.redis_client:
                # Get from Redis
                encrypted_token = self.redis_client.get(f"oauth_token:{chat_id}")
                if encrypted_token:
                    decrypted_json = self.cipher_suite.decrypt(encrypted_token).decode()
                    token_data = json.loads(decrypted_json)
                    logger.info(f"Token retrieved from Redis for chat {chat_id}")
                    return token_data
            
            # Fallback to memory storage
            if hasattr(self, '_oauth_tokens') and str(chat_id) in self._oauth_tokens:
                return self._oauth_tokens[str(chat_id)]
            
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve OAuth token: {e}")
            return None
    
    async def initialize(self):
        """Initialize and register all services"""
        # Create adapters
        self.bungie = BungieAdapter()
        self.telegram = TelegramAdapter()
        
        # Register in service registry
        ServiceRegistry.register(self.bungie)
        ServiceRegistry.register(self.telegram)
        
        # Initialize all services
        await ServiceRegistry.initialize_all()
        
        logger.info("Service orchestrator initialized")
    
    async def shutdown(self):
        """Shutdown all services"""
        await ServiceRegistry.shutdown_all()
        await cache.close()
        logger.info("Service orchestrator shutdown")
    
    async def handle_find_player(self, chat_id: int, gamertag: str) -> dict:
        """
        Orchestrate: Search player on Bungie -> Format result -> Send to Telegram
        """
        try:
            # Step 1: Search player on Bungie (membership_type=3 = Steam)
            logger.info(f"Searching player: {gamertag}")
            data = await self.bungie.search_player(membership_type=3, gamertag=gamertag)
            
            if not data.get("Response"):
                message = f"🔍 Giocatore '<b>{gamertag}</b>' non trovato."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "message": message}
            
            # Step 2: Extract player info
            player = data["Response"][0]
            membership_id = player["membershipId"]
            display_name = player["displayName"]
            
            # Step 3: Format and send message
            message = (
                f"🎮 <b>Giocatore trovato!</b>\n\n"
                f"👤 Nome: <code>{display_name}</code>\n"
                f"🆔 ID: <code>{membership_id}</code>\n"
                f"🔗 Piattaforma: Steam"
            )
            
            await self.telegram.send_message(chat_id, message)
            
            logger.info(f"Player {gamertag} found and notified to chat {chat_id}")
            return {
                "success": True,
                "player": {
                    "display_name": display_name,
                    "membership_id": membership_id,
                    "membership_type": 3
                }
            }
            
        except PlayerNotFoundError:
            message = f"❌ Giocatore '<b>{gamertag}</b>' non trovato."
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": "Player not found"}
            
        except Exception as e:
            logger.error(f"Error in handle_find_player: {e}")
            message = f"❌ Errore durante la ricerca: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}
    
    async def handle_get_activities(self, chat_id: int, gamertag: str) -> dict:
        """
        Orchestrate: Search player -> Get profile -> Get activities -> Send to Telegram
        """
        try:
            # Step 1: Search player
            logger.info(f"Getting activities for: {gamertag}")
            search_data = await self.bungie.search_player(membership_type=3, gamertag=gamertag)
            
            if not search_data.get("Response"):
                message = f"🔍 Giocatore '<b>{gamertag}</b>' non trovato."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Player not found"}
            
            player = search_data["Response"][0]
            membership_id = player["membershipId"]
            display_name = player["displayName"]
            
            # Step 2: Get profile to fetch characters
            profile_data = await self.bungie.get_profile(
                membership_type=3,
                membership_id=membership_id,
                components=[200]  # Characters component
            )
            
            characters_data = profile_data.get("Response", {}).get("characters", {}).get("data", {})
            
            if not characters_data:
                message = f"📭 Nessun personaggio trovato per <b>{display_name}</b>."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "No characters found"}
            
            # Step 3: Get activities for first character
            first_character_id = list(characters_data.keys())[0]
            character = characters_data[first_character_id]
            class_type = self._get_class_name(character.get("classType", 0))
            
            activities_data = await self.bungie.get_character_activities(
                membership_type=3,
                membership_id=membership_id,
                character_id=first_character_id
            )
            
            activities = activities_data.get("Response", {}).get("activities", [])
            
            # Step 4: Format activities
            if activities:
                activity_list = []
                for i, activity in enumerate(activities[:5], 1):
                    ref_id = activity.get("activityDetails", {}).get("referenceId", "Unknown")
                    mode = activity.get("activityDetails", {}).get("mode", 0)
                    mode_name = self._get_activity_mode_name(mode)
                    activity_list.append(f"{i}. {mode_name} (Ref: {ref_id})")
                
                activities_text = "\n".join(activity_list)
            else:
                activities_text = "Nessuna attività recente"
            
            # Step 5: Send formatted message
            message = (
                f"🎮 <b>Attività di {display_name}</b>\n"
                f"🛡️ Personaggio: {class_type}\n\n"
                f"📊 Ultime attività:\n{activities_text}"
            )
            
            await self.telegram.send_message(chat_id, message)
            
            logger.info(f"Activities for {gamertag} sent to chat {chat_id}")
            return {
                "success": True,
                "player": display_name,
                "activities_count": len(activities)
            }
            
        except Exception as e:
            logger.error(f"Error in handle_get_activities: {e}")
            message = f"❌ Errore recupero attività: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def _get_class_name(class_type: int) -> str:
        classes = {0: "Titano", 1: "Cacciatore", 2: "Stregone"}
        return classes.get(class_type, "Sconosciuto")
    
    @staticmethod
    def _get_activity_mode_name(mode: int) -> str:
        modes = {
            2: "Storia",
            3: "Assalto",
            4: "PVP",
            5: "Incursione",
            6: "Dungeon",
            7: "Gambit",
            16: "Assalto Notturno",
            17: "Crogiolo",
            18: "Prova",
            19: "Prove di Osiride",
            20: "Casa delle Vittorie",
            21: "Passaggio",
            22: "Stagione",
            37: "Survival",
            38: "Countdown",
            39: "Clash",
            40: "Control",
            41: "Lockdown",
            42: "Breakthrough",
            43: "Team Scorched",
            44: "Doubles",
            45: "Private Matches",
            46: "Gambit Prime",
            47: "The Reckoning",
            48: "Menagerie",
            49: "Vex Offensive",
            50: "Nightmare Hunt",
            51: "Elimination",
            52: "Momentum",
            53: "Rift",
            54: "Zone Control",
            55: "Rift",
            56: "Iron Banner",
            57: "Crogiolo: Foschia",
            58: "Trials",
            59: "Dares of Eternity",
            60: "Seasonal Event",
            61: "PsiOps",
            62: "Wellspring",
            63: "Terminal Overload",
            64: "Spire of the Watcher",
            65: "Root of Nightmares",
            66: "Ghost of the Deep",
            67: "Crota's End",
            68: "Warlord's Ruin",
            69: "Vesper's Host",
            70: "Onslaught",
            71: "Salvation's Edge",
            72: "Vow of the Disciple",
            73: "King's Fall",
            74: "Vault of Glass",
            75: "Deep Stone Crypt",
            76: "Garden of Salvation",
            77: "Last Wish",
            78: "Leviathan",
            79: "Eater of Worlds",
            80: "Spire of Stars",
            81: "Crown of Sorrow",
            82: "Scourge of the Past",
            83: "The Menagerie",
            84: "Prophecy",
            85: "Grasp of Avarice",
            86: "Duality",
            87: "Spire of the Watcher",
            88: "Ghost of the Deep",
            89: "Salvation's Edge",
            90: "Crota's End",
            91: "Warlord's Ruin",
            92: "Vesper's Host",
            93: "Onslaught",
            94: "Exotic Mission",
            95: "Strike",
            96: "Nightfall",
            97: "Grandmaster Nightfall",
            98: "Lost Sector",
            99: "Master Lost Sector",
            100: "Legendary Lost Sector",
            101: "Patrol",
            102: "Public Event",
            103: "Heroic Public Event",
            104: "Adventure",
            105: "Quest",
            106: "Bounty",
            107: "Challenge",
            108: "Seasonal Activity",
            109: "Event",
            110: "Social",
            111: "Exploration",
            112: "Vendor",
            113: "Collection",
            114: "Triumph",
            115: "Record",
            116: "Seal",
            117: "Title",
            118: "Emblem",
            119: "Shader",
            120: "Ornament",
            121: "Ship",
            122: "Sparrow",
            123: "Ghost Shell",
            124: "Emote",
            125: "Finisher",
            126: "Transmat Effect",
            127: "Artifact",
            128: "Season Pass",
            129: "Bright Engram",
            130: "Eververse",
            131: "Silver",
            132: "Dust",
            133: "Glimmer",
            134: "Legendary Shards",
            135: "Upgrade Module",
            136: "Enhancement Prism",
            137: "Ascendant Shard",
            138: "Spoils of Conquest",
            139: "Raid Banner",
            140: "Token",
            141: "Currency",
            142: "Material",
            143: "Consumable",
            144: "Mod",
            145: "Perk",
            146: "Trait",
            147: "Barrel",
            148: "Magazine",
            149: "Grip",
            150: "Stock",
            151: "Scope",
            152: "Arrow",
            153: "String",
            154: "Blade",
            155: "Guard",
            156: "Hilt",
            157: "Impact",
            158: "Range",
            159: "Stability",
            160: "Handling",
            161: "Reload Speed",
            162: "Aim Assistance",
            163: "Zoom",
            164: "Recoil",
            165: "Magazine Size",
            166: "Rate of Fire",
            167: "Charge Time",
            168: "Draw Time",
            169: "Accuracy",
            170: "Blast Radius",
            171: "Velocity",
            172: "Stability",
            173: "Range",
            174: "Impact",
            175: "Swing Speed",
            176: "Efficiency",
            177: "Defense",
            178: "Ammo Capacity",
            179: "Charge Rate",
            180: "Guard Resistance",
            181: "Guard Efficiency",
            182: "Guard Endurance",
            183: "Sword Energy",
            184: "Damage",
            185: "RPM",
            186: "Shield Duration",
            187: "Attack",
            188: "Defense",
            189: "Power",
            190: "Mobility",
            191: "Resilience",
            192: "Recovery",
            193: "Discipline",
            194: "Intellect",
            195: "Strength",
            196: "Super",
            197: "Grenade",
            198: "Melee",
            199: "Class Ability",
            200: "Rift",
            201: "Barricade",
            202: "Dodge",
            203: "Grenade Launcher",
            204: "Rocket Launcher",
            205: "Fusion Rifle",
            206: "Sniper Rifle",
            207: "Shotgun",
            208: "Machine Gun",
            209: "Linear Fusion Rifle",
            210: "Sword",
            211: "Bow",
            212: "Trace Rifle",
            213: "Glaive",
            214: "Scout Rifle",
            215: "Pulse Rifle",
            216: "Auto Rifle",
            217: "Hand Cannon",
            218: "Submachine Gun",
            219: "Sidearm",
            220: "Combat Bow",
            221: "Light Machine Gun",
            222: "Heavy Grenade Launcher",
            223: "Special Grenade Launcher",
            224: "Kinetic",
            225: "Energy",
            226: "Power",
            227: "Primary",
            228: "Special",
            229: "Heavy",
            230: "Arc",
            231: "Solar",
            232: "Void",
            233: "Stasis",
            234: "Strand",
            235: "Light",
            236: "Darkness",
            237: "Subclass",
            238: "Aspect",
            239: "Fragment",
            240: "Grenade",
            241: "Melee",
            242: "Class Ability",
            243: "Super",
            244: "Jump",
            245: "Movement",
            246: "Armor",
            247: "Weapon",
            248: "Exotic",
            249: "Legendary",
            250: "Rare",
            251: "Common",
            252: "Uncommon",
            253: "Basic",
            254: "Masterwork",
            255: "Enhanced",
            256: "Shaped",
            257: "Crafted",
            258: "Deepsight",
            259: "Resonance",
            260: "Pattern",
            261: "Red Border",
            262: "Adept",
            263: "Timelost",
            264: "Harrowed",
            265: "Hero",
            266: "Legend",
            267: "Master",
            268: "Grandmaster",
            269: "Normal",
            270: "Prestige",
            271: "Guided Games",
            272: "Solo",
            273: "Flawless",
            274: "Champion",
            275: "Contest",
            276: "Day One",
            277: "World First",
            278: "Clan",
            279: "Fireteam",
            280: "Matchmaking",
            281: "Private",
            282: "Custom",
            283: "Ranked",
            284: "Unranked",
            285: "Quickplay",
            286: "Competitive",
            287: "Trials",
            288: "Iron Banner",
            289: "Faction Rally",
            290: "Guardian Games",
            291: "Solstice",
            292: "Festival of the Lost",
            293: "The Dawning",
            294: "Crimson Days",
            295: "Revelry",
            296: "Moments of Triumph",
            297: "Year 1",
            298: "Year 2",
            299: "Year 3",
            300: "Year 4",
            301: "Year 5",
            302: "Year 6",
            303: "Year 7",
            304: "Year 8",
            305: "Year 9",
            306: "Year 10",
            307: "Year 11",
            308: "Year 12",
            309: "Year 13",
            310: "Year 14",
            311: "Year 15",
            312: "Year 16",
            313: "Year 17",
            314: "Year 18",
            315: "Year 19",
            316: "Year 20",
            317: "Season 1",
            318: "Season 2",
            319: "Season 3",
            320: "Season 4",
            321: "Season 5",
            322: "Season 6",
            323: "Season 7",
            324: "Season 8",
            325: "Season 9",
            326: "Season 10",
            327: "Season 11",
            328: "Season 12",
            329: "Season 13",
            330: "Season 14",
            331: "Season 15",
            332: "Season 16",
            333: "Season 17",
            334: "Season 18",
            335: "Season 19",
            336: "Season 20",
            337: "Season 21",
            338: "Season 22",
            339: "Season 23",
            340: "Season 24",
            341: "Season 25",
            342: "Season 26",
            343: "Season 27",
            344: "Season 28",
            345: "Season 29",
            346: "Season 30",
            347: "Episode 1",
            348: "Episode 2",
            349: "Episode 3",
            350: "Episode 4",
            351: "Episode 5",
            352: "Episode 6",
            353: "Episode 7",
            354: "Episode 8",
            355: "Episode 9",
            356: "Episode 10",
            357: "Episode 11",
            358: "Episode 12",
            359: "Episode 13",
            360: "Episode 14",
            361: "Episode 15",
            362: "Episode 16",
            363: "Episode 17",
            364: "Episode 18",
            365: "Episode 19",
            366: "Episode 20",
            367: "Episode 21",
            368: "Episode 22",
            369: "Episode 23",
            370: "Episode 24",
            371: "Episode 25",
            372: "Episode 26",
            373: "Episode 27",
            374: "Episode 28",
            375: "Episode 29",
            376: "Episode 30",
            377: "Raid",
            378: "Dungeon",
            379: "Strike",
            380: "Story",
            381: "Adventure",
            382: "Patrol",
            383: "PVP",
            384: "Gambit",
            385: "Public Event",
            386: "Lost Sector",
            387: "Nightfall",
            388: "Grandmaster",
            389: "Trials",
            390: "Iron Banner",
            391: "Seasonal",
            392: "Event",
            393: "Exotic",
            394: "Quest",
            395: "Bounty",
            396: "Challenge",
            397: "Triumph",
            398: "Seal",
            399: "Title"
        }
        return modes.get(mode, f"Modalità {mode}")

    # ============================================================================
    # NEW BOT COMMANDS
    # ============================================================================

    async def handle_raid_history(self, chat_id: int, gamertag: str) -> dict:
        """
        Get raid completion history for a player
        Mode 4 = Raid
        """
        try:
            logger.info(f"Getting raid history for: {gamertag}")
            
            # Step 1: Search player
            search_data = await self.bungie.search_player(membership_type=3, gamertag=gamertag)
            if not search_data.get("Response"):
                message = f"🔍 Giocatore '<b>{gamertag}</b>' non trovato."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Player not found"}
            
            player = search_data["Response"][0]
            membership_id = player["membershipId"]
            display_name = player["displayName"]
            
            # Step 2: Get profile to find characters
            profile_data = await self.bungie.get_profile(
                membership_type=3,
                membership_id=membership_id,
                components=[200]
            )
            
            characters_data = profile_data.get("Response", {}).get("characters", {}).get("data", {})
            if not characters_data:
                message = f"📭 Nessun personaggio trovato per <b>{display_name}</b>."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "No characters found"}
            
            # Step 3: Get raid history for first character (mode 4 = Raid)
            first_character_id = list(characters_data.keys())[0]
            character = characters_data[first_character_id]
            class_type = self._get_class_name(character.get("classType", 0))
            
            raid_history = await self.bungie.get_activity_history(
                membership_type=3,
                membership_id=membership_id,
                character_id=first_character_id,
                mode=4,  # Raid mode
                count=10
            )
            
            activities = raid_history.get("Response", {}).get("activities", [])
            
            # Step 4: Format raid history
            if activities:
                raid_list = []
                for i, activity in enumerate(activities[:5], 1):
                    ref_id = activity.get("activityDetails", {}).get("referenceId", "Unknown")
                    instance_id = activity.get("activityDetails", {}).get("instanceId", "N/A")
                    period = activity.get("period", "Unknown")[:10]  # YYYY-MM-DD
                    
                    # Get completion status
                    values = activity.get("values", {})
                    completed = values.get("completed", {}).get("basic", {}).get("displayValue", "?")
                    
                    raid_list.append(f"{i}. 🏰 Raid del {period} (ID: {instance_id[-6:]}) - {completed}")
                
                raids_text = "\n".join(raid_list)
            else:
                raids_text = "Nessun raid completato recentemente"
            
            # Step 5: Send message
            message = (
                f"🏰 <b>Storico Raid di {display_name}</b>\n"
                f"🛡️ Personaggio: {class_type}\n\n"
                f"📊 Ultimi raid:\n{raids_text}"
            )
            
            await self.telegram.send_message(chat_id, message)
            
            logger.info(f"Raid history for {gamertag} sent to chat {chat_id}")
            return {"success": True, "raids_count": len(activities)}
            
        except Exception as e:
            logger.error(f"Error in handle_raid_history: {e}")
            message = f"❌ Errore recupero storico raid: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}

    async def handle_xur_inventory(self, chat_id: int) -> dict:
        """
        Get Xur's current inventory
        """
        try:
            logger.info(f"Getting Xur inventory for chat {chat_id}")
            
            # Get Xur items (this may require OAuth for full functionality)
            xur_data = await self.bungie.get_xur_items()
            
            # Parse Xur data
            response = xur_data.get("Response", {})
            vendors = response.get("vendors", {}).get("data", {})
            sales = response.get("vendorSales", {}).get("data", {})
            categories = response.get("categories", {}).get("data", {})
            
            # Xur vendor hash
            xur_hash = "2190858386"
            
            if xur_hash not in vendors:
                message = (
                    "🌌 <b>Xur non è disponibile</b>\n\n"
                    "Xur arriva ogni venerdì alle 18:00 CET\n"
                    "e resta fino a martedì alle 18:00 CET\n\n"
                    "📍 Si trova in una di queste location:\n"
                    "• Torre - Hangar\n"
                    "• Nessus - Landing Zone\n"
                    "• EDZ - Winding Cove"
                )
                await self.telegram.send_message(chat_id, message)
                return {"success": True, "xur_available": False}
            
            # Format Xur inventory (simplified)
            message = (
                "🌌 <b>Inventario Xur</b>\n"
                "📍 Location: [Vedi mappa gioco]\n\n"
                "🎁 Oggetti in vendita:\n"
                "• Esotiche (richiede OAuth per dettagli completi)\n\n"
                "<i>Per vedere gli oggetti esatti, usa il comando in gioco o attendi l'implementazione OAuth completa.</i>"
            )
            
            await self.telegram.send_message(chat_id, message)
            
            logger.info(f"Xur inventory sent to chat {chat_id}")
            return {"success": True, "xur_available": True}
            
        except Exception as e:
            logger.error(f"Error in handle_xur_inventory: {e}")
            message = (
                "🌌 <b>Xur</b>\n\n"
                "Xur arriva ogni venerdì alle 18:00 CET\n"
                "e resta fino a martedì alle 18:00 CET\n\n"
                "📍 Location possibili:\n"
                "• Torre - Hangar ( dietro Dead Orbit )\n"
                "• Nessus - Landing Zone ( sull'albero )\n"
                "• EDZ - Winding Cove ( nella grotta )"
            )
            await self.telegram.send_message(chat_id, message)
            return {"success": True, "xur_available": False, "error": str(e)}

    async def handle_inventory(self, chat_id: int, gamertag: str) -> dict:
        """
        Get player's inventory summary
        """
        try:
            logger.info(f"Getting inventory for: {gamertag}")
            
            # Step 1: Search player
            search_data = await self.bungie.search_player(membership_type=3, gamertag=gamertag)
            if not search_data.get("Response"):
                message = f"🔍 Giocatore '<b>{gamertag}</b>' non trovato."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Player not found"}
            
            player = search_data["Response"][0]
            membership_id = player["membershipId"]
            display_name = player["displayName"]
            
            # Step 2: Get account items
            items_data = await self.bungie.get_account_items(
                membership_type=3,
                membership_id=membership_id
            )
            
            # Parse inventory data
            response = items_data.get("Response", {})
            
            # Extract vault and character inventories
            profile_inventory = response.get("profileInventory", {}).get("data", {}).get("items", [])
            character_inventories = response.get("characterInventories", {}).get("data", {})
            character_equipments = response.get("characterEquipment", {}).get("data", {})
            
            # Count items by bucket
            vault_count = len(profile_inventory)
            character_counts = {}
            equipped_counts = {}
            
            for char_id, char_data in character_inventories.items():
                character_counts[char_id] = len(char_data.get("items", []))
            
            for char_id, char_data in character_equipments.items():
                equipped_counts[char_id] = len(char_data.get("items", []))
            
            total_items = vault_count + sum(character_counts.values())
            
            # Step 3: Format inventory summary
            message = (
                f"🎒 <b>Inventario di {display_name}</b>\n\n"
                f"📊 Riepilogo:\n"
                f"• Oggetti in Vault: {vault_count}\n"
                f"• Oggetti su personaggi: {sum(character_counts.values())}\n"
                f"• Oggetti equipaggiati: {sum(equipped_counts.values())}\n"
                f"• Totale: {total_items}\n\n"
                f"<i>Per dettagli specifici su armi/armature, usa il gioco o richiedi funzionalità avanzate.</i>"
            )
            
            await self.telegram.send_message(chat_id, message)
            
            logger.info(f"Inventory for {gamertag} sent to chat {chat_id}")
            return {"success": True, "total_items": total_items}
            
        except Exception as e:
            logger.error(f"Error in handle_inventory: {e}")
            message = f"❌ Errore recupero inventario: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}

    async def handle_nightfall(self, chat_id: int) -> dict:
        """
        Get current Nightfall info (from advisors)
        """
        try:
            logger.info(f"Getting nightfall info for chat {chat_id}")
            
            # Try to get milestone data from public endpoints
            # Nightfall info is typically in the milestones
            message = (
                "⚡ <b>Nightfall settimanale</b>\n\n"
                "🎯 Informazioni attuali:\n"
                "• La stagione corrente offre nightfall con modificatori rotanti\n"
                "• Ricompense: Esotiche casuali, Prisms, Shards\n\n"
                "📅 Il nightfall cambia ogni martedì alle 18:00 CET\n\n"
                "<i>Per dettagli specifici sul modificatore e mappa correnti, usa il gioco o richiedi OAuth.</i>"
            )
            
            await self.telegram.send_message(chat_id, message)
            
            logger.info(f"Nightfall info sent to chat {chat_id}")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error in handle_nightfall: {e}")
            message = f"❌ Errore: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}

    async def handle_trials(self, chat_id: int) -> dict:
        """
        Get Trials of Osiris info
        """
        try:
            logger.info(f"Getting trials info for chat {chat_id}")
            
            message = (
                "👑 <b>Trials of Osiris</b>\n\n"
                "📅 Orari:\n"
                "• Inizio: Venerdì alle 18:00 CET\n"
                "• Fine: Martedì alle 18:00 CET\n\n"
                "🎯 Requisiti:\n"
                "• Power level consigliato: 1800+\n"
                "• Passaggio stagionale consigliato\n\n"
                "🏆 Ricompense:\n"
                "• 3 vittorie: Arma Adept\n"
                "• 5 vittorie: Armatura Adept\n"
                "• 7 vittorie: Arma Adept con perk extra\n"
                "• Flawless (7-0): Accesso al Lighthouse\n\n"
                "📍 Mappa: Cambia ogni settimana\n\n"
                "<i>Per il tuo personale storico Trials, usa: /activities tuo_gamertag</i>"
            )
            
            await self.telegram.send_message(chat_id, message)
            
            logger.info(f"Trials info sent to chat {chat_id}")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error in handle_trials: {e}")
            message = f"❌ Errore: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}

    # ============================================================================
    # DESTINY 1 COMMANDS - Delegated to D1CommandHandlers
    # ============================================================================

    async def handle_d1_find_player(self, chat_id: int, gamertag: str) -> dict:
        """Find a Destiny 1 player - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_find_player(chat_id, gamertag)
    
    async def handle_d1_activity_history(
        self, 
        chat_id: int, 
        gamertag: str, 
        mode: int = 0
    ) -> dict:
        """Get D1 activity history - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_activities(chat_id, gamertag)
    
    async def handle_d1_raid(self, chat_id: int, gamertag: str) -> dict:
        """Get D1 raid history - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_raid_history(chat_id, gamertag)
    
    async def handle_d1_xur(self, chat_id: int) -> dict:
        """Get D1 Xur status - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_xur(chat_id)
    
    async def handle_d1_inventory(self, chat_id: int, gamertag: str) -> dict:
        """Get D1 inventory - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_inventory(chat_id, gamertag)
    
    # ============================================================================
    # D1 HELPER METHODS
    # ============================================================================

    @staticmethod
    def _get_d1_class_name(class_type: int) -> str:
        """Get D1 class name from class type"""
        classes = {0: "Titano", 1: "Cacciatore", 2: "Stregone"}
        return classes.get(class_type, "Sconosciuto")

    @staticmethod
    def _get_d1_mode_name(mode: int) -> str:
        """Get D1 activity mode name"""
        modes = {
            0: "Tutte le attività",
            2: "Storia", 
            3: "Strike",
            4: "Raid",
            5: "Crogiolo",
            6: "Esplorazione"
        }
        return modes.get(mode, f"Modalità {mode}")

    async def handle_oauth_code(self, chat_id: int, auth_code: str) -> dict:
        """
        Handle OAuth authorization code from Telegram with secure storage
        """
        try:
            logger.info(f"Processing OAuth code for chat {chat_id}")
            
            # Validate auth code format
            if not self._validate_token_format(auth_code):
                message = "❌ Codice autorizzazione non valido."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Invalid auth code format"}
            
            # Exchange authorization code for access token
            from app.services.oauth_handler import get_oauth_handler
            oauth = get_oauth_handler()
            token_data = await oauth.exchange_code_for_token(auth_code)
            
            # Validate received token
            access_token = token_data.get("access_token")
            if not access_token or not self._validate_token_format(access_token):
                message = "❌ Token ricevuto non valido."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Invalid token received"}
            
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)
            
            # Calculate expiry time
            import time
            expiry_time = time.time() + expires_in
            
            # Prepare token data for storage
            token_info = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": expires_in,
                "expiry_time": expiry_time,
                "chat_id": chat_id
            }
            
            # Store token securely
            if self._secure_store_token(chat_id, token_info):
                message = (
                    f"🔐 <b>Autenticazione OAuth riuscita!</b>\n\n"
                    f"✅ Access token ricevuto\n"
                    f"⏰ Scadenza: {expires_in} secondi\n"
                    f"� <b>Token salvato in modo sicuro</b>\n\n"
                    f"<i>Ora puoi usare comandi che richiedono OAuth come equipaggiamento dettagliato</i>"
                )
            else:
                message = "❌ Errore salvataggio token sicuro."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Token storage failed"}
            
            await self.telegram.send_message(chat_id, message)
            
            logger.info(f"OAuth successful for chat {chat_id}")
            return {
                "success": True,
                "chat_id": chat_id,
                "token_received": True
            }
            
        except Exception as e:
            logger.error(f"Error in handle_oauth_code: {e}")
            message = f"❌ Errore autenticazione OAuth: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}

    async def _refresh_oauth_token(self, chat_id: int) -> dict:
        """
        Refresh OAuth token if expired with secure storage
        """
        try:
            # Get current token info
            token_info = self._secure_get_token(chat_id)
            if not token_info:
                return {"success": False, "error": "No OAuth token found"}
            
            import time
            current_time = time.time()
            expiry_time = token_info.get("expiry_time", 0)
            
            # Check if token is expired (5 minutes buffer)
            if current_time > expiry_time - 300:
                logger.info(f"Refreshing OAuth token for chat {chat_id}")
                
                from app.services.oauth_handler import get_oauth_handler
                oauth = get_oauth_handler()
                
                # Use refresh token to get new access token
                new_token_data = await oauth.refresh_token(token_info["refresh_token"])
                
                # Validate new token
                new_access_token = new_token_data.get("access_token")
                if not new_access_token or not self._validate_token_format(new_access_token):
                    logger.error(f"Invalid token received from refresh: {new_access_token}")
                    return {"success": False, "error": "Invalid refresh token"}
                
                # Update token info
                new_expiry_time = time.time() + new_token_data.get("expires_in", 3600)
                
                new_token_info = {
                    "access_token": new_access_token,
                    "refresh_token": new_token_data.get("refresh_token", token_info["refresh_token"]),
                    "expires_in": new_token_data.get("expires_in", 3600),
                    "expiry_time": new_expiry_time,
                    "chat_id": chat_id
                }
                
                # Store new token securely
                if self._secure_store_token(chat_id, new_token_info):
                    message = (
                        f"🔄 <b>Token OAuth aggiornato!</b>\n\n"
                        f"✅ Nuovo access token ricevuto\n"
                        f"⏰ Nuova scadenza: {new_token_data.get('expires_in', 3600)} secondi\n"
                        f"🔒 <b>Token salvato in modo sicuro</b>\n\n"
                        f"<i>Il tuo token è stato refreshato automaticamente</i>"
                    )
                else:
                    message = "❌ Errore aggiornamento token sicuro."
                    await self.telegram.send_message(chat_id, message)
                    return {"success": False, "error": "Token refresh failed"}
                
                logger.info(f"OAuth token refreshed for chat {chat_id}")
                return {
                    "success": True,
                    "refreshed": True,
                    "access_token": new_access_token
                }
            
            return {"success": True, "refreshed": False}
            
        except Exception as e:
            logger.error(f"Error refreshing OAuth token: {e}")
            return {"success": False, "error": str(e)}

    async def handle_oauth_status(self, chat_id: int) -> dict:
        """
        Check OAuth token status and refresh if needed with secure storage
        """
        try:
            logger.info(f"Processing OAuth status request for chat {chat_id}")
            
            # Get current token info securely
            token_info = self._secure_get_token(chat_id)
            if not token_info:
                logger.warning(f"No OAuth token found for chat {chat_id}")
                message = "🔐 Nessuna sessione OAuth trovata.\n\nUsa <code>/auth_code &lt;codice&gt;</code> per autenticarti."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "No OAuth session"}
            
            import time
            current_time = time.time()
            expiry_time = token_info.get("expiry_time", 0)
            time_remaining = int(expiry_time - current_time)
            
            logger.info(f"Token found for chat {chat_id}: {time_remaining}s remaining")
            
            # Check if refresh is needed
            refresh_result = await self._refresh_oauth_token(chat_id)
            
            # Get updated token info after refresh attempt
            updated_token_info = self._secure_get_token(chat_id)
            
            if refresh_result.get("refreshed", False):
                message = (
                    f"🔄 <b>Token OAuth aggiornato!</b>\n\n"
                    f"✅ Nuovo access token ricevuto\n"
                    f"⏰ Nuova scadenza: {updated_token_info.get('expires_in', 3600)} secondi\n"
                    f"🔒 <b>Token salvato in modo sicuro</b>\n\n"
                    f"<i>Il tuo token è stato refreshato automaticamente</i>"
                )
            else:
                hours_remaining = time_remaining // 3600
                minutes_remaining = (time_remaining % 3600) // 60
                
                storage_type = "🔒 Redis" if self.redis_client else "⚠️ Memory"
                
                message = (
                    f"🔐 <b>Stato OAuth</b>\n\n"
                    f"✅ Token attivo\n"
                    f"⏰ Scadenza: {hours_remaining}h {minutes_remaining}m\n"
                    f"🔄 Refresh automatico: <b>ATTIVO</b>\n"
                    f"🔒 Storage: {storage_type}\n\n"
                    f"<i>Il token verrà refreshato automaticamente prima della scadenza</i>"
                )
            
            logger.info(f"Sending OAuth status response to chat {chat_id}")
            await self.telegram.send_message(chat_id, message)
            
            return {
                "success": True,
                "token_active": True,
                "time_remaining": time_remaining,
                "refreshed": refresh_result.get("refreshed", False),
                "storage_type": "redis" if self.redis_client else "memory"
            }
            
        except Exception as e:
            logger.error(f"Error in handle_oauth_status: {e}")
            message = f"❌ Errore controllo OAuth: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}
    
    # ==================== DESTINY 1 METHODS ====================
    
    async def handle_d1_find_player(self, chat_id: int, gamertag: str) -> dict:
        """Find Destiny 1 player using legacy API"""
        from app.services.destiny1_service import Destiny1Service
        
        try:
            logger.info(f"[D1] Searching player: {gamertag}")
            player = Destiny1Service.search_player(gamertag)
            
            if not player:
                message = (
                    f"🔍 Giocatore D1 '<b>{gamertag}</b>' non trovato.\n\n"
                    f"💡 <b>Suggerimenti:</b>\n"
                    f"• Verifica che il gamertag sia corretto\n"
                    f"• Assicurati di aver giocato D1 su PSN/Xbox/Steam\n"
                    f"• Il profilo Bungie deve essere pubblico\n"
                    f"• Prova con maiuscole/minuscole diverse"
                )
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            
            message = (
                f"🎮 <b>Giocatore D1 trovato!</b>\n\n"
                f"👤 Nome: <code>{display_name}</code>\n"
                f"🆔 ID: <code>{membership_id}</code>\n"
                f"🎮 Piattaforma: PlayStation"
            )
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Player {gamertag} found and notified")
            
            return {
                "success": True,
                "player": {
                    "display_name": display_name,
                    "membership_id": membership_id,
                    "membership_type": 2
                }
            }
            
        except Exception as e:
            logger.error(f"[D1] Error finding player: {e}")
            message = f"❌ Errore ricerca D1: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}
    
    async def handle_d1_activity_history(self, chat_id: int, gamertag: str, mode: int = None) -> dict:
        """Get Destiny 1 activity history"""
        from app.services.destiny1_service import Destiny1Service
        
        try:
            logger.info(f"[D1] Getting activities for: {gamertag}")
            
            # Search player
            player = Destiny1Service.search_player(gamertag)
            if not player:
                message = f"🔍 Giocatore D1 '<b>{gamertag}</b>' non trovato."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            
            # Get account summary to get characters
            account = Destiny1Service.get_account(membership_id)
            if not account or not account.get("Response"):
                message = f"📭 Nessun personaggio D1 trovato per <b>{display_name}</b>."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "No characters found"}
            
            characters = account["Response"].get("data", {}).get("characters", [])
            if not characters:
                message = f"📭 Nessun personaggio D1 trovato."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "No characters"}
            
            # Get activities for first character
            character_id = characters[0].get("characterBase", {}).get("characterId")
            activities_data = Destiny1Service.get_recent_activities(membership_id, character_id)
            
            if not activities_data or not activities_data.get("Response"):
                message = f"📭 Nessuna attività recente trovata per <b>{display_name}</b>."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "No activities"}
            
            activities = activities_data["Response"].get("activities", [])
            
            # Format activities
            activity_list = []
            for i, activity in enumerate(activities[:5], 1):
                activity_type = activity.get("activityDetails", {}).get("mode", "Sconosciuto")
                activity_list.append(f"{i}. Attività tipo {activity_type}")
            
            activities_text = "\n".join(activity_list) if activity_list else "Nessuna attività recente"
            
            message = (
                f"🎮 <b>Attività D1 di {display_name}</b>\n\n"
                f"📊 Ultime attività:\n{activities_text}\n\n"
                f"<i>Destiny 1 - PlayStation</i>"
            )
            
            await self.telegram.send_message(chat_id, message)
            logger.info(f"[D1] Activities sent for {gamertag}")
            
            return {
                "success": True,
                "player": display_name,
                "activities_count": len(activities)
            }
            
        except Exception as e:
            logger.error(f"[D1] Error getting activities: {e}")
            message = f"❌ Errore attività D1: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}
    
    async def handle_d1_xur(self, chat_id: int) -> dict:
        """Get Xur, Nightfall, Trials info for D1"""
        from app.services.destiny1_service import Destiny1Service
        
        try:
            logger.info("[D1] Getting advisors (Xur, Nightfall, Trials)")
            advisors_data = Destiny1Service.get_advisors()
            
            if not advisors_data or not advisors_data.get("Response"):
                message = "📭 Impossibile recuperare informazioni weekly D1."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "No advisors data"}
            
            response = advisors_data["Response"]
            data = response.get("data", {})
            
            # Extract Xur info
            xur_data = data.get("vendorHashes", {}).get("2190858386", {})  # Xur hash
            xur_available = bool(xur_data)
            
            # Extract Nightfall info  
            nightfall = data.get("nightfallActivityHash")
            
            # Format message
            message_parts = ["🎯 <b>Attività Settimanali D1</b>\n"]
            
            # Xur
            if xur_available:
                message_parts.append("\n👳‍♂️ <b>Xûr è arrivato!</b>")
                message_parts.append("📍 Controlla la Torre o la Riva")
            else:
                message_parts.append("\n😔 <b>Xûr non è disponibile</b>")
                message_parts.append("⏰ Arriva Venerdì alle 18:00")
            
            # Nightfall
            if nightfall:
                message_parts.append(f"\n⚡ <b>Nightfall:</b> Attivo")
            
            message_parts.append("\n<i>Destiny 1 - PlayStation</i>")
            
            message = "\n".join(message_parts)
            await self.telegram.send_message(chat_id, message)
            
            logger.info("[D1] Advisors sent successfully")
            return {"success": True, "xur_available": xur_available}
            
        except Exception as e:
            logger.error(f"[D1] Error getting advisors: {e}")
            message = f"❌ Errore advisors D1: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}
    
    async def handle_d1_inventory(self, chat_id: int, gamertag: str) -> dict:
        """Get complete D1 inventory (character + vault)"""
        from app.services.destiny1_service import Destiny1Service
        
        try:
            logger.info(f"[D1] Getting inventory for: {gamertag}")
            
            # Search player
            player = Destiny1Service.search_player(gamertag)
            if not player:
                message = f"🔍 Giocatore D1 '<b>{gamertag}</b>' non trovato."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            
            # Get account summary to get characters
            account = Destiny1Service.get_account(membership_id)
            if not account or not account.get("Response"):
                message = f"📭 Nessun personaggio D1 trovato."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "No characters"}
            
            characters = account["Response"].get("data", {}).get("characters", [])
            if not characters:
                message = f"📭 Nessun personaggio D1 trovato."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "No characters"}
            
            # Get inventory for first character
            character_id = characters[0].get("characterBase", {}).get("characterId")
            character_class = self._get_class_name(characters[0].get("characterBase", {}).get("classType", 0))
            
            inventory_data = Destiny1Service.get_character_inventory(membership_id, character_id)
            vault_data = Destiny1Service.get_vault(membership_id)
            
            # Count items
            char_items = 0
            if inventory_data and inventory_data.get("Response"):
                buckets = inventory_data["Response"].get("data", {}).get("buckets", {})
                for bucket in buckets.values():
                    char_items += len(bucket)
            
            vault_items = 0
            if vault_data and vault_data.get("Response"):
                vault_items = len(vault_data["Response"].get("data", {}).get("items", []))
            
            message = (
                f"🎒 <b>Inventario D1 di {display_name}</b>\n"
                f"🛡️ Personaggio: {character_class}\n\n"
                f"📦 Oggetti personaggio: ~{char_items}\n"
                f"🏦 Oggetti vault: ~{vault_items}\n\n"
                f"<i>Destiny 1 - PlayStation</i>"
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
            logger.error(f"[D1] Error getting inventory: {e}")
            message = f"❌ Errore inventario D1: {str(e)}"
            await self.telegram.send_message(chat_id, message)
            return {"success": False, "error": str(e)}
    
    async def handle_d1_raid(self, chat_id: int, gamertag: str) -> dict:
        """Get D1 raid history with specific raid details"""
        from app.services.destiny1_service import Destiny1Service
        
        try:
            logger.info(f"[D1] Getting raid history for: {gamertag}")
            
            # Search player
            player = Destiny1Service.search_player(gamertag)
            if not player:
                message = f"🔍 Giocatore D1 '<b>{gamertag}</b>' non trovato."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "Player not found"}
            
            membership_id = player.get("membershipId")
            display_name = player.get("displayName")
            
            # Get account summary
            account = Destiny1Service.get_account(membership_id)
            if not account or not account.get("Response"):
                message = f"📭 Nessun personaggio D1 trovato."
                await self.telegram.send_message(chat_id, message)
                return {"success": False, "error": "No characters"}
            
            characters = account["Response"].get("data", {}).get("characters", [])
            if not characters:
                message = f"📭 Nessun personaggio D1 trovato."
                await self.telegram.send_message(chat_id, message)
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

    async def handle_d1_xur(self, chat_id: int) -> dict:
        """Get D1 Xur status - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_xur(chat_id)

    async def handle_d1_pvp(self, chat_id: int) -> dict:
        """Get D1 PvP info - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_pvp(chat_id)

    async def handle_d1_assalti(self, chat_id: int) -> dict:
        """Get D1 Strikes info - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_assalti(chat_id)

    async def handle_d1_elders(self, chat_id: int) -> dict:
        """Get D1 Elders info - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_elders(chat_id)

    async def handle_d1_stats(self, chat_id: int, gamertag: str) -> dict:
        """Get D1 stats - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_stats(chat_id, gamertag)

    async def handle_d1_clan(self, chat_id: int, clan_name: str) -> dict:
        """Get D1 clan - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_clan(chat_id, clan_name)

    async def handle_d1_leaderboard(self, chat_id: int) -> dict:
        """Get D1 leaderboard - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_leaderboard(chat_id)

    async def handle_d1_stats(self, chat_id: int, gamertag: str) -> dict:
        """Get D1 stats - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_stats(chat_id, gamertag)

    async def handle_d1_clan(self, chat_id: int, clan_name: str) -> dict:
        """Get D1 clan - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_clan(chat_id, clan_name)

    async def handle_d1_leaderboard(self, chat_id: int) -> dict:
        """Get D1 leaderboard - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_leaderboard(chat_id)

    async def handle_d1_speedruns(self, chat_id: int, gamertag: str) -> dict:
        """Get D1 speedruns - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_speedruns(chat_id, gamertag)

    async def handle_d1_clan_ranking(self, chat_id: int, clan_name: str) -> dict:
        """Get D1 clan ranking - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_clan_ranking(chat_id, clan_name)

    async def handle_d1_global_leaderboard(self, chat_id: int, category: str) -> dict:
        """Get D1 global leaderboard - delegates to D1CommandHandlers"""
        return await self.d1_handlers.handle_global_leaderboard(chat_id, category)
