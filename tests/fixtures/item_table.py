"""Small made-up item catalogue for the synthetic games: id -> (name, cost, components)."""

from collections import Counter

ITEMS: dict[int, tuple[str, int, list[int]]] = {
    1001: ("Boots", 300, []),
    1004: ("Faerie Charm", 250, []),
    1006: ("Rejuvenation Bead", 150, []),
    1011: ("Giant's Belt", 900, []),
    1018: ("Cloak of Agility", 600, []),
    1026: ("Blasting Wand", 850, []),
    1027: ("Sapphire Crystal", 350, []),
    1028: ("Ruby Crystal", 400, []),
    1029: ("Cloth Armor", 300, []),
    1033: ("Null-Magic Mantle", 450, []),
    1036: ("Long Sword", 350, []),
    1037: ("Pickaxe", 875, []),
    1038: ("B. F. Sword", 1300, []),
    1042: ("Dagger", 300, []),
    1043: ("Recurve Bow", 700, []),
    1052: ("Amplifying Tome", 435, []),
    1054: ("Doran's Shield", 450, []),
    1055: ("Doran's Blade", 450, []),
    1056: ("Doran's Ring", 400, []),
    1058: ("Needlessly Large Rod", 1250, []),
    1101: ("Scorchclaw Pup", 450, []),
    2003: ("Health Potion", 50, []),
    2055: ("Control Ward", 75, []),
    3006: ("Berserker's Greaves", 1100, [1001, 1042]),
    3020: ("Sorcerer's Shoes", 1100, [1001]),
    3031: ("Infinity Edge", 3450, [1038, 1018]),
    3033: ("Mortal Reminder", 3000, [1037, 1043]),
    3036: ("Lord Dominik's Regards", 3000, [1037, 1018]),
    3047: ("Plated Steelcaps", 1100, [1001, 1029]),
    3053: ("Sterak's Gage", 3200, [1037, 1011]),
    3068: ("Sunfire Aegis", 2700, [1029, 1011]),
    3071: ("Black Cleaver", 3000, [1037, 1011]),
    3075: ("Thornmail", 2700, [1029, 1011]),
    3085: ("Runaan's Hurricane", 2600, [1043, 1042]),
    3089: ("Rabadon's Deathcap", 3600, [1058, 1026]),
    3135: ("Void Staff", 3000, [1026, 1033]),
    3143: ("Randuin's Omen", 2700, [1029, 1011]),
    3157: ("Zhonya's Hourglass", 3250, [1026, 1029]),
    3158: ("Ionian Boots of Lucidity", 900, [1001]),
    3190: ("Locket of the Iron Solari", 2200, [1004, 1029]),
    3340: ("Stealth Ward", 0, []),
    3364: ("Oracle Lens", 0, []),
    3802: ("Lost Chapter", 1300, [1052, 1027]),
    3865: ("World Atlas", 400, []),
    6617: ("Moonstone Renewer", 2200, [1004, 1006]),
    6655: ("Luden's Tempest", 3200, [3802, 1026]),
}

TRINKETS = (3340, 3364)
SELLABLE_STARTERS = (1054, 1055, 1056)


def plan_buy(inventory: list[int], item: int) -> tuple[list[int], int]:
    """Components of `item` that get consumed from `inventory`, and the gold actually paid."""
    owned = Counter(inventory)
    destroyed: list[int] = []

    def consume(target: int) -> None:
        for comp in ITEMS[target][2]:
            if owned[comp] > 0:
                owned[comp] -= 1
                destroyed.append(comp)
            else:
                consume(comp)

    consume(item)
    paid = ITEMS[item][1] - sum(ITEMS[c][1] for c in destroyed)
    return destroyed, paid


def next_component(inventory: list[int], item: int, gold: int) -> int | None:
    """The most expensive affordable piece of `item` not yet owned (drilling into sub-recipes)."""
    owned = Counter(inventory)

    def find(target: int) -> int | None:
        for comp in sorted(ITEMS[target][2], key=lambda c: -ITEMS[c][1]):
            if owned[comp] > 0:
                owned[comp] -= 1
                continue
            if ITEMS[comp][1] <= gold:
                return comp
            sub = find(comp)
            if sub is not None:
                return sub
        return None

    return find(item)
