"""Diff the event-flag bitfield between two saves, aligned RELATIVE to
flag_start (= name_offset + FLAG_OFFSET). Reports bits that turned 0->1.

This is immune to name_offset drift between saves. For each newly-set bit we
print the implied direct-index flag_id (rel_byte*8 + bit) so we can check it
against the wiki dictionary.

Usage:  ./venv/bin/python scripts/diff_flags.py <before.sl2> <after.sl2>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser import bnd4, crypto, userdata as ud_mod
from parser.slots import _find_name_offset

QA_SLOT = 4
FLAG_OFFSET = 0x11660
# How far past flag_start to scan. Slot payload is 0x C0000; flag_start lands
# around 0x2x000, so scan a generous window that stays in-bounds.
SCAN_LEN = 0x34000  # clean bitfield ends ~here; beyond is physics/hash noise

_DICT_PATH = Path(__file__).resolve().parent.parent / "data" / "_event_flags.json"


def load_dict():
    d = json.load(open(_DICT_PATH))
    flags = d.get("flags", d)
    out = {}
    if isinstance(flags, dict):
        for k, v in flags.items():
            try:
                out[int(k)] = (v.get("label") if isinstance(v, dict) else v)
            except ValueError:
                pass
    return out


def flag_blob(sl2: Path, idx: int = QA_SLOT):
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    ud_payload = crypto.decrypt_entry(raw, *entries[ud_mod.USERDATA_ENTRY_INDEX])
    ud = ud_mod.parse_userdata(ud_payload)[idx]
    off, size = entries[idx]
    payload = crypto.decrypt_entry(raw, off, size)
    name_off = _find_name_offset(payload, ud.name or "")
    start = name_off + FLAG_OFFSET
    end = min(start + SCAN_LEN, len(payload))
    return payload[start:end], name_off


def main():
    before, after = Path(sys.argv[1]), Path(sys.argv[2])
    b, name_b = flag_blob(before)
    a, name_a = flag_blob(after)
    names = load_dict()
    n = min(len(a), len(b))
    print(f"name_offset before=0x{name_b:X} after=0x{name_a:X} "
          f"({'SAME' if name_a == name_b else 'DIFFERS'})")
    print(f"scanning {n} bytes relative to flag_start\n")

    set_bits, cleared_bits = [], []
    for i in range(n):
        if a[i] == b[i]:
            continue
        for bit in range(8):
            ba = (a[i] >> bit) & 1
            bb = (b[i] >> bit) & 1
            if ba and not bb:
                set_bits.append(i * 8 + bit)
            elif bb and not ba:
                cleared_bits.append(i * 8 + bit)

    print(f"{len(set_bits)} bits set (0->1), {len(cleared_bits)} cleared (1->0)\n")
    print("--- newly SET (implied flag_id = rel_bit_index) ---")
    for fid in set_bits:
        label = names.get(fid, "")
        mark = "  <== IN DICT" if fid in names else ""
        print(f"  {fid:>10}  rel=0x{fid // 8:X} bit{fid % 8}  {label}{mark}")
    if len(set_bits) > 60:
        print(f"  ... ({len(set_bits)} total)")


if __name__ == "__main__":
    main()
