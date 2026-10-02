TIERS = [
    "IRON",
    "BRONZE",
    "SILVER",
    "GOLD",
    "PLATINUM",
    "EMERALD",
    "DIAMOND",
    "MASTER",
    "GRANDMASTER",
    "CHALLENGER",
]
TIER_INDEX = {t: i for i, t in enumerate(TIERS)}
PRO_TIER_INDEX = 10
APEX_TIERS = ["MASTER", "GRANDMASTER", "CHALLENGER"]
DIVISIONS = ["I", "II", "III", "IV"]

QUEUE_RANKED_SOLO = 420
REMAKE_MAX_S = 300

PLATFORM_TO_CLUSTER = {
    "na1": "americas",
    "br1": "americas",
    "la1": "americas",
    "la2": "americas",
    "euw1": "europe",
    "eun1": "europe",
    "tr1": "europe",
    "ru": "europe",
    "me1": "europe",
    "kr": "asia",
    "jp1": "asia",
    "oc1": "sea",
    "sg2": "sea",
    "tw2": "sea",
    "vn2": "sea",
}
CLUSTERS = ["americas", "europe", "asia", "sea"]

ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
BLUE = 100
RED = 200

DRAGON_TYPES = {
    "FIRE_DRAGON": "Infernal",
    "EARTH_DRAGON": "Mountain",
    "WATER_DRAGON": "Ocean",
    "AIR_DRAGON": "Cloud",
    "HEXTECH_DRAGON": "Hextech",
    "CHEMTECH_DRAGON": "Chemtech",
}
ELDER = "ELDER_DRAGON"
