"""DS3 user-data file parser — BND4 entry 10.

This file is what the in-game LOAD GAME screen reads: per-slot summary used
to render the slot list (name, level, playtime, location, character face).

Layout (from souls_givifier source and empirical probing):

    offset 4244 (10 bytes)       slot occupancy: 1 byte per slot, 1=populated
    offset 4254                  per-slot records start
    stride 554                   bytes per slot record
    record +0   (32 bytes)       name (UTF-16-LE, up to 16 chars + null)
    record +34  (u32 LE)         level
    record +38  (u32 LE)         playtime, seconds
    record +50  (u16 LE)         last bonfire ID (BonfireWarpParam-like enum)
    record +rest                 face / appearance data, etc.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from . import bnd4, crypto

USERDATA_ENTRY_INDEX = 10

OCCUPANCY_OFFSET = 4244
SLOT_RECORDS_OFFSET = 4254
SLOT_RECORD_STRIDE = 554
NUM_SLOTS = 10

_NAME_LEN = 32
_LEVEL_OFFSET = 34
_PLAYTIME_OFFSET = 38
_BONFIRE_OFFSET = 50  # u16 LE — the load-screen "location" enum, found by
                      # diffing 4 slots at 4 distinct locations (2026-05-28).

# Area codes stored at userdata record +50 (u16 LE). Each code covers all
# bonfires in one map area. Formula from BonfireWarpParam: WarpEventId //
# 10000 * 10 = area code (e.g. 3001950 → 300 * 10 = 3000).
# Confirmed empirical values (from QA corpus): 3000, 3100, 4000, 4005, 4100, 5100.
# Remaining entries derived from BonfireWarpParam (2026-05-30); verify from
# controlled saves as encountered.
BONFIRE_NAMES: dict[int, str] = {
    # base game — confirmed empirical
    3000: "High Wall of Lothric",
    3100: "Undead Settlement",
    4000: "Cemetery of Ash",
    4005: "Firelink Shrine",      # anomaly: same map (m40) as Cemetery, stored as 4005
    4100: "Kiln of the First Flame",
    5100: "The Ringed City",
    # base game — derived from BonfireWarpParam (WarpEventId // 10000 * 10)
    3010: "Lothric Castle",
    3200: "Archdragon Peak",
    3300: "Road of Sacrifices / Farron Keep",
    3410: "Grand Archives",
    3500: "Cathedral of the Deep",
    3700: "Irithyll of the Boreal Valley",
    3800: "Catacombs of Carthus / Smouldering Lake",
    3900: "Irithyll Dungeon / Profaned Capital",
    # DLC — derived
    4500: "Painted World of Ariandel",
    5000: "The Dreg Heap",
    5110: "Filianore's Rest",
}


@dataclass
class UserDataSlot:
    """One slot's load-screen summary."""
    index: int
    occupied: bool
    name: Optional[str]
    level: Optional[int]
    playtime_seconds: Optional[int]
    last_bonfire_id: Optional[int]
    last_bonfire_name: Optional[str]  # resolved via BONFIRE_NAMES, None if unknown


def parse_userdata(payload: bytes) -> List[UserDataSlot]:
    occ = payload[OCCUPANCY_OFFSET : OCCUPANCY_OFFSET + NUM_SLOTS]
    slots: List[UserDataSlot] = []
    for i in range(NUM_SLOTS):
        occupied = bool(occ[i] & 0x01)
        if not occupied:
            slots.append(UserDataSlot(i, False, None, None, None, None, None))
            continue
        rec_off = SLOT_RECORDS_OFFSET + i * SLOT_RECORD_STRIDE
        name_raw = payload[rec_off : rec_off + _NAME_LEN]
        name = name_raw.decode("utf-16-le", errors="ignore").split("\x00", 1)[0]
        level = struct.unpack_from("<I", payload, rec_off + _LEVEL_OFFSET)[0]
        playtime = struct.unpack_from("<I", payload, rec_off + _PLAYTIME_OFFSET)[0]
        bonfire_id = struct.unpack_from("<H", payload, rec_off + _BONFIRE_OFFSET)[0]
        bonfire_name = BONFIRE_NAMES.get(bonfire_id)
        slots.append(UserDataSlot(
            i, True, name, level, playtime, bonfire_id, bonfire_name,
        ))
    return slots


def load_userdata(sl2_path: Path) -> List[UserDataSlot]:
    """Decrypt entry 10 of the .sl2 archive and parse the per-slot summary."""
    raw = sl2_path.read_bytes()
    entries = bnd4.parse_entries(raw)
    payload = crypto.decrypt_entry(raw, *entries[USERDATA_ENTRY_INDEX])
    return parse_userdata(payload)
