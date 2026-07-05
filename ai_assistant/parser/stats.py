"""Per-slot stat block reader.

DS3 save slots have variable layout — the absolute position of any field
shifts depending on how many items the character owns (the item registry at
the front of the slot grows). All offsets below are therefore expressed
*relative to the character-name position*, which is the stable anchor (and
the same anchor souls_givifier uses).

Engine storage order is `VIG, ATT, END, STR, DEX, INT, FTH, LCK, pad, pad,
VIT, LEVEL, SOULS`. VIT is separated from the rest because it was added
later in the Souls series and slotted in at the end of the existing block.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

# Offset from `name_pos` to the start of the stat block (negative — stats
# come *before* the name). Verified across the Wanderer, max-level, sl_715,
# and Usurpation saves.
STATS_OFFSET_FROM_NAME = -68

# Offsets within the stats block (u32 LE each).
_OFF_VIG   = 0x00
_OFF_ATT   = 0x04
_OFF_END   = 0x08
_OFF_STR   = 0x0C
_OFF_DEX   = 0x10
_OFF_INT   = 0x14
_OFF_FTH   = 0x18
_OFF_LCK   = 0x1C
# 0x20, 0x24 — padding (always 0 in observed saves)
_OFF_VIT   = 0x28
_OFF_LEVEL = 0x2C
_OFF_SOULS = 0x30


@dataclass
class CharacterStats:
    """Core character stats. Fields in UI order, not engine order."""
    level: int
    souls: int
    vigor: int
    attunement: int
    endurance: int
    vitality: int
    strength: int
    dexterity: int
    intelligence: int
    faith: int
    luck: int


def parse_stats(payload: bytes, name_offset: int) -> CharacterStats:
    """Read the stat block relative to a known name offset."""
    base = name_offset + STATS_OFFSET_FROM_NAME

    def _u32(off: int) -> int:
        return struct.unpack_from("<I", payload, base + off)[0]

    return CharacterStats(
        level        = _u32(_OFF_LEVEL),
        souls        = _u32(_OFF_SOULS),
        vigor        = _u32(_OFF_VIG),
        attunement   = _u32(_OFF_ATT),
        endurance    = _u32(_OFF_END),
        vitality     = _u32(_OFF_VIT),
        strength     = _u32(_OFF_STR),
        dexterity    = _u32(_OFF_DEX),
        intelligence = _u32(_OFF_INT),
        faith        = _u32(_OFF_FTH),
        luck         = _u32(_OFF_LCK),
    )
