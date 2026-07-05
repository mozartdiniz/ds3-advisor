"""Hexdump the area around name_offset + 0x403F4 for multiple characters,
looking for a header / directory structure that explains the 4-byte drift.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parser import bnd4, crypto, userdata as ud_mod
from parser.slots import _find_name_offset

ROOT = Path(__file__).resolve().parent.parent.parent / "play_simulator_save_files"


def load_slot(sl2: Path, slot: int):
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    ud_payload = crypto.decrypt_entry(raw, *entries[ud_mod.USERDATA_ENTRY_INDEX])
    ud = ud_mod.parse_userdata(ud_payload)[slot]
    off, size = entries[slot]
    payload = crypto.decrypt_entry(raw, off, size)
    name_off = _find_name_offset(payload, ud.name or "")
    return payload, name_off, ud.name


def hexdump(data: bytes, start: int, length: int, base_label: str):
    for i in range(start, start + length, 16):
        chunk = data[i:i + 16]
        hexs = " ".join(f"{b:02X}" for b in chunk)
        print(f"  {base_label}+0x{i - start:04X} (abs 0x{i:06X}): {hexs}")


def probe(sl2: Path, slot: int, flag_rel: int):
    payload, name_off, name = load_slot(sl2, slot)
    print(f"\n=== {sl2.parent.name}/{sl2.name}  slot={slot} char={name!r} name_off=0x{name_off:X}")
    region = name_off + flag_rel
    print(f"  expected flag_start = name+0x{flag_rel:X} = 0x{region:X}")
    # dump 0x80 bytes before and 0x60 after the expected flag start
    hexdump(payload, region - 0x80, 0xE0, f"fs-0x80")
    return payload, name_off


if __name__ == "__main__":
    # Greirat char, slot 5: flag_rel believed 0x403F8
    probe(ROOT / "greirat-quest" / "05_-_Loretta Bone given.sl2", 5, 0x403F8)
    # QA char, slot 4 from play_00 (steps 35-37 had name_off 0x10AA0): flag_rel 0x403F4
    play00 = sorted((ROOT / "play_00").glob("*.sl2"))
    s37 = [p for p in play00 if p.name.startswith("37")]
    if s37:
        probe(s37[0], 4, 0x403F4)
    # quest-track char (auto slot?) — try same rel on a late save
    qt = sorted((ROOT / "quest-track").glob("*.sl2"))
    if qt:
        # find occupied slot by trying slots 0..9
        for s in range(10):
            try:
                payload, name_off, name = load_slot(qt[-1], s)
                if name and name_off:
                    print(f"\n[quest-track last save slot {s}: char {name!r}]")
            except Exception:
                pass
