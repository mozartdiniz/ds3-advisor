"""Step 3: locate the start of the inventory grid by walking 16-byte-aligned
records and finding the first long contiguous run whose +4 field is a known
item ID. Then dump the first ~20 records with names."""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parser import slots  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"
SAVE = Path(__file__).resolve().parents[2] / "DS30000.sl2"

RECORD_SIZE = 16
ID_OFFSET = 4


def parse_hex_bytes(s: str) -> bytes:
    return bytes(int(b, 16) for b in s.split())


def load_all_ids() -> dict[bytes, tuple[str, str]]:
    ids: dict[bytes, tuple[str, str]] = {}
    for category, fname in [
        ("weapon", "_weapons.json"),
        ("armor",  "_armor.json"),
        ("ring",   "_ring.json"),
        ("good",   "_goods_magic.json"),
    ]:
        d = json.loads((DATA / fname).read_text())
        for name, hex_str in d.items():
            ids[parse_hex_bytes(hex_str)] = (category, name)
    return ids


def main() -> None:
    summaries = slots.load_slots(SAVE)
    pl = summaries[9].payload
    ids = load_all_ids()

    # Walk every 16-byte-aligned record in the slot. Mark records whose +4 is
    # a known item ID. Find the longest run of consecutive marked records —
    # that's the inventory grid.
    n_records = (len(pl) - ID_OFFSET) // RECORD_SIZE
    marked = bytearray(n_records)
    for i in range(n_records):
        off = i * RECORD_SIZE + ID_OFFSET
        if pl[off : off + 4] in ids:
            marked[i] = 1

    # Longest run with at most a small gap (item slots may be sparse).
    best_start = best_end = best_density = 0
    run_start = None
    run_count = 0
    GAP_ALLOWED = 4
    consecutive_gap = 0
    for i, m in enumerate(marked):
        if m:
            if run_start is None:
                run_start = i
            run_count += 1
            consecutive_gap = 0
        else:
            if run_start is not None:
                consecutive_gap += 1
                if consecutive_gap > GAP_ALLOWED:
                    density = run_count
                    if density > best_density:
                        best_density = density
                        best_start = run_start
                        best_end = i - consecutive_gap
                    run_start = None
                    run_count = 0
                    consecutive_gap = 0
    if run_start is not None and run_count > best_density:
        best_start = run_start
        best_end = n_records - consecutive_gap
        best_density = run_count

    print(f"longest run: {best_density:,} marked records "
          f"between record #{best_start:,} and #{best_end:,}")
    grid_start_off = best_start * RECORD_SIZE
    grid_end_off = best_end * RECORD_SIZE
    print(f"  byte range: 0x{grid_start_off:06X} - 0x{grid_end_off:06X}  "
          f"({grid_end_off - grid_start_off:,} bytes, "
          f"{(grid_end_off - grid_start_off)//RECORD_SIZE:,} 16-byte records)")

    # Dump first 25 records of the grid.
    print(f"\n--- first 25 records of inventory grid at 0x{grid_start_off:06X} ---")
    for k in range(25):
        off = grid_start_off + k * RECORD_SIZE
        rec = pl[off : off + RECORD_SIZE]
        u32s = struct.unpack("<IIII", rec)
        id_bytes = rec[4:8]
        named = ids.get(id_bytes, ("?", "?"))
        hex_part = " ".join(f"{b:02x}" for b in rec)
        print(f"  0x{off:06X}  {hex_part}  "
              f"u32: ({u32s[0]:>10}, {u32s[1]:>10}, {u32s[2]:>10}, {u32s[3]:>10})  "
              f"[{named[0]:<6} {named[1]}]")

    # Also count, by category, how many DISTINCT named items are present in the
    # grid range — quick sanity vs. the "all items obtained" save description.
    seen: dict[str, set[str]] = {"weapon": set(), "armor": set(), "ring": set(), "good": set()}
    off = grid_start_off
    while off + RECORD_SIZE <= grid_end_off:
        id_bytes = pl[off + ID_OFFSET : off + ID_OFFSET + 4]
        named = ids.get(id_bytes)
        if named:
            seen[named[0]].add(named[1])
        off += RECORD_SIZE
    print(f"\n--- distinct named items inside grid range ---")
    for cat in ("weapon", "armor", "ring", "good"):
        print(f"  {cat:<6}  {len(seen[cat]):>4}")


if __name__ == "__main__":
    main()
