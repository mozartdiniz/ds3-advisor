"""Port of alfizari's parse_save() slot-payload walk + event-flag verification.

Structure (from alfizari/Dark-Souls-3-Save-Editor-PS4-PC, GPL-3):
  0x70: gaitem registry, 6144 entries (8 bytes; +52 for weapon/armor)
  -> chain of fixed offsets + counted tables -> event_flag_start
  Event-flag section: fixed 0x33E5E bytes.
  In-memory world-flag blob origin = event_flag_start + 0x5D
  (alfizari base = efs-0x12; CT offset + 0x6F = alfizari distance)

In-memory flag model (from TGA cheat table):
  byte = MAP_BASE[map] + (local//32)*4 + 3 - ((local%32)//8)
  bit  = 7 - local%8                       (u32 LE words, MSB-first bits)
"""
import struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parser import bnd4, crypto, userdata as ud_mod

ROOT = Path(__file__).resolve().parent.parent.parent / "play_simulator_save_files"

ITEM_TYPE_WEAPON = 0x80000000
ITEM_TYPE_ARMOR  = 0x90000000


def gaitem_end(data: bytes, start: int = 0x70, slots: int = 6144) -> int:
    off = start
    for _ in range(slots):
        handle = struct.unpack_from("<I", data, off)[0]
        off += 8
        if handle != 0 and (handle & 0xF0000000) in (ITEM_TYPE_WEAPON, ITEM_TYPE_ARMOR):
            off += 52
    return off


def parse_save(data: bytes) -> dict:
    end_offset = gaitem_end(data)
    magic_start           = end_offset + 0x13F
    inventory_start       = magic_start + 0x1DD
    inventory_end         = inventory_start + 0x8808
    above_storage_counter = inventory_end + 0x11C
    above_storage_size    = struct.unpack_from('<I', data, above_storage_counter)[0]
    table_1_end           = above_storage_counter + 4 + above_storage_size * 8
    face_data_maybe       = table_1_end + 0x18C
    storage_box_start     = face_data_maybe + 0x4
    storage_box_end       = storage_box_start + 0x8800
    gesture_start         = storage_box_end + 0xC
    gesture_end           = gesture_start + 0xA4
    table_2_size          = struct.unpack_from('<I', data, gesture_end)[0]
    table_2_end           = gesture_end + 4 + table_2_size * 4
    new_game_plus         = table_2_end + 0x92
    event_flag_start      = new_game_plus + 0xBCC
    return {
        "gaitem_end": end_offset,
        "new_game_plus": new_game_plus,
        "event_flag_start": event_flag_start,
        "blob0": event_flag_start + 0x5D,   # in-memory world-flag blob origin
    }


# Map base table (in-memory offsets, from TGA CT world-flag entries)
MAP_BASE = {
    "m30_00": 0x0F00, "m30_01": 0x1400, "m31_00": 0x1900, "m32_00": 0x2300,
    "m33_00": 0x2D00, "m34_01": 0x3700, "m35_00": 0x3C00, "m37_00": 0x4B00,
    "m38_00": 0x5000, "m39_00": 0x5500, "m40_00": 0x5A00, "m41_00": 0x5F00,
    "m45_00": 0x6400, "m50_00": 0x7300, "m51_00": 0x7800, "m51_10": 0x7D00,
}

def mem_off(map_name: str, local: int):
    base = MAP_BASE[map_name]
    return base + (local // 32) * 4 + 3 - ((local % 32) // 8), 7 - local % 8


def read_flag(data, blob0, map_name, local):
    off, bit = mem_off(map_name, local)
    return (data[blob0 + off] >> bit) & 1


def load_slot(sl2: Path, slot: int):
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    off, size = entries[slot]
    payload = crypto.decrypt_entry(raw, off, size)
    # alfizari offsets assume the 4-byte length prefix is still present
    return b"\x00\x00\x0c\x00" + payload


def decode_pos(blob0, abs_pos, bits):
    """Decode absolute payload byte+bits into candidate flag locals per map block."""
    rel = abs_pos - blob0
    out = []
    block_base = (rel // 0x500) * 0x500
    within = rel - block_base
    word = within // 4
    byte_in_word = within % 4
    for b in bits:
        local = word * 32 + (3 - byte_in_word) * 8 + (7 - b)
        out.append((block_base, local))
    return out


if __name__ == "__main__":
    gq = sorted((ROOT / "greirat-quest").glob("*.sl2"))
    for s in gq:
        p = load_slot(s, 5)
        info = parse_save(p)
        b0 = info["blob0"]
        print(f"\n{s.name}")
        print(f"  gaitem_end=0x{info['gaitem_end']:X} efs=0x{info['event_flag_start']:X} blob0=0x{b0:X}")
        checks = [
            ("m40_00", 0,   "Firelink bonfire lit (14000000)"),
            ("m40_00", 101, "Coiled Sword embedded (14000101)"),
            ("m40_00", 800, "Iudex defeated (14000800)"),
            ("m30_00", 0,   "High Wall warp (13000000)"),
            ("m30_00", 800, "Vordt defeated (13000800)"),
            ("m31_00", 800, "Greatwood defeated (13100800)"),
            ("m51_10", 800, "Gael defeated (15110800)"),
        ]
        for m, l, lbl in checks:
            print(f"    {lbl}: {read_flag(p, b0, m, l)}")

    # decode the bone-given diff (save 04 -> 05): bytes 0x53099 (set bit6, clr bit3), 0x530B1 (set bits 2,3)
    p5 = load_slot(gq[4], 5)
    b0 = parse_save(p5)["blob0"]
    print("\nDecoding bone-given diff positions:")
    # +4: diff positions were measured on the unprefixed payload
    for pos, bits, what in [(0x53099 + 4, [6], "set"), (0x53099 + 4, [3], "clr"),
                            (0x530B1 + 4, [2, 3], "set")]:
        for block_base, local in decode_pos(b0, pos, bits):
            rev = {v: k for k, v in MAP_BASE.items()}
            mname = rev.get(block_base, f"block@0x{block_base:X}")
            print(f"  0x{pos:05X} {what}: {mname} local {local}  (rel=0x{pos - b0:X})")
