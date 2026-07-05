"""Investigate the event-flag directory + block structure.

1. Dump the (group_key, block_index) directory for given saves.
2. Diff the flag region between two saves of the same character and report
   changed bits as (raw_bit, block_index_under_hypothesis, group, bit_in_block)
   for several block-size hypotheses.
"""
import struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parser import bnd4, crypto, userdata as ud_mod
from parser.slots import _find_name_offset

_MIN = 20


def find_directory(payload: bytes):
    """Return (dir_start, entries[(key, idx)], blocks_start)."""
    for pos in range(0, len(payload) - 4 * _MIN, 4):
        k0, v0 = struct.unpack_from("<HH", payload, pos)
        if v0 != 0 or k0 == 0 or k0 > 0x4000:
            continue
        prev_k = k0
        ok = True
        for j in range(1, _MIN):
            k, v = struct.unpack_from("<HH", payload, pos + 4 * j)
            if v != j or k <= prev_k or k > 0x4000:
                ok = False
                break
            prev_k = k
        if not ok:
            continue
        entries = [(k0, 0)]
        j = 1
        prev_k = k0
        while pos + 4 * (j + 1) <= len(payload):
            k, v = struct.unpack_from("<HH", payload, pos + 4 * j)
            if v != j or k <= prev_k:
                break
            entries.append((k, v))
            prev_k = k
            j += 1
        return pos, entries, pos + 4 * j
    return None, None, None


def load_slot(sl2: Path, slot: int):
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    ud_payload = crypto.decrypt_entry(raw, *entries[ud_mod.USERDATA_ENTRY_INDEX])
    ud = ud_mod.parse_userdata(ud_payload)[slot]
    off, size = entries[slot]
    payload = crypto.decrypt_entry(raw, off, size)
    name_off = _find_name_offset(payload, ud.name or "")
    return payload, name_off, ud.name


def dump_dir(sl2: Path, slot: int):
    payload, name_off, name = load_slot(sl2, slot)
    ds, entries, bs = find_directory(payload)
    print(f"\n=== {sl2.name}  (slot {slot}, char {name!r}, name_off=0x{name_off:X})")
    if ds is None:
        print("  NO DIRECTORY FOUND")
        return None
    print(f"  dir_start=0x{ds:X}  blocks_start=0x{bs:X}  n_entries={len(entries)}")
    print(f"  rel to name_off: dir_start=name+0x{ds - name_off:X}" if name_off else "")
    keys = [k for k, _ in entries]
    print(f"  group keys: {keys}")
    return payload, ds, entries, bs


def diff_pair(sl2a: Path, sl2b: Path, slot: int, scan_bytes: int = 0x40000):
    pa, dsa, ea, bsa = dump_dir(sl2a, slot)
    pb, dsb, eb, bsb = dump_dir(sl2b, slot)
    print(f"\n--- diff {sl2a.name} -> {sl2b.name}")
    if ea != eb:
        sa, sb = set(ea), set(eb)
        print(f"  DIRECTORY CHANGED: added={sorted(sb - sa)} removed={sorted(sa - sb)}")
    else:
        print("  directory identical")
    n = min(len(pa) - bsa, len(pb) - bsb, scan_bytes)
    changed = []
    for i in range(n):
        x, y = pa[bsa + i], pb[bsb + i]
        if x != y:
            for bit in range(8):
                old = (x >> bit) & 1
                new = (y >> bit) & 1
                if old != new:
                    changed.append((i * 8 + bit, old, new))
    print(f"  changed bits in first 0x{n:X} bytes after blocks_start: {len(changed)}")
    for raw_bit, old, new in changed[:80]:
        byte_off = raw_bit // 8
        line = f"    raw_bit {raw_bit:>7} (byte 0x{byte_off:05X}+bit{raw_bit % 8}) {old}->{new}"
        # hypotheses: block sizes in bytes
        for bb in (125, 128, 1000, 1024):
            blk = byte_off // bb
            bit_in = raw_bit - blk * bb * 8
            # which group is at this block index (use 'after' dir)
            grp = None
            for k, v in eb:
                if v == blk:
                    grp = k
                    break
            if grp is not None:
                line += f" | bb={bb}: blk={blk} grp={grp} bit={bit_in} -> fid={grp * bb * 8 + bit_in}"
        print(line)
    if len(changed) > 80:
        print(f"    ... {len(changed) - 80} more")
    return changed


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent / "play_simulator_save_files"
    gq = root / "greirat-quest"
    qt = root / "quest-track"

    saves_gq = sorted(gq.glob("*.sl2"))
    saves_qt = sorted(qt.glob("*.sl2"))
    print("greirat-quest saves:", [s.name for s in saves_gq])
    print("quest-track saves:", [s.name for s in saves_qt])

    # The cleanest pair: 04 (bone in inventory) -> 05 (bone given), slot 5
    diff_pair(saves_gq[3], saves_gq[4], 5)
