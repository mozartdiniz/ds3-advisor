"""Empirically derive an (flag_id -> event) table from the QA save corpus.

The save filenames are ground truth ("33_Defeat_the_Curse-Rotted_Greatwood").
We read the flag bitfield (direct-index: bit flag_id at flag_start+id//8, bit
id%8) for every save in order, then keep only bits that are STRICTLY MONOTONIC
across the whole sequence: 0...0 1...1 (turn on exactly once, never turn off).
Each such bit is labelled by the save where it first turned on.

Volatile regions (low IDs, NPC-log buffer) fail the monotonic test and drop out
automatically. What remains are persistent progression flags.

Run from ai_assistant/:  ./venv/bin/python scripts/find_monotonic_flags.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.verify_flag_formula import slot_payload, FLAG_OFFSET, QA_SLOT, SAVE_DIR

CLEAN_START_BIT = 0x400 * 8     # skip the volatile low region
CLEAN_END_BIT = 0x34000 * 8     # bitfield ends before the physics/hash noise
# The NPC-interaction log is a circular buffer, not stable storage.
NPC_LOG_LO, NPC_LOG_HI = 0x2E000 * 8, 0x30000 * 8


def bit_at(payload, flag_start, idx):
    byte = flag_start + idx // 8
    if byte >= len(payload):
        return 0
    return (payload[byte] >> (idx % 8)) & 1


def main():
    saves = sorted(SAVE_DIR.glob("[0-9][0-9]_*.sl2"))
    labels = [s.name[3:-4].replace("_", " ") for s in saves]
    n = len(saves)
    print(f"{n} saves\n")

    # Load each save's clean-region flag bytes, relative to its own flag_start.
    blobs = []
    for sv in saves:
        payload, name_off, _ = slot_payload(sv, QA_SLOT)
        start = name_off + FLAG_OFFSET
        blobs.append(payload[start:start + 0x34000])

    min_len = min(len(b) for b in blobs)
    # For each candidate bit, build its on/off vector and test monotonicity.
    by_step = {}  # step_index -> list of flag_ids that first turn on there
    for idx in range(CLEAN_START_BIT, min(CLEAN_END_BIT, min_len * 8)):
        if NPC_LOG_LO <= idx < NPC_LOG_HI:
            continue
        byte_i, bit_i = idx // 8, idx % 8
        vec = [(blobs[s][byte_i] >> bit_i) & 1 for s in range(n)]
        if vec[0] == 1 or vec[-1] == 0:
            continue  # must start off and end on
        # strictly monotonic: once 1, always 1
        first_on = vec.index(1)
        if any(v == 0 for v in vec[first_on:]):
            continue
        by_step.setdefault(first_on, []).append(idx)

    total = sum(len(v) for v in by_step.values())
    print(f"{total} strictly-monotonic flags found\n")
    for step in sorted(by_step):
        ids = by_step[step]
        print(f"step {step+1:>2} — {labels[step]}")
        print(f"   {len(ids)} new flag(s): {', '.join(str(i) for i in ids[:20])}"
              + (" ..." if len(ids) > 20 else ""))


if __name__ == "__main__":
    main()
