"""Clean same-name_offset diff to find the event-flag bitfield.

Previous findings:
  - 0x8B00-0x8E00 relative: ITEM DATA (goods IDs, face data) — NOT flags
  - 0x11660 relative: growing sorted index — NOT flags
  - Known flag IDs (6104 etc.) don't appear as raw u32 values in the save
  → Flags must be a flat bitfield at a position that is ABSOLUTE or
    at a fixed offset from something other than name_offset.

Strategy:
  Saves 06 and 07 have IDENTICAL name_offset (0x10488). Only event between
  them is "Talk to Hawkwood." Diff in the ENTIRE clean region (abs 0xD000-
  0x73000) — since name_offset is the same, absolute positions are stable.
  This gives the cleanest possible diff: only Hawkwood NPC flags can change.

  If the bitfield is at a fixed ABSOLUTE position, the Hawkwood flags will
  appear as isolated 0->1 bits at stable absolute positions.

  Then test: is there a flag_start such that the changed bits fit the flat
  bitfield formula (flag_id = (abs - flag_start)*8 + bit)?

Run from ai_assistant/:
    python scripts/find_flag_start.py
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser import bnd4, crypto, userdata as ud_mod
from parser.slots import _find_name_offset

SAVE_DIR = Path(__file__).resolve().parent.parent.parent / "save_files"
QA_SLOT  = 4

# Absolute clean region boundaries (same for all saves)
ABS_CLEAN_START = 0x0D000
ABS_CLEAN_END   = 0x73000

FLAG_DICT_PATH = Path(__file__).resolve().parent.parent / "data" / "_event_flags.json"

import json
def load_flag_dict() -> dict[int, str]:
    raw = json.load(open(FLAG_DICT_PATH, encoding="utf-8"))
    flags = raw.get("flags", raw)
    out: dict[int, str] = {}
    for k, v in flags.items():
        try:
            label = v.get("label") if isinstance(v, dict) else str(v)
            out[int(k)] = label
        except (ValueError, AttributeError):
            pass
    return out


def load_slot(sl2: Path, slot_idx: int = QA_SLOT):
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    ud_payload = crypto.decrypt_entry(raw, *entries[ud_mod.USERDATA_ENTRY_INDEX])
    ud = ud_mod.parse_userdata(ud_payload)[slot_idx]
    off, size = entries[slot_idx]
    payload = crypto.decrypt_entry(raw, off, size)
    name_off = _find_name_offset(payload, ud.name or "")
    return payload, name_off


def find_save(step: int) -> Path:
    saves = sorted(SAVE_DIR.glob("[0-9][0-9]_*.sl2"))
    matches = [s for s in saves if s.name.startswith(f"{step:02d}_")]
    if not matches:
        raise FileNotFoundError(f"No save for step {step:02d}")
    return matches[0]


def abs_diff_bits(payload_a: bytes, payload_b: bytes, start: int, end: int):
    """Return 0->1 and 1->0 changes in abs range [start, end)."""
    set_bits, clr_bits = [], []
    for i in range(start, min(end, len(payload_a), len(payload_b))):
        ba, bb = payload_a[i], payload_b[i]
        if ba == bb:
            continue
        for bit in range(8):
            a_val = (ba >> bit) & 1
            b_val = (bb >> bit) & 1
            if b_val and not a_val:
                set_bits.append((i, bit))
            elif a_val and not b_val:
                clr_bits.append((i, bit))
    return set_bits, clr_bits


def hexdump_region(payload: bytes, start: int, end: int) -> str:
    chunk = payload[start:end]
    parts = []
    for i in range(0, len(chunk), 16):
        row = chunk[i:i+16]
        hex_part = " ".join(f"{b:02X}" for b in row)
        parts.append(f"  0x{start+i:06X}: {hex_part}")
    return "\n".join(parts)


def main():
    flag_dict = load_flag_dict()
    saves_all = sorted(SAVE_DIR.glob("[0-9][0-9]_*.sl2"))
    n_saves = len(saves_all)
    payloads, name_offsets = [], []
    for sv in saves_all:
        p, no = load_slot(sv)
        payloads.append(p)
        name_offsets.append(no)

    # ------------------------------------------------------------------ #
    # 0. Show all saves grouped by name_offset to pick clean pairs
    # ------------------------------------------------------------------ #
    print("=== name_offset groups ===\n")
    from collections import defaultdict
    groups: dict[int, list[int]] = defaultdict(list)
    for i, no in enumerate(name_offsets):
        groups[no].append(i+1)
    for no, steps in sorted(groups.items()):
        if len(steps) > 1:
            print(f"  name_off=0x{no:X}: steps {steps}  <- SAME - valid for absolute diff")
    print()

    # ------------------------------------------------------------------ #
    # 1. Clean diff: saves 06 vs 07  (same name_off=0x10488, Talk to Hawkwood)
    # ------------------------------------------------------------------ #
    p06, no06 = payloads[5], name_offsets[5]
    p07, no07 = payloads[6], name_offsets[6]
    print(f"=== Clean diff: save 06 vs 07 (same name_off=0x{no06:X}) ===\n")
    assert no06 == no07, f"name_offsets differ: {no06:X} vs {no07:X}"

    set07, clr07 = abs_diff_bits(p06, p07, ABS_CLEAN_START, ABS_CLEAN_END)
    print(f"  0->1 bits: {len(set07)}    1->0 bits: {len(clr07)}\n")

    if len(set07) <= 50:
        print("  Set bits (absolute pos, bit):")
        for abs_pos, bit in set07:
            print(f"    abs=0x{abs_pos:06X}  rel_to_name=0x{abs_pos-no06:05X}  bit{bit}")
        print()
    else:
        print(f"  Too many ({len(set07)}) — showing first 30:")
        for abs_pos, bit in set07[:30]:
            print(f"    abs=0x{abs_pos:06X}  rel_to_name=0x{abs_pos-no06:05X}  bit{bit}")
        print()

    # ------------------------------------------------------------------ #
    # 2. Clean diff: saves 08 vs 09  (same name_off=0x107FC, Talk to Handmaid)
    # ------------------------------------------------------------------ #
    p08, no08 = payloads[7], name_offsets[7]
    p09, no09 = payloads[8], name_offsets[8]
    print(f"=== Clean diff: save 08 vs 09 (same name_off=0x{no08:X}) ===\n")

    set09, clr09 = abs_diff_bits(p08, p09, ABS_CLEAN_START, ABS_CLEAN_END)
    print(f"  0->1 bits: {len(set09)}    1->0 bits: {len(clr09)}\n")

    if len(set09) <= 50:
        print("  Set bits:")
        for abs_pos, bit in set09:
            print(f"    abs=0x{abs_pos:06X}  rel_to_name=0x{abs_pos-no08:05X}  bit{bit}")
        print()
    else:
        print(f"  Too many ({len(set09)}) — showing first 30:")
        for abs_pos, bit in set09[:30]:
            print(f"    abs=0x{abs_pos:06X}  rel_to_name=0x{abs_pos-no08:05X}  bit{bit}")
        print()

    # ------------------------------------------------------------------ #
    # 3. Clean diff: saves 01 vs 02 (same name_off=0x10454, Ashen Estus loot)
    #    Then 01 vs 04 (same name_off=0x10454, everything through Iudex kill)
    # ------------------------------------------------------------------ #
    p01, no01 = payloads[0], name_offsets[0]
    p02, no02 = payloads[1], name_offsets[1]
    p04, no04 = payloads[3], name_offsets[3]

    print(f"=== Clean diff: save 01 vs 02 (same name_off=0x{no01:X}) ===\n")
    set02, clr02 = abs_diff_bits(p01, p02, ABS_CLEAN_START, ABS_CLEAN_END)
    print(f"  0->1 bits: {len(set02)}    1->0 bits: {len(clr02)}")
    if len(set02) <= 50:
        for abs_pos, bit in set02:
            print(f"    abs=0x{abs_pos:06X}  bit{bit}")
    print()

    print(f"=== Clean diff: save 01 vs 04 (same name_off=0x{no01:X}, Iudex killed) ===\n")
    set04, clr04 = abs_diff_bits(p01, p04, ABS_CLEAN_START, ABS_CLEAN_END)
    print(f"  0->1 bits: {len(set04)}    1->0 bits: {len(clr04)}\n")
    if len(set04) <= 200:
        for abs_pos, bit in set04:
            print(f"    abs=0x{abs_pos:06X}  bit{bit}")
    print()

    # ------------------------------------------------------------------ #
    # 4. Bits unique to 01->04 (not in 01->02) = Iudex + bonfire flags only
    # ------------------------------------------------------------------ #
    set04_unique = [x for x in set04 if x not in set(set02)]
    print(f"  Bits set in 01->04 but NOT in 01->02 (Iudex-specific + bonfires): {len(set04_unique)}")
    for abs_pos, bit in set04_unique:
        print(f"    abs=0x{abs_pos:06X}  bit{bit}")
    print()

    # ------------------------------------------------------------------ #
    # 5. For each set bit in 01->04, test if it could be a known flag
    #    by computing implied flag_id for various candidate flag_start values
    # ------------------------------------------------------------------ #
    print("=== Testing: do any 01->04 bits correspond to flag 6104 at a consistent flag_start? ===\n")

    # Iudex flag 6104: byte offset = 763, bit = 0
    # If a bit at (abs_pos, bit0), flag_start = abs_pos - 763
    bit0_changes = [(abs_pos, bit) for abs_pos, bit in set04 if bit == 0]
    print(f"  Changes with bit=0 in 01->04: {len(bit0_changes)}")
    print(f"  Implied flag_start candidates (abs_pos - 763):")
    for abs_pos, bit in bit0_changes[:20]:
        fsr = abs_pos - 763
        print(f"    abs=0x{abs_pos:06X}  =>  flag_start=0x{fsr:X} ({fsr})")

    # Check: does any candidate flag_start from the 01->04 diff
    # also correctly predict flag 6105 (Vordt) in a future diff?
    # We can check if bit1 at the same absolute position turns on
    # between steps 01-04 and stays on (which would be wrong — Vordt is later)
    # OR if bit1 at that abs_pos is still 0 in save 04 (correct)
    if bit0_changes:
        abs_candidate = bit0_changes[0][0]
        bit1_in_04 = (p04[abs_candidate] >> 1) & 1
        print(f"\n  At abs=0x{abs_candidate:06X}: bit1 in save 04 = {bit1_in_04}  (should be 0 if Vordt not yet killed)")
        # And in save 16 (Vordt killed):
        if len(payloads) >= 16:
            no16 = name_offsets[15]
            bit1_in_16 = (payloads[15][abs_candidate] >> 1) & 1
            print(f"  At abs=0x{abs_candidate:06X}: bit1 in save 16 = {bit1_in_16}  (should be 1 if Vordt killed, abs flag_start model)")

    # ------------------------------------------------------------------ #
    # 6. Dump 64 bytes around the top set-bit candidates in 01->04
    # ------------------------------------------------------------------ #
    print("\n=== Raw bytes around top candidates in 01->04 (saves 01 and 04) ===\n")
    for abs_pos, bit in set04[:6]:
        print(f"abs=0x{abs_pos:06X} bit{bit}:")
        w = 16
        s = max(ABS_CLEAN_START, abs_pos - w)
        e = min(ABS_CLEAN_END, abs_pos + w)
        print(f"  save 01: {hexdump_region(p01, s, e)}")
        print(f"  save 04: {hexdump_region(p04, s, e)}")
        print()


if __name__ == "__main__":
    main()
