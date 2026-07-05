"""play_simulator.py - replay a sequence of DS3 saves and print what changed.

Usage:
    python play_simulator.py play_00          # use play_simulator_save_files/play_00/
    python play_simulator.py play_01          # use play_simulator_save_files/play_01/
    python play_simulator.py play_00 --interval 2   # 2 seconds between steps
    python play_simulator.py play_00 --slot 4       # watch slot 4 (default: auto)
    python play_simulator.py play_03_auto --log     # write session log to the play folder

Each save in the folder is copied to sim_workspace/DS30000.sl2 in sequence,
then parsed. The diff since the previous save is printed - no LLM tokens used.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parser import bnd4, crypto, userdata as ud_mod
from parser.slots import load_slots
from parser.inventory import load_id_maps
from snapshot import SlotSnap, snap_slot, diff_events
from advisor import AdvisorSession

ROOT      = Path(__file__).resolve().parent.parent
SIM_SAVES = ROOT / "play_simulator_save_files"
WORKSPACE = Path(__file__).resolve().parent / "sim_workspace"
WORK_SAVE = WORKSPACE / "DS30000.sl2"
DATA_DIR  = Path(__file__).resolve().parent / "data"

SEP = "-" * 60


class _Tee:
    """Write to both terminal and a log file simultaneously."""
    def __init__(self, terminal, log_file):
        self._terminal = terminal
        self._log      = log_file

    def write(self, msg):
        self._terminal.write(msg)
        self._log.write(msg)

    def flush(self):
        self._terminal.flush()
        self._log.flush()

    def __getattr__(self, attr):
        return getattr(self._terminal, attr)


# ---------------------------------------------------------------------------
# Slot detection (snapshot/diff logic lives in snapshot.py)
# ---------------------------------------------------------------------------

def detect_active_slot(sl2: Path) -> int:
    """Return the slot most likely being played: shortest playtime among occupied slots.

    Shortest playtime = most recently started character = the one being recorded.
    Falls back to first occupied slot if playtime is unavailable.
    """
    raw = sl2.read_bytes()
    entries = bnd4.parse_entries(raw)
    ud_payload = crypto.decrypt_entry(raw, *entries[ud_mod.USERDATA_ENTRY_INDEX])
    ud_slots = ud_mod.parse_userdata(ud_payload)
    occupied = [(ud.playtime_seconds or 0, ud.index) for ud in ud_slots if ud.occupied and ud.name]
    if not occupied:
        return 0
    # Slot with minimum playtime is the freshest / most recently started character
    _, idx = min(occupied)
    return idx


def detect_changed_slot(sl2_prev: Path, sl2_curr: Path) -> Optional[int]:
    """Return the slot index whose playtime changed between two saves, or None."""
    id_maps = load_id_maps(DATA_DIR)
    prev_slots = load_slots(sl2_prev, id_maps=id_maps)
    curr_slots = load_slots(sl2_curr, id_maps=id_maps)
    for p, c in zip(prev_slots, curr_slots):
        if p.name and c.name and p.playtime_seconds != c.playtime_seconds:
            return p.index
    return None


# ---------------------------------------------------------------------------
# Diff + print
# ---------------------------------------------------------------------------

def print_diff(label: str, prev: Optional[SlotSnap], curr: SlotSnap) -> None:
    bonfire = curr.bonfire_name or ("bonfire#%s" % curr.bonfire_id)
    print()
    print(SEP)
    print("  %s" % label)
    print("  %s  |  Level %d  |  %s souls  |  %s" % (
        curr.name, curr.level, "{:,}".format(curr.souls), bonfire))
    print(SEP)

    events = diff_events(prev, curr)
    if events:
        for line in events:
            print("  %s" % line)
    else:
        print("  (no changes detected)")


def print_advisor(text: Optional[str]) -> None:
    if not text:
        return
    print()
    print("  --- ADVISOR " + "-" * 46)
    for line in text.splitlines():
        print("  %s" % line)
    print("  " + "-" * 58)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("play", help="folder under play_simulator_save_files/")
    ap.add_argument("--interval", type=float, default=3.0,
                    help="seconds between saves (default 3)")
    ap.add_argument("--slot", default="auto",
                    help="slot index 0-9, or 'auto' to detect (default auto)")
    ap.add_argument("--log", action="store_true",
                    help="write a session log file to the play folder")
    ap.add_argument("--llm", action="store_true",
                    help="phrase advisor output via Claude (costs tokens); "
                         "default is deterministic text")
    ap.add_argument("--no-advisor", action="store_true",
                    help="diff only, skip the advisor entirely")
    args = ap.parse_args()

    play_dir = SIM_SAVES / args.play
    if not play_dir.exists():
        print("ERROR: %s not found" % play_dir)
        sys.exit(1)

    saves = sorted(
        [f for f in play_dir.iterdir() if f.suffix == ".sl2"],
        key=lambda p: int(p.name.split("_")[0])
    )

    if not saves:
        print("No .sl2 files in %s" % play_dir)
        sys.exit(1)

    # Auto-folders written by --record watcher store the active slot in slot.txt
    slot_hint_file = play_dir / "slot.txt"
    if args.slot == "auto" and slot_hint_file.exists():
        try:
            hinted = int(slot_hint_file.read_text(encoding="utf-8").strip())
            args.slot = str(hinted)
        except (ValueError, OSError):
            pass

    WORKSPACE.mkdir(exist_ok=True)

    # Set up log file if requested
    _log_file = None
    log_path = None
    if args.log:
        session_ts = datetime.now().strftime("%Y%m%d%H%M")
        log_path = play_dir / ("session_replay_%s.log" % session_ts)
        _log_file = open(log_path, "w", encoding="utf-8", buffering=1)
        sys.stdout = _Tee(sys.__stdout__, _log_file)

    try:
        print()
        print("=" * 60)
        print("  DS3 Play Simulator - %s" % args.play)
        print("  %d saves  |  interval: %ss  |  slot: %s%s" % (
            len(saves), args.interval, args.slot,
            ("  |  log: %s" % log_path.name) if log_path else ""))
        print("=" * 60)

        # Determine slot once before the loop
        if args.slot.isdigit():
            slot_idx: int = int(args.slot)
            print("  [using slot %d]" % slot_idx)
        else:
            if len(saves) >= 2:
                changed = detect_changed_slot(saves[0], saves[1])
                if changed is not None:
                    slot_idx = changed
                    print("  [auto-detected slot %d (changed between saves 1 and 2)]" % slot_idx)
                else:
                    slot_idx = detect_active_slot(saves[0])
                    print("  [auto-detected slot %d (min playtime fallback)]" % slot_idx)
            else:
                slot_idx = detect_active_slot(saves[0])
                print("  [auto-detected slot %d]" % slot_idx)

        prev_snap: Optional[SlotSnap] = None
        advisor_session: Optional[AdvisorSession] = None
        if not args.no_advisor:
            # simulator memory is in-process only (persist=False) so replays
            # always start fresh
            advisor_session = AdvisorSession(
                "sim_%s" % args.play, use_llm=args.llm, persist=False)

        for i, src in enumerate(saves):
            stem = src.stem
            step_num = stem.split("_")[0]
            parts = stem.split("_")[1:]
            step_desc = " ".join(parts).replace("-", " ")

            shutil.copy2(src, WORK_SAVE)

            try:
                curr = snap_slot(WORK_SAVE, slot_idx)
            except Exception as e:
                print("\n  [Step %s] ERROR: %s" % (step_num, e))
                continue

            if curr is None:
                print("\n  [Step %s] Slot %d not occupied" % (step_num, slot_idx))
                continue

            label = "Step %s: %s" % (step_num, step_desc)
            print_diff(label, prev_snap, curr)

            if advisor_session is not None:
                advice = advisor_session.on_save_event(prev_snap, curr)
                print_advisor(advice)

            prev_snap = curr

            if i < len(saves) - 1:
                if args.interval > 0:
                    print("\n  [waiting %.1fs...]" % args.interval)
                    time.sleep(args.interval)

        print()
        print("=" * 60)
        print("  Done - %d saves processed" % len(saves))
        print("=" * 60)
        if log_path:
            print("  Log saved to: %s" % log_path)

    finally:
        if _log_file is not None:
            sys.stdout = sys.__stdout__
            _log_file.close()


if __name__ == "__main__":
    main()
