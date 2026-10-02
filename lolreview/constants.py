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

# Role quests (2026). The timeline has no quest events; a quest item is destroyed once, when its
# quest is done (9-14 min in 100 Challenger games). The support quest is done when Runic Compass
# upgrades to Bounty of Worlds. Top, top with Teleport, mid, bot, jungle, support:
QUEST_DONE_ITEMS = {1200, 1222, 1201, 1202, 1204, 3866}
MID_QUEST = 1201  # done: tier-2 boots become tier 3
BOT_QUEST = 1202  # done: boots move to an extra slot
CONTROL_WARD = 2055  # supports keep these in the quest slot
# Items that turn into another with no purchase event, only the old one's ITEM_DESTROYED.
SILENT_UPGRADES = {3004: 3042, 3003: 3040, 3119: 3121}  # tears once stacked
# The support item's steps. World Atlas is bought with participantId 0, and which upgrade Bounty of
# Worlds (3867) became isn't an event, so it's read off the end items.
SUPPORT_UPGRADES = {3865: 3866, 3866: 3867}
SUPPORT_FINAL = {3869, 3870, 3871, 3876, 3877}
# Tier-2 boots -> tier 3, from the Mid Lane quest.
MID_BOOTS = {
    3006: 3172, 3008: 3168, 3009: 3170, 3013: 3176, 3020: 3175, 3047: 3174, 3111: 3173,
    3158: 3171,
}  # fmt: skip
BOOTS = {1001, 2422, 3010, 3117, *MID_BOOTS, *MID_BOOTS.values()}
# The Magical Footwear rune gives Slightly Magical Footwear with no event; the minute it arrived
# is the rune's var1 in the match.
FOOTWEAR_RUNE = 8304
FOOTWEAR = 2422
ELIXIRS = {2138, 2139, 2140}  # drunk when bought, so they never take a slot
