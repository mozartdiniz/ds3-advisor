"""snapshot.py - shared save-state snapshot + structured diff.

Used by watcher.py (live saves), play_simulator.py (replayed saves) and the
advisor pipeline. One snapshot per slot per save event; diffs between two
snapshots yield the human-readable event list.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from parser import bnd4, crypto, userdata as ud_mod
from parser.slots import load_slots
from parser.inventory import load_id_maps
from parser.flags import find_flag_blob, KNOWN_FLAGS, read_flag

DATA_DIR = Path(__file__).resolve().parent / "data"


class SlotSnap:
    def __init__(self, index, name, level, souls, bonfire_name, bonfire_id,
                 playtime, inventory, equipment, flags_set, stats=None):
        self.index        = index
        self.name         = name
        self.level        = level
        self.souls        = souls
        self.bonfire_name = bonfire_name
        self.bonfire_id   = bonfire_id
        self.playtime     = playtime
        self.inventory    = inventory      # dict: item_name -> count
        self.equipment    = equipment      # dict: slot -> item_name
        self.flags_set    = flags_set      # set of semantic flag_ids (KNOWN_FLAGS only)
        self.stats        = stats or {}    # dict: vigor/attunement/.../luck -> int


# Items that uniquely signal a boss kill (kept alongside boss flags as a
# fallback for bosses whose flag is not yet validated)
ITEM_TO_KILL: dict[str, str] = {
    "Coiled Sword":                      "Killed Iudex Gundyr",
    "Soul of Boreal Valley Vordt":       "Killed Vordt of the Boreal Valley",
    "Soul of the Blood of the Wolf":     "Killed Abyss Watchers",
    "Soul of Yhorm the Giant":           "Killed Yhorm the Giant",
    "Soul of Aldrich":                   "Killed Aldrich, Devourer of Gods",
    "Soul of a Crystal Sage":            "Killed Crystal Sage",
    "Soul of the Deacons of the Deep":   "Killed Deacons of the Deep",
    "Soul of Pontiff Sulyvahn":          "Killed Pontiff Sulyvahn",
    "Soul of Dragonslayer Armour":       "Killed Dragonslayer Armour",
    "Soul of Champion Gundyr":           "Killed Champion Gundyr",
    "Soul of Consumed Oceiros":          "Killed Oceiros, the Consumed King",
    "Soul of the Twin Princes":          "Killed Lothric and Lorian",
    "Soul of the Lords":                 "Killed Soul of Cinder",
    "Soul of Sister Friede":             "Killed Sister Friede",
    "Soul of Slave Knight Gael":         "Killed Slave Knight Gael",
}

SLOT_LABELS: dict[str, str] = {
    "left_hand": "left hand", "right_hand": "right hand",
    "head": "head", "chest": "chest", "hands": "hands", "legs": "legs",
    "ring_1": "ring", "ring_2": "ring", "ring_3": "ring", "ring_4": "ring",
}


def snap_slot(sl2: Path, slot_idx: int, data_dir: Path = DATA_DIR) -> Optional[SlotSnap]:
    """Parse one slot of a save file into a SlotSnap (None if unoccupied)."""
    id_maps = load_id_maps(data_dir)
    summaries = load_slots(sl2, id_maps=id_maps)
    if slot_idx >= len(summaries):
        return None
    s = summaries[slot_idx]
    if not s.name or s.stats is None:
        return None

    inv = {}
    for item in s.inventory:
        key = item.name or ("item_%010x" % item.item_id)
        inv[key] = inv.get(key, 0) + item.count

    flags_on = set()
    if s.payload:
        blob = find_flag_blob(s.payload)
        if blob is not None:
            for fid in KNOWN_FLAGS:
                if read_flag(s.payload, blob, fid) == 1:
                    flags_on.add(fid)

    equip = {}
    for e in s.equipment:
        if e.item_id is not None:
            equip[e.slot] = e.name or ("item_%010x" % e.item_id)

    stats = {
        "vigor": s.stats.vigor, "attunement": s.stats.attunement,
        "endurance": s.stats.endurance, "vitality": s.stats.vitality,
        "str": s.stats.strength, "dex": s.stats.dexterity,
        "int": s.stats.intelligence, "fth": s.stats.faith,
        "luck": s.stats.luck,
    }

    return SlotSnap(
        index=slot_idx, name=s.name, level=s.stats.level,
        souls=s.stats.souls, bonfire_name=s.last_bonfire_name,
        bonfire_id=s.last_bonfire_id, playtime=s.playtime_seconds or 0,
        inventory=inv, equipment=equip, flags_set=flags_on, stats=stats,
    )


def get_all_playtimes(sl2: Path) -> dict[int, int]:
    """Return {slot_idx: playtime_seconds} for all occupied slots."""
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    ud_payload = crypto.decrypt_entry(raw, *entries[ud_mod.USERDATA_ENTRY_INDEX])
    ud_slots = ud_mod.parse_userdata(ud_payload)
    return {ud.index: (ud.playtime_seconds or 0)
            for ud in ud_slots if ud.occupied and ud.name}


def detect_changed_slot(old_times: dict[int, int], new_times: dict[int, int]) -> Optional[int]:
    """Return the slot whose playtime changed, or None."""
    for idx in new_times:
        if new_times[idx] != old_times.get(idx, -1):
            return idx
    return None


def diff_events(prev: Optional[SlotSnap], curr: SlotSnap) -> list[str]:
    """Structured event lines between two snapshots of the same character."""
    if prev is None or prev.name != curr.name:
        bonfire = curr.bonfire_name or ("bonfire#%s" % curr.bonfire_id)
        return ["Rested at %s" % bonfire]

    events: list[str] = []

    if curr.level != prev.level:
        diff = curr.level - prev.level
        events.append("Level up: %d -> %d  (+%d)" % (prev.level, curr.level, diff))

    if curr.bonfire_id != prev.bonfire_id:
        bonfire = curr.bonfire_name or ("bonfire#%s" % curr.bonfire_id)
        prev_b = prev.bonfire_name or str(prev.bonfire_id)
        events.append("Rested at %s  (from %s)" % (bonfire, prev_b))

    soul_diff = curr.souls - prev.souls
    if soul_diff != 0:
        sign = "+" if soul_diff > 0 else ""
        events.append("Souls: %s -> %s  (%s%s)" % (
            "{:,}".format(prev.souls), "{:,}".format(curr.souls),
            sign, "{:,}".format(soul_diff)))

    for name in sorted(curr.inventory):
        gained = curr.inventory[name] - prev.inventory.get(name, 0)
        if gained > 0:
            qty = (" x%d" % gained) if gained > 1 else ""
            events.append("Got %s%s" % (name, qty))
            kill = ITEM_TO_KILL.get(name)
            if kill:
                events.append(kill)

    for name in sorted(prev.inventory):
        lost = prev.inventory[name] - curr.inventory.get(name, 0)
        if lost > 0:
            qty = (" x%d" % lost) if lost > 1 else ""
            events.append("Lost %s%s" % (name, qty))

    all_slots = sorted(set(list(curr.equipment) + list(prev.equipment)))
    for slot in all_slots:
        p_item = prev.equipment.get(slot)
        c_item = curr.equipment.get(slot)
        if p_item == c_item:
            continue
        # Suppress unnamed->unnamed transitions (e.g. weapon upgrade level change)
        if (p_item and p_item.startswith("item_") and
                c_item and c_item.startswith("item_")):
            continue
        label = SLOT_LABELS.get(slot, slot)
        if c_item and not p_item:
            events.append("Equipped %s (%s)" % (c_item, label))
        elif p_item and not c_item:
            events.append("Unequipped %s (%s)" % (p_item, label))
        else:
            events.append("%s: %s -> %s" % (label, p_item, c_item))

    for fid in sorted(curr.flags_set - prev.flags_set):
        if fid in KNOWN_FLAGS:
            events.append(KNOWN_FLAGS[fid])

    return events
