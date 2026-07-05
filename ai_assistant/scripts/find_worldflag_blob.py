"""Locate the in-memory-format world-flag blob inside the decrypted slot payload.

The TGA cheat table proves DS3 keeps world flags in one flat blob:
    byte = MAP_BASE[map] + local_id // 8     bit = 7 - local_id % 8
with MAP_BASE stride 0x500 (m30_00=0xF03, m40_00=0x5A03, ...).

If the save serializes that blob verbatim, a multi-point signature of flags we
KNOW are set/cleared in a given save will pin its start offset uniquely.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parser import bnd4, crypto, userdata as ud_mod

ROOT = Path(__file__).resolve().parent.parent.parent / "play_simulator_save_files"

# (blob_offset, bit, expected_value, label) for greirat-quest save 05
# bit uses CE convention: bit index within byte (MSB-first flag order already applied)
SIGNATURE = [
    (0x5A03, 7, 1, "Firelink Shrine bonfire lit (14000000)"),
    (0x5A03, 5, 1, "Iudex Gundyr bonfire lit (14000002)"),
    (0x5A0F, 2, 1, "Coiled Sword embedded (14000101)"),
    (0x5A67, 7, 1, "Iudex Gundyr defeated (14000800)"),
    (0x5A67, 6, 1, "Iudex encountered (14000801)"),
    (0x0F03, 7, 1, "High Wall warp enabled (13000000)"),
    (0x0F67, 7, 1, "Vordt defeated (13000800)"),
    (0x0F67, 6, 1, "Vordt encountered (13000801)"),
    # negatives — late-game content this character has not done
    (0x7D67, 7, 0, "Gael defeated (15110800)"),
    (0x5F67, 7, 0, "Soul of Cinder defeated (14100800)"),
    (0x6467, 7, 0, "Friede defeated (14500800)"),
    (0x5A03, 4, 0, "Untended Graves bonfire (14000003)"),
    (0x5A03, 3, 0, "Champion Gundyr bonfire (14000004)"),
]

MAX_OFF = 0x26000  # blob is at least this big (max known CT offset 0x2534D)


def load_slot(sl2: Path, slot: int):
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    off, size = entries[slot]
    return crypto.decrypt_entry(raw, off, size)


def find_blob(payload: bytes, signature):
    hits = []
    limit = len(payload) - MAX_OFF
    for s in range(0, limit):
        ok = True
        for off, bit, want, _ in signature:
            if (payload[s + off] >> bit) & 1 != want:
                ok = False
                break
        if ok:
            hits.append(s)
    return hits


if __name__ == "__main__":
    sl2 = ROOT / "greirat-quest" / "05_-_Loretta Bone given.sl2"
    payload = load_slot(sl2, 5)
    print(f"payload size: {len(payload):#x}")
    hits = find_blob(payload, SIGNATURE)
    print(f"candidate blob starts: {[hex(h) for h in hits]}")

    for s in hits:
        print(f"\n=== verifying candidate S=0x{s:X}")
        for off, bit, want, label in SIGNATURE:
            got = (payload[s + off] >> bit) & 1
            mark = "OK " if got == want else "BAD"
            print(f"  {mark} {label}: want {want} got {got}")
