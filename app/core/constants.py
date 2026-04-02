"""
Constants and configuration values for Destiny 1/2 services
"""

# Membership Types
class MembershipType:
    XBOX = 1
    PLAYSTATION = 2
    STEAM = 3
    BLIZZARD = 4
    STADIA = 5
    EPIC = 6

# D1 Activity Modes
class D1ActivityMode:
    NONE = 0
    STORY = 2
    STRIKE = 3
    RAID = 4
    CRUCIBLE = 5
    PATROL = 6
    NIGHTFALL = 16
    TRIALS = 19

# D1 Raid Hashes with Italian names
D1_RAID_NAMES = {
    # Vault of Glass - Antro di Cristallo
    "2048260250": "🟡 Antro di Cristallo (Normale)",
    "1946620227": "🟡 Antro di Cristallo (Difetto)",
    "1014020645": "🟡 Antro di Cristallo (390)",
    "2178968300": "🟡 Antro di Cristallo (Prestigio)",
    # Crota's End - La Fine di Crota
    "2693136600": "🟢 La Fine di Crota (Normale)",
    "1375099857": "🟢 La Fine di Crota (Difetto)",
    "2324748950": "🟢 La Fine di Crota (390)",
    "2184393900": "🟢 La Fine di Crota (Prestigio)",
    # King's Fall - La Caduta del Re
    "2437930460": "🔵 La Caduta del Re (Normale)",
    "3500794796": "🔵 La Caduta del Re (Difetto)",
    "1142458582": "🔵 La Caduta del Re (390)",
    "2186849900": "🔵 La Caduta del Re (Prestigio)",
    "2197680900": "🔵 La Caduta del Re (Sfida)",
    # Wrath of the Machine - Ira della Macchina
    "10898880": "🔴 Ira della Macchina (Normale)",
    "2608159054": "🔴 Ira della Macchina (Eroica)",
    "2200634800": "🔴 Ira della Macchina (Prestigio)",
    "2201622100": "🔴 Ira della Macchina (Sfida)",
    # Prison of Elders
    "2444515908": "🟣 Prigione degli Anziani (Liv. 32)",
    "2444515909": "🟣 Prigione degli Anziani (Liv. 34)",
    "2444515910": "🟣 Prigione degli Anziani (Liv. 35)",
    # Strikes
    "1836893158": "⚡ Assalto: Schiavitù Cabal",
    "2332037829": "⚡ Assalto: Cripta di Crota",
    "4287936728": "⚡ Assalto: Abisso Infinito",
    "2680821749": "⚡ Assalto: Città del Vetro",
    "3848655169": "⚡ Assalto: Desolazione",
    "4107311651": "⚡ Assalto: Tomba di Oryx",
    "2082069811": "⚡ Assalto: Dreadnaught",
    "4163254841": "⚡ Assalto: PvP: Rift",
    "3156370673": "⚡ Assalto: Oro Sfuggente",
    "2846352253": "⚡ Assalto: Il Mondo Sepolto",
    # Additional Strike hashes
    "3602734444": "⚡ Assalto: Velocità Oscura",
    "1719392426": "⚡ Assalto: Sepoltura delle Lamine",
    "4260139096": "⚡ Assalto: Tenebre Profonde",
    "2375659209": "⚡ Assalto: L'Abisso",
    "2507231369": "⚡ Assalto: L'Oscurità",
    "3292667840": "⚡ Assalto: Eco del Tuono",
    # Nightfall Activities
    "2693077237": "🌙 Nightfall: L'Eco del Vuoto",
    "2680821749": "🌙 Nightfall: Città del Vetro", 
    "3848655169": "🌙 Nightfall: Desolazione",
    "4107311651": "🌙 Nightfall: Tomba di Oryx",
    "2082069811": "🌙 Nightfall: Dreadnaught",
    # Challenge of Elders
    "3902439766": "🏆 Sfida degli Anziani",
    "391517884": "🏆 Sfida: Punteggio Alto",
}

# Xur Vendor Hash (D1)
XUR_VENDOR_HASH = "2190858386"

# Default membership type for searches
DEFAULT_MEMBERSHIP_TYPE = MembershipType.STEAM

# Cache TTLs (in seconds)
CACHE_TTL_SHORT = 300  # 5 minutes
CACHE_TTL_MEDIUM = 1800  # 30 minutes
CACHE_TTL_LONG = 3600  # 1 hour

# API Timeouts
API_TIMEOUT = 10  # seconds
