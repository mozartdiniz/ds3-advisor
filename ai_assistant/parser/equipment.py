"""Read the currently-equipped weapon, armor, and ring loadout.

All offsets are relative to the character-name position (name_offset), which
is the stable anchor used throughout this parser (see slots.py).

Verified against QA saves 01–40 and Dark Tarnished (NG+5):
  name+492  left-hand weapon/shield (slot A)
  name+496  right-hand weapon       (slot A)
  name+540  head armor
  name+544  chest armor
  name+548  hand armor
  name+552  leg armor
  name+556  ring slot 1
  name+560  ring slot 2
  name+564  ring slot 3
  name+568  ring slot 4

Encoding quirks:
- Weapons/shields: stored as base_item_id + upgrade_level (0–10 for normal,
  0–5 for unique). Lookup strips the upgrade suffix by trying base-0 first,
  then base-1 … base-10. The resolved name is suffixed with " +N".
- Armor: stored with high byte 0x01 regardless of the 0x1X category byte in
  the armor map. Lookup uses the lower 3 bytes.
- Rings: stored WITHOUT the high byte 0x20 that the ring map uses. Lookup
  adds 0x20000000 before consulting the map. Ring tier variants (+1/+2/+3)
  are stored as base_id+tier (same +1-per-level scheme as weapons).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_WEAPON_SLOTS = [
    (492, "left_hand"),
    (496, "right_hand"),
]
_ARMOR_SLOTS = [
    (540, "head"),
    (544, "chest"),
    (548, "hands"),
    (552, "legs"),
]
_RING_SLOTS = [
    (556, "ring_1"),
    (560, "ring_2"),
    (564, "ring_3"),
    (568, "ring_4"),
]

# Sentinel values that mean "nothing equipped in this slot".
_EMPTY = frozenset({0xFFFFFFFF, 0x00000000, 0x0001ADB0})

# Maximum upgrade levels to probe when resolving weapon names.
# Normal weapons go to +10; unique/boss weapons go to +5.
_MAX_WEAPON_UPGRADE = 10


@dataclass
class EquipmentSlot:
    slot: str
    item_id: Optional[int]   # None when slot is empty; stored value (with upgrade/tier)
    base_item_id: Optional[int]  # base item ID (upgrade stripped); same as item_id for un-upgraded
    upgrade_level: Optional[int]  # 0 for base, N for +N
    name: Optional[str]      # None when item_id not in the ID map; includes " +N" suffix when N>0


def _resolve_weapon(val: int, wmap: Dict[int, str]) -> Tuple[int, int, Optional[str]]:
    """Return (base_id, upgrade_level, name_or_None) for a weapon/shield slot value."""
    for lvl in range(_MAX_WEAPON_UPGRADE + 1):
        base = val - lvl
        if base in wmap:
            suffix = f" +{lvl}" if lvl > 0 else ""
            return base, lvl, wmap[base] + suffix
    return val, 0, None


def _resolve_ring(val: int, rmap: Dict[int, str]) -> Tuple[int, int, Optional[str]]:
    """Return (base_id, tier, name_or_None) for a ring slot value.

    Ring IDs in equipment slots omit the high byte 0x20 present in the ring
    map. Tier variants (+1/+2/+3) follow the same +1-per-level scheme.
    """
    for tier in range(4):  # base + up to +3
        full_id = (val - tier) | 0x20000000
        if full_id in rmap:
            suffix = f" +{tier}" if tier > 0 else ""
            return full_id, tier, rmap[full_id] + suffix
    return val, 0, None


def parse_equipment(
    payload: bytes,
    name_offset: int,
    id_maps: Dict[str, Dict[int, str]],
) -> List[EquipmentSlot]:
    """Return the equipped loadout as a list of EquipmentSlot records."""
    wmap = id_maps.get("weapon", {})
    amap = id_maps.get("armor", {})
    rmap = id_maps.get("ring", {})

    # Armor is stored with high byte 0x01 in the slot but may have a different
    # high byte in the armor map. Key by lower 3 bytes to bridge the gap.
    armor_by_lower: Dict[int, str] = {
        iid & 0x00FFFFFF: name for iid, name in amap.items()
    }

    def ru32(delta: int) -> int:
        return struct.unpack_from("<I", payload, name_offset + delta)[0]

    result: List[EquipmentSlot] = []

    for delta, label in _WEAPON_SLOTS:
        val = ru32(delta)
        if val in _EMPTY:
            result.append(EquipmentSlot(label, None, None, None, None))
        else:
            base_id, upgrade, name = _resolve_weapon(val, wmap)
            result.append(EquipmentSlot(label, val, base_id, upgrade, name))

    for delta, label in _ARMOR_SLOTS:
        val = ru32(delta)
        if val in _EMPTY:
            result.append(EquipmentSlot(label, None, None, None, None))
        else:
            lower = val & 0x00FFFFFF
            name = armor_by_lower.get(lower)
            result.append(EquipmentSlot(label, val, val, 0, name))

    for delta, label in _RING_SLOTS:
        val = ru32(delta)
        if val in _EMPTY:
            result.append(EquipmentSlot(label, None, None, None, None))
        else:
            base_id, tier, name = _resolve_ring(val, rmap)
            result.append(EquipmentSlot(label, val, base_id, tier, name))

    return result
