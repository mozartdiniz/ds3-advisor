"""reason.py — read a state.json (from `extract.py`) and surface advice.

Usage:
    python reason.py <state.json>
    python reason.py <state.json> --slot 0    # focus on one slot

Rule scope (v0 POC): only what we can determine from the data the parser
currently extracts — character class, sex, level, attributes, souls, full
inventory. NO event-flag-based reasoning yet. That layer comes once the
parser locates the event-flag bitfield.

Adding rules: drop a function below, return an `Advice` or `None`, and
register it in `RULES`.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# Severity strictly ordered: warning > nudge > info.
SEVERITY_ORDER = {"warning": 0, "nudge": 1, "info": 2}


@dataclass
class Advice:
    category: str        # "lockout" | "build" | "ending" | "tip" | "checklist"
    severity: str        # "warning" | "nudge" | "info"
    rule_id: str
    title: str
    body: str


# Slot is a plain dict matching extract.py's output schema. We treat it as
# read-only data; rules return Advice or None.
Slot = dict
Rule = Callable[[Slot], Optional[Advice]]


# ---- helpers ----------------------------------------------------------------

def _owned_names(slot: Slot, category: Optional[str] = None) -> set:
    """Set of item names the character owns. Optionally filtered by category."""
    return {
        i["name"]
        for i in slot["inventory"]
        if i.get("name") and (category is None or i["category"] == category)
    }


def _has_any(slot: Slot, names: set, category: Optional[str] = None) -> set:
    return _owned_names(slot, category) & names


# ---- catalogues --------------------------------------------------------------
# Hand-curated subsets sufficient for the POC rules below. Sources: DS3 wiki.
# Catalysts are weapons that cast sorceries.
CATALYSTS = {
    "Sorcerer's Staff",
    "Heretic's Staff",
    "Court Sorcerer's Staff",
    "Man-grub's Staff",
    "Mendicant's Staff",
    "Storyteller's Staff",
    "Witchtree Branch",
    "Izalith Staff",
    "Sage's Crystal Staff",
    "Archdeacon's Great Staff",
    "Cleric's Candlestick",
    "Scholar's Candlestick",
    "Murky Longstaff",
    "Crystal Sage's Rapier",  # also casts
}

# Chimes (and talismans) cast miracles.
CHIMES_AND_TALISMANS = {
    # chimes
    "Cleric's Sacred Chime",
    "Priest's Chime",
    "Saint-tree Bellvine",
    "Crystal Chime",
    "Caitha's Chime",
    "Yorshka's Chime",
    "Saint Bident",            # casts too
    "Sacred Chime of Filianore",
    # talismans
    "Talisman",
    "Canvas Talisman",
    "Sunless Talisman",
    "Sunlight Talisman",
    "White Hair Talisman",
}

# Flames (pyromancies). Pyromancer catalyst.
FLAMES = {
    "Pyromancy Flame",
    "Pyromancer's Parting Flame",
}

# Boss souls Ludleth can trade. Map: soul name → list of options.
LUDLETH_TRADES = {
    "Soul of the Dancer":
        ["Dancer's Enchanted Swords", "Soothing Sunlight"],
    "Soul of Aldrich":
        ["Lifehunt Scythe", "Darkmoon Longbow"],
    "Soul of Pontiff Sulyvahn":
        ["Greatsword of Judgment", "Profaned Greatsword"],
    "Soul of the Old Demon King":
        ["Old King's Great Hammer", "Chaos Bed Vestiges"],
    "Soul of Yhorm the Giant":
        ["Yhorm's Great Machete", "Yhorm's Greatshield"],
    "Soul of the Twin Princes":
        ["Lorian's Greatsword", "Lothric's Holy Sword"],
    "Soul of Slave Knight Gael":
        ["Gael's Greatsword", "Repeating Crossbow"],
    "Soul of Darkeater Midir":
        ["Frayed Blade", "Old Moonlight"],
    "Soul of the Demon Prince":
        ["Demon's Scar", "Seething Chaos"],
    "Soul of Sister Friede":
        ["Friede's Great Scythe", "Rose of Ariandel"],
    "Soul of Champion Gundyr":
        ["Gundyr's Halberd", "Prayer of a Maiden"],
    "Soul of Boreal Valley Vordt":
        ["Vordt's Great Hammer", "Pierce Earth"],
    "Soul of the Rotted Greatwood":
        ["Arstor's Spear"],
    "Soul of a Crystal Sage":
        ["Crystal Sage's Rapier", "Crystal Hail"],
    "Soul of Consumed Oceiros":
        ["Moonlight Greatsword", "White Dragon Breath"],
    "Soul of the Deacons of the Deep":
        ["Cleric's Candlestick", "Deep Soul"],
    "Soul of the Blood of the Wolf":
        ["Wolf Knight's Greatsword", "Wolf Knight's Greatshield"],
    "Soul of High Lord Wolnir":
        ["Wolnir's Holy Sword", "Black Serpent"],
    "Soul of the Lords":
        ["Firelink Greatsword", "Sunlight Spear"],
    "Soul of Dragonslayer Armour":
        ["Dragonslayer Greataxe", "Dragonslayer Greatshield"],
}

# Key items the player would want to know they own.
KEY_ITEM_NUDGES = {
    "Loretta's Bone":
        "You have Loretta's Bone. Give it to the dying woman in the Undead "
        "Settlement (kicks off Cornyx's hatmaker's daughter side). Also: "
        "Greirat will only attempt the *Undead Settlement* pillage if he has "
        "Loretta's Bone in his stash — if he hasn't gone yet, deliver it before "
        "you encourage him to leave.",
    "Small Doll":
        "Small Doll opens the painting in Cathedral of the Deep to reach Irithyll, "
        "and grants entry to the Watchdogs of Farron covenant nearby.",
    "Eyes of a Fire Keeper":
        "Eyes of a Fire Keeper unlocks the Fire Keeper / End of Fire ending. "
        "Give to the Fire Keeper before you fight Soul of Cinder, or that "
        "ending path is closed for this playthrough.",
    "Storm Ruler":
        "Storm Ruler is needed to defeat Yhorm the Giant. You pick it up *inside* "
        "his arena — having it in inventory means you've reached Yhorm. If his "
        "soul is also in your inventory you've already killed him; check Ludleth "
        "for trade options.",
    "Dark Sigil":
        "Dark Sigil in inventory means Yoel of Londor has 'drawn out true strength' "
        "at least once — the Usurpation of Fire ending is on the table. You need "
        "5 Dark Sigils total before Yoel dies for Yuria to appear and continue "
        "the quest. (Hollowing count, which we don't yet read from saves, tells "
        "you exactly how many sigils you have.)",
    "Pale Tongue":
        "Pale Tongues are the Rosaria's Fingers covenant offering, also used to "
        "respec at Rosaria's Bed Chamber in the Cathedral of the Deep. "
        "Covenant ranks: 10 tongues = rank +1, 30 = rank +2. Each respec also "
        "consumes one tongue (5 respecs total per playthrough).",
    "Old Cell Key":
        "Old Cell Key opens Siegward's cell in Profaned Capital. Free him *before* "
        "the Yhorm fight — he summons in and a key Siegward conversation triggers.",
    "Transposing Kiln":
        "Transposing Kiln: hand it to Ludleth of Courland at Firelink to unlock "
        "soul transposition — that's what lets you trade boss souls for unique "
        "weapons and spells. Until you give it to him, your boss souls just sit "
        "in your inventory.",
    "Grave Key":
        "Grave Key opens the locked grave in the Undead Settlement (the Mortician's "
        "house area) — leads to extra loot. No lockout, just a missable.",
}


# F — covenant badges. Owning one means you've joined (or can join) that
# covenant. Reliable: the badge item resolves by name from the inventory grid.
COVENANT_ITEMS = {
    "Way of Blue":
        "low-stakes co-op/PvP protection — summons Blue Sentinels/Darkmoons to "
        "help when you're invaded. Joined via Emma in the High Wall.",
    "Blue Sentinels":
        "the auto-summon defender covenant. Rank up with Proof of a Concord Kept.",
    "Blades of the Darkmoon":
        "Yorshka's covenant (Anor Londo). Rank up with Proof of a Concord Kept. "
        "Joining requires reaching Yorshka — tied to the Sirris questline.",
    "Warrior of Sunlight":
        "jolly co-operation. Offer Sunlight Medals to rank up. Altar is in the "
        "Undead Settlement (behind an illusory wall, requires a small detour).",
    "Mound-makers":
        "chaotic PvP — given by Holy Knight Hodrick. Offer Vertebra Shackles. "
        "Note Hodrick is also part of Sirris's questline; killing him affects it.",
    "Watchdogs of Farron":
        "guards Farron Keep as an invader. Joined via the Small Doll-adjacent "
        "covenant altar near the Old Wolf of Farron. Offer Wolf's Blood Swordgrass.",
    "Aldrich Faithful":
        "defends Anor Londo (Aldrich's domain). Offer Human Dregs to rank up.",
    "Rosaria's Fingers":
        "PvP covenant at Rosaria's Bed Chamber (Cathedral of the Deep). Offer "
        "Pale Tongues. Rosaria also lets you respec and rebuild your appearance.",
}


# H — area-keyed missable / lockout nudges. Keyed by the human-readable area
# name; many bonfires map to one area. Reliable because last_bonfire is parsed
# and validated. These are prevent-regret pointers, not a walkthrough.
def _area_of(bonfire_name: Optional[str]) -> Optional[str]:
    if not bonfire_name:
        return None
    return _BONFIRE_TO_AREA.get(bonfire_name)


_BONFIRE_TO_AREA = {
    "Firelink Shrine": "firelink",
    "High Wall of Lothric": "high_wall",
    "Tower on the Wall": "high_wall",
    "Foot of the High Wall": "high_wall",
    "Vordt of the Boreal Valley": "high_wall",
    "Undead Settlement": "undead_settlement",
    "Dilapidated Bridge": "undead_settlement",
    "Cliff Underside": "undead_settlement",
    "Road of Sacrifices": "road_of_sacrifices",
    "Halfway Fortress": "road_of_sacrifices",
    "Crystal Sage": "road_of_sacrifices",
    "Cathedral of the Deep": "cathedral",
    "Cleansing Chapel": "cathedral",
    "Rosaria's Bed Chamber": "cathedral",
    "Deacons of the Deep": "cathedral",
    "Farron Keep": "farron",
    "Keep Ruins": "farron",
    "Farron Keep Perimeter": "farron",
    "Old Wolf of Farron": "farron",
    "Abyss Watchers": "farron",
    "Catacombs of Carthus": "catacombs",
    "High Lord Wolnir": "catacombs",
    "Irithyll of the Boreal Valley": "irithyll",
    "Central Irithyll": "irithyll",
    "Church of Yorshka": "irithyll",
    "Distant Manor": "irithyll",
    "Pontiff Sulyvahn": "irithyll",
    "Anor Londo": "irithyll",
    "Prison Tower": "irithyll",
    "Irithyll Dungeon": "profaned",
    "Profaned Capital": "profaned",
    "Old Cell": "profaned",
    "Lothric Castle": "lothric_castle",
    "Dragon Barracks": "lothric_castle",
    "Dragonslayer Armour": "lothric_castle",
    "Grand Archives": "lothric_castle",
    "Twin Princes": "lothric_castle",
    "Kiln of the First Flame": "kiln",
}

LOCATION_TIPS = {
    "firelink": (
        "You're at Firelink Shrine — the NPC hub",
        "Recurring checks here: hand the Transposing Kiln to Ludleth (unlocks "
        "boss-soul trades); buy from the Shrine Handmaid (her stock grows as you "
        "give her NPC ashes); and remember most NPCs you recruit relocate *here*. "
        "If a quest NPC has gone quiet, check they didn't move into the Shrine.",
    ),
    "high_wall": (
        "You're on the High Wall of Lothric",
        "Missables before you leave: free **Greirat** from his cell (need the Cell "
        "Key, found nearby) — he's a key merchant. Talk to **Emma** for the Small "
        "Lothric Banner (and to join Way of Blue). Vordt's fog gate is the area "
        "boundary; you can still backtrack until much later.",
    ),
    "undead_settlement": (
        "You're in the Undead Settlement",
        "High-lockout-risk area:\n"
        "  • Recruit **Cornyx** (pyromancy trainer) — caged near the entrance.\n"
        "  • **Irina of Carim** (miracle trainer) is reachable from the Catacombs-"
        "side cell behind a wall — needs the **Grave Key**.\n"
        "  • Pick up **Loretta's Bone** (hanging corpse by the giant's tower) and "
        "give it to the dying woman — and Greirat needs it stashed before his "
        "Undead Settlement pillage.\n"
        "  • **Hodrick** (Mound-makers covenant) is here via the Pit of Hollows.\n"
        "  • The tower **giant** befriends you if you don't get him shot — he aids "
        "with crow-trade items and arrows.",
    ),
    "road_of_sacrifices": (
        "You're at the Road of Sacrifices",
        "Recruit **Orbeck of Vinheim** (sorcery trainer) — he's on the upper path. "
        "Critically: **buy at least one spell or give him a scroll**, or he leaves "
        "and dies later. **Sirris** has a summon sign for the Crystal Sage here; "
        "her quest desyncs if you skip her signs. **Hawkwood** is at Firelink and "
        "leaves around this point.",
    ),
    "cathedral": (
        "You're at the Cathedral of the Deep",
        "**Rosaria** (Bed Chamber, behind the Deacons) lets you respec and rebuild "
        "appearance, and runs the Rosaria's Fingers covenant. **Patches** appears "
        "here and can be recruited to Firelink (he matters for Greirat's later "
        "Irithyll pillage and Siegward). The Cathedral is a long detour off the "
        "main path — easy to under-explore.",
    ),
    "farron": (
        "You're at Farron Keep",
        "**Watchdogs of Farron** covenant altar is by the Old Wolf. **Sirris** has "
        "another summon sign here (Abyss Watchers). Hawkwood's questline continues "
        "around the Abyss Watchers fight. Light all three Estus-soup... err, the "
        "three braziers to open the boss path.",
    ),
    "catacombs": (
        "You're in the Catacombs of Carthus",
        "**Anri of Astora / Horace** questline runs through here — Horace can get "
        "stranded in the Smouldering Lake below; finding him matters for Anri's "
        "quest (and the Usurpation ending if you're stabbing Anri). Don't rush "
        "Wolnir before checking the side paths.",
    ),
    "irithyll": (
        "You're in Irithyll of the Boreal Valley",
        "Quest-dense area:\n"
        "  • **Anri's wedding** happens at the Church of Yorshka (Sirris quest / "
        "Usurpation path) — timing-sensitive.\n"
        "  • **Sirris** summon sign vs. the invader near Pontiff.\n"
        "  • **Yorshka** (Blades of the Darkmoon covenant) is reachable via Sirris.\n"
        "  • Crossing into Irithyll is a soft gate — wrap up Road/Cathedral/Farron "
        "NPC business first.",
    ),
    "profaned": (
        "You're at the Irithyll Dungeon / Profaned Capital",
        "Free **Siegward** from his cell with the **Old Cell Key** (bought from the "
        "Shrine Handmaid after Patches takes over) *before* the Yhorm fight — Yhorm "
        "needs the **Storm Ruler**, and Siegward's summon there is a signature "
        "moment you'll lose if he's still locked up. **Karla** (dark/pyromancy "
        "trainer) is caged in the Dungeon.",
    ),
    "lothric_castle": (
        "You're at Lothric Castle / Grand Archives",
        "The endgame approaches. **Orbeck** should have his full stock by now — "
        "buy any sorceries you still want (he won't be a vendor forever). Make "
        "sure any NPC summons/quest steps you care about are done before the Twin "
        "Princes — several quests resolve around here.",
    ),
    "kiln": (
        "⚠️ You're at the Kiln of the First Flame — POINT OF NO RETURN",
        "Beyond Soul of Cinder there is no return this cycle. Before you commit:\n"
        "  • **Eyes of a Fire Keeper** must already be *given* to the Fire Keeper "
        "for the End of Fire ending.\n"
        "  • For **Usurpation of Fire**: Yuria alive, all Dark Sigils, Anri dealt "
        "with.\n"
        "  • Finish any NPC questlines (Siegward, Sirris, Greirat, Orbeck, Anri) — "
        "they cannot be completed in NG after this.\n"
        "  • Spend boss souls / souls you don't want to risk; grab any remaining "
        "unique items.",
    ),
}

# Stat caps (DS3). Past the hard cap, additional points give almost nothing —
# flag as wasted investment. Endurance stamina stops scaling at 40.
_STAT_HARD_CAP = {
    "strength": 60, "dexterity": 60, "intelligence": 60, "faith": 60,
    "vigor": 50, "endurance": 40, "luck": 60,
}


# ---- rules ------------------------------------------------------------------

def rule_int_no_catalyst(slot: Slot) -> Optional[Advice]:
    """E — build viability: high INT with nothing to cast with."""
    s = slot["stats"]
    if not s:
        return None
    if s["intelligence"] < 14:
        return None
    if _has_any(slot, CATALYSTS, "weapon"):
        return None
    return Advice(
        category="build",
        severity="nudge",
        rule_id="E.int_no_catalyst",
        title=f"INT {s['intelligence']} but no catalyst owned",
        body=(
            f"Your Intelligence is {s['intelligence']}, but you don't have a "
            "catalyst (staff). You need one to cast sorceries. Sorcerer's Staff "
            "is the starting catalyst — buy one from Orbeck of Vinheim once "
            "he's at Firelink, or pick up the Heretic's Staff in Farron Keep."
        ),
    )


def rule_faith_no_chime(slot: Slot) -> Optional[Advice]:
    """E — build viability: high FAITH with nothing to cast with."""
    s = slot["stats"]
    if not s:
        return None
    if s["faith"] < 14:
        return None
    if _has_any(slot, CHIMES_AND_TALISMANS, "weapon"):
        return None
    return Advice(
        category="build",
        severity="nudge",
        rule_id="E.faith_no_chime",
        title=f"FAITH {s['faith']} but no chime or talisman owned",
        body=(
            f"Your Faith is {s['faith']}, but you don't have a chime or "
            "talisman. You need one to cast miracles. Cleric's Sacred Chime is "
            "the Cleric starting weapon; Talisman is bought from the Shrine "
            "Handmaid; Saint-tree Bellvine from Irina."
        ),
    )


def rule_boss_souls_untraded(slot: Slot) -> Optional[Advice]:
    """E — build viability: list Ludleth trades available right now."""
    owned = _owned_names(slot, "good")
    available = {soul: trades for soul, trades in LUDLETH_TRADES.items()
                 if soul in owned}
    if not available:
        return None
    lines = [
        f"  • {soul} → {' or '.join(trades)}"
        for soul, trades in available.items()
    ]
    return Advice(
        category="build",
        severity="info",
        rule_id="E.ludleth_trades_available",
        title=f"{len(available)} boss soul(s) you could trade at Ludleth",
        body=(
            "You have unused boss souls in inventory. Ludleth of Courland (at "
            "Firelink, if you've placed his Lord of Cinders ashes) can transpose "
            "them into unique weapons or spells:\n" + "\n".join(lines)
        ),
    )


def rule_key_item_nudges(slot: Slot) -> Optional[Advice]:
    """H — informational tips about specific key items in inventory.

    Returns one composite Advice listing all matched key items, so the chat
    feed doesn't get spammed with a separate message per item.
    """
    owned = _owned_names(slot, "good")
    hits = [(name, msg) for name, msg in KEY_ITEM_NUDGES.items() if name in owned]
    if not hits:
        return None
    sections = "\n\n".join(f"**{name}** — {msg}" for name, msg in hits)
    return Advice(
        category="tip",
        severity="info",
        rule_id="H.key_item_nudges",
        title=f"{len(hits)} notable key item(s) in your inventory",
        body=sections,
    )


def rule_usurpation_progress(slot: Slot) -> Optional[Advice]:
    """D (partial) — ending path: detect Yoel/Yuria progression signals.

    Without the hollowing count we can only say "this path is active". A more
    precise version of this rule lands once the parser reads the hollowing
    field.
    """
    owned = _owned_names(slot, "good")
    sigil_present = "Dark Sigil" in owned
    if not sigil_present:
        return None
    return Advice(
        category="ending",
        severity="nudge",
        rule_id="D.usurpation_path_active",
        title="Usurpation of Fire ending path is active",
        body=(
            "Dark Sigil in inventory: Yoel of Londor has drawn out your "
            "strength at least once. The Usurpation of Fire ending requires "
            "**5** Dark Sigils total before Yoel dies, after which Yuria "
            "appears at Firelink. We can't yet read your exact sigil count "
            "from the save file — when we can, this rule will tell you "
            "exactly how many more free levels you can take before Yoel's "
            "death deadline.\n\n"
            "Reminder: Dark Sigils permanently increase Hollowing each time "
            "you die. Buy Purging Stones from Yuria or use the Statue of "
            "Velka if your appearance bothers you — but DO NOT cure the "
            "Dark Sigils via Anri's hidden stab or you'll break this ending."
        ),
    )


def rule_caster_no_flame(slot: Slot) -> Optional[Advice]:
    """E — build viability: invested in both INT and FAITH (a pyromancy spread)
    but owns nothing to cast with. Pyromancy scales off both stats."""
    s = slot["stats"]
    if not s:
        return None
    if s["intelligence"] < 12 or s["faith"] < 12:
        return None
    # If they already own ANY catalyst/chime/flame, they can cast — no nudge.
    if (_has_any(slot, CATALYSTS, "weapon")
            or _has_any(slot, CHIMES_AND_TALISMANS, "weapon")
            or _has_any(slot, FLAMES, "weapon")):
        return None
    return Advice(
        category="build",
        severity="nudge",
        rule_id="E.caster_no_flame",
        title=f"INT {s['intelligence']} + FAITH {s['faith']} but nothing to cast with",
        body=(
            "You've put points into both Intelligence and Faith — that's the "
            "pyromancy spread (pyromancies scale off both). But you have no "
            "Pyromancy Flame, staff, or chime in inventory. Recruit Cornyx in "
            "the Undead Settlement and he'll give you the Pyromancy Flame for "
            "free; that's almost certainly the catalyst your stats are pointing at."
        ),
    )


def rule_low_vigor(slot: Slot) -> Optional[Advice]:
    """E — build viability: under-invested Vigor for the character's level."""
    s = slot["stats"]
    if not s:
        return None
    if s["level"] < 25 or s["vigor"] >= 18:
        return None
    return Advice(
        category="build",
        severity="nudge",
        rule_id="E.low_vigor",
        title=f"Vigor {s['vigor']} is low for level {s['level']}",
        body=(
            f"At level {s['level']} your Vigor is only {s['vigor']}, which makes "
            "you very fragile against DS3's hard-hitting bosses. Vigor gives the "
            "most HP per point up to about 27 (then 44). Pushing it into the "
            "20s is usually the single biggest survivability upgrade — consider "
            "spending your next few levels here."
        ),
    )


def rule_stat_overinvest(slot: Slot) -> Optional[Advice]:
    """E — build viability: points sunk past the hard cap are nearly wasted."""
    s = slot["stats"]
    if not s:
        return None
    over = [
        (name, s[name], cap)
        for name, cap in _STAT_HARD_CAP.items()
        if s.get(name, 0) > cap
    ]
    if not over:
        return None
    lines = [
        f"  • {name.capitalize()} {val} (effective ceiling ~{cap})"
        for name, val, cap in over
    ]
    return Advice(
        category="build",
        severity="info",
        rule_id="E.stat_overinvest",
        title=f"{len(over)} stat(s) invested past their effective ceiling",
        body=(
            "These attributes are past the point where extra points do much — "
            "the returns are nearly flat:\n" + "\n".join(lines) + "\n"
            "Not a problem if you're already where you want to be, but if you're "
            "still leveling, points elsewhere (Vigor, a second scaling stat) buy "
            "more. Endurance stamina, in particular, stops growing at 40."
        ),
    )


def rule_covenant_badges(slot: Slot) -> Optional[Advice]:
    """F — covenant progression: report which covenants the character holds."""
    owned_all = _owned_names(slot)
    hits = [(name, desc) for name, desc in COVENANT_ITEMS.items()
            if name in owned_all]
    if not hits:
        return None
    lines = [f"**{name}** — {desc}" for name, desc in hits]
    return Advice(
        category="covenant",
        severity="info",
        rule_id="F.covenant_badges",
        title=f"{len(hits)} covenant(s) available to you",
        body=(
            "You hold these covenant badges (equip one at a bonfire to be in "
            "that covenant):\n\n" + "\n\n".join(lines)
        ),
    )


def rule_location_tips(slot: Slot) -> Optional[Advice]:
    """H — area-keyed missable / lockout nudges based on the last bonfire."""
    area = _area_of(slot.get("last_bonfire_name"))
    if area is None or area not in LOCATION_TIPS:
        return None
    title, body = LOCATION_TIPS[area]
    severity = "warning" if area == "kiln" else "info"
    return Advice(
        category="tip" if area != "kiln" else "checklist",
        severity=severity,
        rule_id=f"H.area.{area}",
        title=title,
        body=body,
    )


RULES: List[Rule] = [
    rule_int_no_catalyst,
    rule_faith_no_chime,
    rule_caster_no_flame,
    rule_low_vigor,
    rule_stat_overinvest,
    rule_boss_souls_untraded,
    rule_covenant_badges,
    rule_key_item_nudges,
    rule_location_tips,
    rule_usurpation_progress,
]


# ---- runner -----------------------------------------------------------------

def evaluate(slot: Slot) -> List[Advice]:
    out: List[Advice] = []
    for rule in RULES:
        try:
            advice = rule(slot)
        except Exception as e:  # pragma: no cover — rule bugs shouldn't crash run
            print(f"  rule {rule.__name__} raised {type(e).__name__}: {e}",
                  file=sys.stderr)
            continue
        if advice is not None:
            out.append(advice)
    out.sort(key=lambda a: SEVERITY_ORDER.get(a.severity, 99))
    return out


def render(slot: Slot, advice: List[Advice]) -> str:
    header = (
        f"Slot {slot['index']}: {slot['name']} — "
        f"{slot.get('class') or '?'} / {slot.get('sex') or '?'} / "
        f"lvl {slot.get('level')}"
    )
    if not advice:
        return f"{header}\n  (no rules fired)\n"
    lines = [header, "-" * len(header)]
    for a in advice:
        lines.append(f"\n[{a.severity.upper():<7}] [{a.category}] {a.title}")
        lines.append(f"  rule: {a.rule_id}")
        for body_line in a.body.split("\n"):
            lines.append(f"  {body_line}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("state", type=Path, help="path to state.json produced by extract.py")
    p.add_argument("--slot", type=int, default=None,
                   help="only evaluate this slot index (default: all populated)")
    args = p.parse_args()

    if not args.state.exists():
        print(f"file not found: {args.state}", file=sys.stderr)
        return 1
    state = json.loads(args.state.read_text())

    slots_to_run = [s for s in state["slots"] if s["occupied"]]
    if args.slot is not None:
        slots_to_run = [s for s in slots_to_run if s["index"] == args.slot]
    if not slots_to_run:
        print("no populated slots to evaluate", file=sys.stderr)
        return 1

    print(f"# {state['source']}")
    print(f"# saved {state['save_mtime']}\n")
    for slot in slots_to_run:
        advice = evaluate(slot)
        print(render(slot, advice))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
