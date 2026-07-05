"""Enumerate DS3 character slots and extract per-slot summary data.

For v0 we only pull the character name — enough to validate that BND4 parsing
and AES decryption work end-to-end. The full stat block (level, sex, class,
attributes, inventory, event flags) is a follow-up step.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from . import bnd4, crypto, equipment as equip_mod, inventory as inv_mod, stats as stats_mod, userdata as ud_mod

NUM_CHARACTER_SLOTS = 10
NAME_MAX_CHARS = 16  # DS3 enforces a 16-character limit in the UI

# Playtime sits at the top of the slot payload as u32 LE milliseconds.
# Cross-checked against the load-screen timestamps for every slot.
_PLAYTIME_MS_OFFSET = 8

# Sex and starting-class fields are 1-byte values immediately past the
# 32-byte name buffer. Offsets are relative to the character-name position.
_SEX_OFFSET_FROM_NAME   = 34   # u8 — 1=Male, 0=Female
_CLASS_OFFSET_FROM_NAME = 38   # u8 — see CLASS_NAMES below

# DS3 starting-class enum, in the order shown on the New Game class screen.
CLASS_NAMES = [
    "Knight", "Mercenary", "Warrior", "Herald", "Thief",
    "Assassin", "Sorcerer", "Pyromancer", "Cleric", "Deprived",
]


@dataclass
class SlotSummary:
    """Summary of one character slot."""
    index: int
    name: Optional[str]
    sex: Optional[str]              # "Male" / "Female"
    character_class: Optional[str]  # human-readable class name
    class_id: Optional[int]         # raw enum
    playtime_seconds: Optional[int] # from user-data entry, not slot payload
    last_bonfire_id: Optional[int]  # BonfireWarpParam-like enum from userdata
    last_bonfire_name: Optional[str]
    stats: Optional[stats_mod.CharacterStats]
    inventory: List[inv_mod.InventoryItem]
    equipment: List[equip_mod.EquipmentSlot]
    payload: bytes                  # full decrypted slot data


def _find_name_offset(payload: bytes, expected_name: str) -> Optional[int]:
    """Locate the character name in the slot payload using the value from
    user-data as the anchor. Returns the byte offset, or None if not found.

    DS3 slot layout shifts with how many items the character owns (variable-
    size item registry at the front), so the absolute offset of the name
    isn't fixed across saves.

    Short names (e.g. "QA") have many spurious matches in binary data, so
    every candidate is validated by checking the sex byte (+34) and class
    byte (+38) that the character structure places immediately after the name.
    """
    needle = expected_name.encode("utf-16-le")
    if not needle:
        return None
    pos = 0
    while True:
        idx = payload.find(needle, pos)
        if idx < 0:
            return None
        sex_pos = idx + _SEX_OFFSET_FROM_NAME
        cls_pos = idx + _CLASS_OFFSET_FROM_NAME
        if (sex_pos < len(payload) and payload[sex_pos] in (0, 1) and
                cls_pos < len(payload) and 0 <= payload[cls_pos] < len(CLASS_NAMES)):
            return idx
        pos = idx + 1


def _read_class_and_sex(payload: bytes, name_offset: int):
    """Return (class_name, class_id, sex_label) relative to the name."""
    import struct
    sex_raw   = payload[name_offset + _SEX_OFFSET_FROM_NAME]
    class_raw = payload[name_offset + _CLASS_OFFSET_FROM_NAME]
    sex = "Male" if sex_raw == 1 else ("Female" if sex_raw == 0 else None)
    class_name = (
        CLASS_NAMES[class_raw] if 0 <= class_raw < len(CLASS_NAMES) else None
    )
    return class_name, class_raw, sex


def load_slots(
    sl2_path: Path,
    id_maps: Optional[dict] = None,
) -> List[SlotSummary]:
    """Decrypt and summarise all character slots in the save file.

    Pass `id_maps` (from `inventory.load_id_maps`) to resolve item names; if
    omitted, inventory items still load with `name=None`.
    """
    import struct as _struct
    raw = sl2_path.read_bytes()
    entries = bnd4.parse_entries(raw)

    # User-data tells us which slots are occupied and what each character
    # is named — we use those names to find the per-slot name offsets, which
    # then anchor everything else.
    ud_payload = crypto.decrypt_entry(raw, *entries[ud_mod.USERDATA_ENTRY_INDEX])
    ud_slots = ud_mod.parse_userdata(ud_payload)

    slots: List[SlotSummary] = []
    for idx in range(min(NUM_CHARACTER_SLOTS, len(entries))):
        off, size = entries[idx]
        ud = ud_slots[idx] if idx < len(ud_slots) else None
        if size == 0 or ud is None or not ud.occupied:
            slots.append(SlotSummary(
                idx, None, None, None, None, None, None, None, None, [], [], b"",
            ))
            continue
        payload = crypto.decrypt_entry(raw, off, size)
        playtime_ms = _struct.unpack_from("<I", payload, _PLAYTIME_MS_OFFSET)[0]
        playtime_sec = playtime_ms // 1000
        name_off = _find_name_offset(payload, ud.name or "")
        if name_off is None or name_off < 0:
            # Slot occupied per user-data but name not locatable — surface as
            # name from user-data with no further fields parsed.
            slots.append(SlotSummary(
                idx, ud.name, None, None, None, playtime_sec,
                ud.last_bonfire_id, ud.last_bonfire_name, None, [], [], payload,
            ))
            continue
        class_name, class_id, sex = _read_class_and_sex(payload, name_off)
        char_stats = stats_mod.parse_stats(payload, name_off)
        items = inv_mod.parse_inventory(payload, name_off, id_maps)
        equipped = equip_mod.parse_equipment(payload, name_off, id_maps or {})
        slots.append(SlotSummary(
            idx, ud.name, sex, class_name, class_id, playtime_sec,
            ud.last_bonfire_id, ud.last_bonfire_name,
            char_stats, items, equipped, payload,
        ))
    return slots
