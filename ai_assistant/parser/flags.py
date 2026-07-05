"""DS3 event-flag reader — structural, semantic, portable across characters.

How it works (cracked 2026-06-11; see ai_assistant_design/flag_research.md):

The slot payload is a sequential serialization of game structures. Walking it
field-by-field (same walk as alfizari's save editor) yields `event_flag_start`,
a FIXED-SIZE (0x33E5E bytes) event-flag section. At `event_flag_start + 0x5D`
begins a byte-for-byte copy of the game's in-memory world-flag blob (the one
the TGA cheat table reads at [[SprjEventFlagMan]+0]).

Inside the blob, flags live in 0x500-byte per-map blocks grouped in per-type
regions. A semantic flag ID (the same IDs used by EMEVD, the wiki flag list,
and cheat tables) decodes as:

    flag_id = T * 10_000_000 + AABB * 1000 + local      (8-digit IDs)
    flag_id = local                                      (commons, < 30720)

    T    = system digit (1 = event, 6 = object, 7 = talk)
    AABB = map code (3000 = m30_00 High Wall, 4000 = m40_00 Firelink, ...)

    byte = region_origin(T) + map_slot(AABB)*0x500
           + (local//32)*4 + 3 - ((local%32)//8)
    bit  = 7 - local % 8

(The +3-((...)//8) term: flags are u32 little-endian words, bit 31 = local 0.)

Verified against: TGA CT hardcoded offsets (156 entries), alfizari boss/bonfire
distances (exact +0x6F match), and controlled save pairs across THREE different
characters (QA slot 4, Greirat slot 5, quest_track slot 4) — same semantic IDs
decode from all of them.

NOTE: payloads from crypto.decrypt_entry() have the 4-byte length prefix
stripped; all constants here are in stripped-payload space (alfizari's
published offsets are 4 bytes higher).
"""
from __future__ import annotations

import struct
from typing import Optional

# ---------------------------------------------------------------------------
# Structural walk to the event-flag section
# ---------------------------------------------------------------------------

_GAITEM_START = 0x6C          # 0x70 in length-prefixed space
_GAITEM_SLOTS = 6144
_ITEM_TYPE_WEAPON = 0x80000000
_ITEM_TYPE_ARMOR = 0x90000000

FLAG_SECTION_SIZE = 0x33E5E   # fixed size of the event-flag section
BLOB_DELTA = 0x5D             # blob origin relative to event_flag_start


def _gaitem_end(payload: bytes) -> int:
    """Walk the gaitem registry (variable size: weapons/armor are 60 bytes)."""
    off = _GAITEM_START
    for _ in range(_GAITEM_SLOTS):
        handle = struct.unpack_from("<I", payload, off)[0]
        off += 8
        if handle != 0 and (handle & 0xF0000000) in (_ITEM_TYPE_WEAPON, _ITEM_TYPE_ARMOR):
            off += 52
    return off


def find_event_flag_start(payload: bytes) -> Optional[int]:
    """Walk the slot payload structure to the event-flag section start.

    Mirrors alfizari's parse_save() chain. Returns None on a malformed walk
    (counted-table size that runs past the payload).
    """
    try:
        end_offset = _gaitem_end(payload)
        inventory_start = end_offset + 0x13F + 0x1DD
        above_storage_counter = inventory_start + 0x8808 + 0x11C
        above_storage_size = struct.unpack_from("<I", payload, above_storage_counter)[0]
        table_1_end = above_storage_counter + 4 + above_storage_size * 8
        storage_box_start = table_1_end + 0x18C + 0x4
        gesture_end = storage_box_start + 0x8800 + 0xC + 0xA4
        table_2_size = struct.unpack_from("<I", payload, gesture_end)[0]
        table_2_end = gesture_end + 4 + table_2_size * 4
        efs = table_2_end + 0x92 + 0xBCC
    except struct.error:
        return None
    if efs + FLAG_SECTION_SIZE > len(payload):
        return None
    return efs


def find_flag_blob(payload: bytes) -> Optional[int]:
    """Absolute offset of the in-memory-format world-flag blob, or None."""
    efs = find_event_flag_start(payload)
    return None if efs is None else efs + BLOB_DELTA


# ---------------------------------------------------------------------------
# Semantic flag-ID codec
# ---------------------------------------------------------------------------

# Map code (AABB digits) -> block slot within a region. From the TGA cheat
# table world-flag offsets: slot = (CT_map_base - 0xF00) / 0x500.
MAP_SLOT = {
    3000: 0,    # m30_00 High Wall of Lothric
    3010: 1,    # m30_01 Lothric Castle
    3100: 2,    # m31_00 Undead Settlement
    3200: 4,    # m32_00 Archdragon Peak
    3300: 6,    # m33_00 Road of Sacrifices / Farron Keep
    3410: 8,    # m34_01 Grand Archives
    3500: 9,    # m35_00 Cathedral of the Deep
    3700: 12,   # m37_00 Irithyll / Anor Londo
    3800: 13,   # m38_00 Catacombs / Smouldering Lake
    3900: 14,   # m39_00 Irithyll Dungeon / Profaned Capital
    4000: 15,   # m40_00 Cemetery of Ash / Firelink Shrine
    4100: 16,   # m41_00 Kiln of the First Flame
    4500: 17,   # m45_00 Painted World of Ariandel (DLC1)
    5000: 20,   # m50_00 The Dreg Heap (DLC2)
    5100: 21,   # m51_00 The Ringed City (DLC2)
    5110: 22,   # m51_10 Filianore's Rest (DLC2)
}

# System digit -> region origin within the blob (empirically verified:
# type 1 from CT offsets; type 6 from CT door/shortcut offsets; type 7
# validated via talk flags 74000600/74000300 in controlled saves).
REGION_ORIGIN = {
    1: 0x00F00,   # event flags   1AABBCCC(C)
    6: 0x1FE00,   # object flags  6AABBCCC(C)
    7: 0x2A300,   # talk flags    7AABBCCC(C)
}

COMMONS_MAX = 30720          # commons region: blob[0x000:0xF00] = ids 0..30719
BLOCK_BYTES = 0x500          # one map block = 10240 flags


def _local_offset(local: int) -> tuple[int, int]:
    """(byte, bit) of a local flag index within its block (u32 LE words)."""
    return (local // 32) * 4 + 3 - ((local % 32) // 8), 7 - local % 8


def flag_offset(flag_id: int) -> Optional[tuple[int, int]]:
    """Semantic flag ID -> (byte offset within blob, bit). None if unmapped."""
    if 0 <= flag_id < COMMONS_MAX:
        byte, bit = _local_offset(flag_id)
        return byte, bit
    t = flag_id // 10_000_000
    origin = REGION_ORIGIN.get(t)
    if origin is None:
        return None
    rem = flag_id - t * 10_000_000
    # AABB*1000 + local with local possibly 4 digits: try both splits and
    # keep the one whose AABB is a real map and local fits the block.
    for aabb in (rem // 1000, rem // 10000 * 10):
        slot = MAP_SLOT.get(aabb)
        if slot is None:
            continue
        local = rem - aabb * 1000
        if 0 <= local < BLOCK_BYTES * 8:
            byte, bit = _local_offset(local)
            return origin + slot * BLOCK_BYTES + byte, bit
    return None


_SLOT_TO_MAP = {v: k for k, v in MAP_SLOT.items()}


def decode_offset(rel: int, bit: int) -> Optional[int]:
    """Inverse of flag_offset: blob-relative (byte, bit) -> semantic flag ID.

    Returns None for blocks whose map slot / region is not in the tables.
    """
    if rel < 0:
        return None
    if rel < 0xF00:
        word, biw = rel // 4, rel % 4
        return word * 32 + (3 - biw) * 8 + (7 - bit)
    for t, origin in REGION_ORIGIN.items():
        span = (max(MAP_SLOT.values()) + 1) * BLOCK_BYTES
        if origin <= rel < origin + span:
            slot = (rel - origin) // BLOCK_BYTES
            aabb = _SLOT_TO_MAP.get(slot)
            if aabb is None:
                return None
            within = rel - origin - slot * BLOCK_BYTES
            word, biw = within // 4, within % 4
            local = word * 32 + (3 - biw) * 8 + (7 - bit)
            return t * 10_000_000 + aabb * 1000 + local
    return None


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------

def read_flag(payload: bytes, blob_start: int, flag_id: int) -> Optional[int]:
    """Return 0/1 for flag_id, or None if the flag can't be located."""
    loc = flag_offset(flag_id)
    if loc is None:
        return None
    byte, bit = loc
    pos = blob_start + byte
    if pos >= len(payload):
        return None
    return (payload[pos] >> bit) & 1


def read_flags(payload: bytes, blob_start: int,
               flag_ids: list[int]) -> dict[int, Optional[int]]:
    return {fid: read_flag(payload, blob_start, fid) for fid in flag_ids}


def read_all_known(payload: bytes, blob_start: int) -> dict[int, int]:
    result = {}
    for fid in KNOWN_FLAGS:
        val = read_flag(payload, blob_start, fid)
        if val is not None:
            result[fid] = val
    return result


# Backwards-compatible alias used by older scripts. The old implementation
# located an inventory index — it is gone; this now returns the flag blob.
def find_bit_blocks_start(payload: bytes) -> Optional[int]:
    return find_flag_blob(payload)


def diff_flags(payload_a: bytes, payload_b: bytes):
    """Diff the full flag sections of two slot payloads (same character).

    Returns (set_flags, cleared_flags) — lists whose entries are semantic flag
    IDs (int) where decodable, else "?rel0x{rel:X}b{bit}" strings for bits in
    blocks not yet in the region/map tables.
    """
    ba, bb = find_flag_blob(payload_a), find_flag_blob(payload_b)
    if ba is None or bb is None:
        raise ValueError("could not locate flag blob in one of the payloads")
    sets, clears = [], []
    for rel in range(FLAG_SECTION_SIZE - BLOB_DELTA):
        x, y = payload_a[ba + rel], payload_b[bb + rel]
        if x == y:
            continue
        for bit in range(8):
            old, new = (x >> bit) & 1, (y >> bit) & 1
            if old != new:
                fid = decode_offset(rel, bit)
                entry = fid if fid is not None else f"?rel0x{rel:X}b{bit}"
                (sets if new else clears).append(entry)
    return sets, clears


# ---------------------------------------------------------------------------
# Known semantic flag IDs
#
# Boss "defeated" flags follow the per-map pattern local 800 (801 =
# encountered); offsets cross-checked against the TGA cheat table and the
# soulsmodding wiki flag list. Quest flags below were validated empirically
# via controlled save pairs on three characters (2026-06-11).
# ---------------------------------------------------------------------------

BOSS_FLAGS: dict[int, str] = {
    14000800: "Iudex Gundyr defeated",
    13000800: "Vordt of the Boreal Valley defeated",
    13100800: "Curse-Rotted Greatwood defeated",
    13300800: "Abyss Watchers defeated",
    13300850: "Crystal Sage defeated",
    13500800: "Deacons of the Deep defeated",
    13800800: "High Lord Wolnir defeated",
    13800830: "Old Demon King defeated",
    13700850: "Pontiff Sulyvahn defeated",
    13700800: "Aldrich, Devourer of Gods defeated",
    13900800: "Yhorm the Giant defeated",
    13000890: "Dancer of the Boreal Valley defeated",
    13000830: "Oceiros, the Consumed King defeated",
    13010800: "Dragonslayer Armour defeated",
    13410830: "Lothric, Younger Prince (Twin Princes) defeated",
    13200850: "Nameless King defeated",
    14000830: "Champion Gundyr defeated",
    14100800: "Soul of Cinder defeated",
    14500800: "Sister Friede defeated (DLC1)",
    14500860: "Champion's Gravetender defeated (DLC1)",
    15000800: "Demon Prince defeated (DLC2)",
    15100800: "Halflight, Spear of the Church defeated (DLC2)",
    15100850: "Darkeater Midir defeated (DLC2)",
    15110800: "Slave Knight Gael defeated (DLC2)",
}

QUEST_FLAGS: dict[int, str] = {
    # Greirat (validated: greirat-quest + quest-track + play_00 corpora)
    63000156: "Greirat freed from his cell (High Wall)",
    1225:     "Greirat recruited (at Firelink)",
    1226:     "Greirat away scavenging (state)",
    74000300: "Loretta's Bone given to Greirat",
    74000301: "Loretta's Bone given to Greirat (secondary)",
    74000302: "Greirat sent to scavenge Undead Settlement",
    74000303: "Greirat sent to scavenge Undead Settlement (secondary)",

    # Yoel / Yuria (validated: quest-track + play_00)
    73100150: "Talked to Yoel of Londor (dying pilgrims)",
    74000400: "Yoel of Londor: Dark Sigil drawn (free level)",
    74000600: "Talked to Yuria of Londor (at Firelink)",

    # Irina / Eygon of Carim (validated: quest-track step 08, play_00 28/31/39)
    73100100: "Talked to Irina of Carim (sewer cell)",
    74000350: "Talked to Irina of Carim (at Firelink)",
    73100300: "Talked to Eygon of Carim (at Irina's cell)",

    # Siegward (validated: play_00 step 27)
    73100363: "Siegward: talked after Fire Demon fight",

    # Hodrick / Leonhard / Cornyx (validated: play_00 steps 32, 35, 38;
    # 74000850 label independently confirmed by the TGA cheat table)
    73100400: "Talked to Holy Knight Hodrick (Pit of Hollows)",
    74000850: "Talked to Leonhard (at Firelink)",
    74000450: "Talked to Cornyx (at Firelink)",
}

KNOWN_FLAGS: dict[int, str] = {**BOSS_FLAGS, **QUEST_FLAGS}
