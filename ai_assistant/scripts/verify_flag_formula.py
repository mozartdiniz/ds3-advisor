"""Verify the event-flag formula: flag_id is a direct bit index into a
bitfield starting at name_offset + FLAG_OFFSET in the slot payload.

bit(flag_id) lives at byte  flag_start + flag_id // 8,  bit  flag_id % 8.

Run from ai_assistant/:  ./venv/bin/python scripts/verify_flag_formula.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser import bnd4, crypto, userdata as ud_mod
from parser.slots import _find_name_offset

SAVE_DIR = Path(__file__).resolve().parent.parent.parent / "save_files"
QA_SLOT = 4
FLAG_OFFSET = 0x11660

# Confirmed-from-prior-session flag IDs and the save step they should turn on at.
CONFIRMED = {
    29064:   "Loretta's Bone given to Greirat (step 36)",
    34127:   "Greirat sent to scavenge (step 37)",
    34085:   "Dark Sigil from Yoel (step 40)",
    1564013: "Irina first talked to in Firelink (step 39)",
}


def slot_payload(sl2: Path, idx: int):
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    ud_payload = crypto.decrypt_entry(raw, *entries[ud_mod.USERDATA_ENTRY_INDEX])
    ud_slots = ud_mod.parse_userdata(ud_payload)
    ud = ud_slots[idx]
    off, size = entries[idx]
    payload = crypto.decrypt_entry(raw, off, size)
    name_off = _find_name_offset(payload, ud.name or "")
    return payload, name_off, ud.name


def get_bit(payload: bytes, flag_start: int, flag_id: int) -> int:
    byte_pos = flag_start + flag_id // 8
    if byte_pos >= len(payload):
        return -1
    return (payload[byte_pos] >> (flag_id % 8)) & 1


def main():
    saves = sorted(SAVE_DIR.glob("[0-9][0-9]_*.sl2"))
    print(f"{len(saves)} saves found\n")

    # Print the on/off timeline for each confirmed flag across all saves.
    for flag_id, label in CONFIRMED.items():
        timeline = []
        for sv in saves:
            payload, name_off, _ = slot_payload(sv, QA_SLOT)
            if name_off is None:
                timeline.append("?")
                continue
            bit = get_bit(payload, name_off + FLAG_OFFSET, flag_id)
            step = sv.name[:2]
            timeline.append(f"{step}:{bit}")
        print(f"flag {flag_id:>8}  {label}")
        print("   " + " ".join(timeline) + "\n")


if __name__ == "__main__":
    main()
