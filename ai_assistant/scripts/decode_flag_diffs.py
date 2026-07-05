"""Decode every flag-section bit change between consecutive saves into
(block_base, local) coordinates, and validate the block->flag-prefix model.

Block model (save blob, origin = event_flag_start + 0x5D):
  commons:      0x00000 - 0x00EFF   flag ids 0..30719
  type-1 maps:  0x00F00 + slot*0x500   (event flags 1AABBCCC[C])
  type-6 maps:  0x1FE00 + slot*0x500   (object flags 6AABBCCC[C])
  type-7 maps:  0x2A300 + slot*0x500   (talk flags  7AABBCCC[C])  <- hypothesis
  map slots: m30_00=0 m30_01=1 m31_00=2 m32_00=4 m33_00=6 m34_01=8 m35_00=9
             m37_00=12 m38_00=13 m39_00=14 m40_00=15 m41_00=16 m45_00=17
             m50_00=20 m51_00=21 m51_10=22
Within a block: local = word*32 + (3 - byte_in_word)*8 + (7 - bit)
"""
import struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parser import bnd4, crypto

ROOT = Path(__file__).resolve().parent.parent.parent / "play_simulator_save_files"

ITEM_TYPE_WEAPON = 0x80000000
ITEM_TYPE_ARMOR  = 0x90000000

MAP_SLOTS = {
    0: "m30_00", 1: "m30_01", 2: "m31_00", 4: "m32_00", 6: "m33_00",
    8: "m34_01", 9: "m35_00", 12: "m37_00", 13: "m38_00", 14: "m39_00",
    15: "m40_00", 16: "m41_00", 17: "m45_00", 20: "m50_00", 21: "m51_00",
    22: "m51_10",
}
MAP_PREFIX = {  # AABB digits of the flag id
    "m30_00": 3000, "m30_01": 3010, "m31_00": 3100, "m32_00": 3200,
    "m33_00": 3300, "m34_01": 3410, "m35_00": 3500, "m37_00": 3700,
    "m38_00": 3800, "m39_00": 3900, "m40_00": 4000, "m41_00": 4100,
    "m45_00": 4500, "m50_00": 5000, "m51_00": 5100, "m51_10": 5110,
}
REGIONS = [  # (origin, type_digit)
    (0x00F00, 1),
    (0x1FE00, 6),
    (0x2A300, 7),
]
FLAG_SECTION_SIZE = 0x33E5E


def gaitem_end(data, start=0x70, slots=6144):
    off = start
    for _ in range(slots):
        handle = struct.unpack_from("<I", data, off)[0]
        off += 8
        if handle != 0 and (handle & 0xF0000000) in (ITEM_TYPE_WEAPON, ITEM_TYPE_ARMOR):
            off += 52
    return off


def event_flag_start(data):
    end_offset = gaitem_end(data)
    inventory_start = end_offset + 0x13F + 0x1DD
    above_storage_counter = inventory_start + 0x8808 + 0x11C
    above_storage_size = struct.unpack_from('<I', data, above_storage_counter)[0]
    table_1_end = above_storage_counter + 4 + above_storage_size * 8
    storage_box_start = table_1_end + 0x18C + 0x4
    gesture_end = storage_box_start + 0x8800 + 0xC + 0xA4
    table_2_size = struct.unpack_from('<I', data, gesture_end)[0]
    table_2_end = gesture_end + 4 + table_2_size * 4
    return table_2_end + 0x92 + 0xBCC


def load_slot(sl2, slot):
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    off, size = entries[slot]
    return b"\x00\x00\x0c\x00" + crypto.decrypt_entry(raw, off, size)


def flag_id_for(rel, bit):
    """rel = offset within blob. Returns semantic flag id or None."""
    block_base = (rel // 0x500) * 0x500
    within = rel - block_base
    word = within // 4
    byte_in_word = within % 4
    local = word * 32 + (3 - byte_in_word) * 8 + (7 - bit)
    if rel < 0xF00:
        # commons: continuous u32 model over whole region
        word = rel // 4
        byte_in_word = rel % 4
        return word * 32 + (3 - byte_in_word) * 8 + (7 - bit)
    for origin, tdigit in REGIONS:
        span = 23 * 0x500
        if origin <= rel < origin + span:
            slot = (block_base - origin) // 0x500
            name = MAP_SLOTS.get(slot)
            if name is None:
                return f"?type{tdigit}_slot{slot}_local{local}"
            return tdigit * 10_000_000 + MAP_PREFIX[name] * 1000 + local
    return f"?block0x{block_base:X}_local{local}"


def diff_pair(pa, pb, label):
    efs_a, efs_b = event_flag_start(pa), event_flag_start(pb)
    b0a, b0b = efs_a + 0x5D, efs_b + 0x5D
    print(f"\n=== {label}   (blob0 a=0x{b0a:X} b=0x{b0b:X})")
    sets, clrs = [], []
    for rel in range(FLAG_SECTION_SIZE - 0x5D):
        x, y = pa[b0a + rel], pb[b0b + rel]
        if x == y:
            continue
        for bit in range(8):
            old, new = (x >> bit) & 1, (y >> bit) & 1
            if old != new:
                fid = flag_id_for(rel, bit)
                (sets if new else clrs).append(fid)
    print(f"  SET:   {sets}")
    print(f"  CLEAR: {clrs}")
    return sets, clrs


if __name__ == "__main__":
    # quest-track corpus, slot 4 (char 'quest_track') — incl. 5 sigil draws
    qt = sorted((ROOT / "quest-track").glob("*.sl2"), key=lambda p: int(p.name.split("_")[0]))
    payloads = [load_slot(s, 4) for s in qt]
    for i in range(len(qt) - 1):
        diff_pair(payloads[i], payloads[i + 1],
                  f"qt {qt[i].name.split('_')[0]} -> {qt[i+1].name[:46]}")
