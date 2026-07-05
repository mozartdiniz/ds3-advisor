"""Validate KNOWN_FLAGS against the play_00 40-save QA corpus (slot 4).

For every flag in KNOWN_FLAGS, print the first save step where it reads 1,
flag monotonicity violations (1 -> 0 transitions), and check the expected
milestone steps.

Run from ai_assistant/:
    python scripts/validate_flags_qa.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parser import bnd4, crypto
from parser.flags import KNOWN_FLAGS, find_flag_blob, read_flag

ROOT = Path(__file__).resolve().parent.parent.parent / "play_simulator_save_files"
SLOT = 4

EXPECTED = {
    14000800: 4,    # Iudex defeated
    13000800: 16,   # Vordt defeated
    13100800: 33,   # Greatwood defeated
    74000300: 36,   # bone given
    74000301: 36,
    74000302: 37,   # greirat sent
    74000303: 37,
    73100100: 31,   # talked to Irina (sewer)
    73100150: 19,   # talked to Yoel (dying pilgrims) — QA step 19
    73100300: 28,   # talked to Eygon
    74000350: 39,   # talked to Irina at Firelink
    74000400: 40,   # Yoel: Dark Sigil drawn
    73100363: 27,   # Siegward post-Fire-Demon talk
    73100400: 32,   # talked to Hodrick
    74000850: 35,   # talked to Leonhard
    74000450: 38,   # talked to Cornyx at Firelink
    63000156: 14,   # Greirat freed from cell
    1225: 14,       # Greirat recruited
    1226: 38,       # Greirat away scavenging (state advances on reload after send)
}
NEVER = [fid for fid in KNOWN_FLAGS if fid not in EXPECTED]

# NPC state-machine flags clear when the state advances (1225 -> 1226 etc.) —
# monotonicity is not expected for them.
STATE_FLAGS = {1225, 1226}


def load_slot(sl2, slot):
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    off, size = entries[slot]
    return crypto.decrypt_entry(raw, off, size)


def main():
    saves = sorted((ROOT / "play_00").glob("*.sl2"),
                   key=lambda p: int(p.name.split("_")[0]))
    timeline = {fid: [] for fid in KNOWN_FLAGS}
    steps = []
    for s in saves:
        step = int(s.name.split("_")[0])
        steps.append(step)
        payload = load_slot(s, SLOT)
        blob = find_flag_blob(payload)
        if blob is None:
            print(f"step {step}: WALK FAILED")
            continue
        for fid in KNOWN_FLAGS:
            timeline[fid].append(read_flag(payload, blob, fid) or 0)

    failures = 0
    print(f"{'flag':>10}  {'label':<55} first_on  monotonic")
    for fid, vals in sorted(timeline.items()):
        first_on = next((steps[i] for i, v in enumerate(vals) if v), None)
        mono = all(a <= b for a, b in zip(vals, vals[1:]))
        label = KNOWN_FLAGS[fid][:53]
        exp = EXPECTED.get(fid)
        status = ""
        if exp is not None:
            ok = first_on == exp and (mono or fid in STATE_FLAGS)
            status = "OK" if ok else f"FAIL (expected first_on={exp})"
            failures += 0 if ok else 1
        elif fid in NEVER:
            ok = first_on is None
            status = "OK (never)" if ok else f"FAIL (fired at {first_on}, expected never)"
            failures += 0 if ok else 1
        print(f"{fid:>10}  {label:<55} {str(first_on):>8}  {str(mono):<5} {status}")

    print(f"\n{failures} failures across {len(KNOWN_FLAGS)} flags x {len(saves)} saves")


if __name__ == "__main__":
    main()
