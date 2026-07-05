"""watcher.py - live DS3 save watcher.

Monitors the game save file and runs the advisor pipeline every time DS3
writes a new save (bonfire rest, quit to menu, death).

Configuration (environment variables):
    DS3_SAVE_PATH   Path to the DS3 save folder containing DS30000.sl2
                    Default: C:\\Users\\user\\AppData\\Roaming\\DarkSoulsIII\\011000016f3aa67c

    DS3_SLOT        Character slot to watch (0-9). Default: auto (detect by playtime change)
    DS3_POLL        Poll interval in seconds. Default: 1.0
    DS3_SETTLE      Seconds to wait after a change before reading. Default: 2.0

Usage:
    python watcher.py
    DS3_SAVE_PATH=C:\\path\\to\\save python watcher.py
    DS3_SLOT=4 python watcher.py
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Flush stdout immediately so output appears in real time; UTF-8 so quest
# text (em-dashes etc.) survives the Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")


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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from snapshot import (SlotSnap, snap_slot, get_all_playtimes,
                      detect_changed_slot, diff_events)
from advisor import AdvisorSession

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_SAVE_PATH = r"C:\Users\user\AppData\Roaming\DarkSoulsIII\011000016f3aa67c"

SAVE_DIR    = Path(os.environ.get("DS3_SAVE_PATH", DEFAULT_SAVE_PATH))
SAVE_FILE   = SAVE_DIR / "DS30000.sl2"
DATA_DIR    = Path(__file__).resolve().parent / "data"
WORKSPACE   = Path(__file__).resolve().parent / "sim_workspace"
WORK_SAVE   = WORKSPACE / "DS30000.sl2"

POLL_SECS   = float(os.environ.get("DS3_POLL",   "1.0"))
SETTLE_SECS = float(os.environ.get("DS3_SETTLE", "2.0"))
SLOT_ENV    = os.environ.get("DS3_SLOT", "auto")

SEP  = "-" * 60
SEP2 = "=" * 60

# ---------------------------------------------------------------------------
# Diff + print (snapshot/diff logic lives in snapshot.py)
# ---------------------------------------------------------------------------

def print_save_event(prev: Optional[SlotSnap], curr: SlotSnap, ts: str) -> None:
    bonfire = curr.bonfire_name or ("bonfire#%s" % curr.bonfire_id)
    print()
    print(SEP2)
    print("  SAVE DETECTED  %s" % ts)
    print("  %s  |  Level %d  |  %s souls  |  %s" % (
        curr.name, curr.level, "{:,}".format(curr.souls), bonfire))
    print(SEP2)

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
# Recording helpers
# ---------------------------------------------------------------------------

SIM_SAVES_ROOT = Path(__file__).resolve().parent.parent / "play_simulator_save_files"


def make_record_folder() -> Path:
    """Create the next play_NN_auto folder that does not already exist."""
    n = 0
    while n < 100:
        folder = SIM_SAVES_ROOT / ("play_%02d_auto" % n)
        if not folder.exists():
            folder.mkdir(parents=True)
            return folder
        n += 1
    raise RuntimeError("All play_00_auto..play_99_auto slots are taken")


# ---------------------------------------------------------------------------
# Main watch loop
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--record", action="store_true",
                    help="save a numbered copy of each save to play_simulator_save_files/play_NN_auto/")
    ap.add_argument("--no-llm", action="store_true",
                    help="advisor uses deterministic text only (no Claude calls)")
    args = ap.parse_args()

    WORKSPACE.mkdir(exist_ok=True)

    # Validate save file exists
    if not SAVE_FILE.exists():
        print("ERROR: save file not found: %s" % SAVE_FILE)
        print("Set DS3_SAVE_PATH environment variable to your DS3 save folder.")
        sys.exit(1)

    # Set up recording folder and log if requested
    record_folder: Optional[Path] = None
    record_seq = 0
    _log_file = None
    if args.record:
        record_folder = make_record_folder()
        session_ts = datetime.now().strftime("%Y%m%d%H%M")
        log_path = record_folder / ("session_%s.log" % session_ts)
        _log_file = open(log_path, "w", encoding="utf-8", buffering=1)
        sys.stdout = _Tee(sys.__stdout__, _log_file)
        print("  Recording to: %s" % record_folder)
        print("  Log file:     %s" % log_path.name)

    # Resolve slot
    if SLOT_ENV.isdigit():
        fixed_slot: Optional[int] = int(SLOT_ENV)
        print("  Watching slot %d (fixed)" % fixed_slot)
    else:
        fixed_slot = None
        print("  Slot: auto-detect (tracks whichever slot playtime changes)")

    print()
    print(SEP2)
    print("  DS3 Save Watcher%s" % ("  [RECORDING]" if record_folder else ""))
    print("  Save: %s" % SAVE_FILE)
    print("  Poll: %.1fs  |  Settle: %.1fs" % (POLL_SECS, SETTLE_SECS))
    print(SEP2)
    print()
    print("  Waiting for first save event... (rest at a bonfire in-game)")
    print()

    last_mtime: Optional[float] = None
    last_size:  Optional[int]   = None
    prev_snap:  Optional[SlotSnap] = None
    prev_playtimes: dict[int, int] = {}
    active_slot: Optional[int]     = fixed_slot
    advisor_sessions: dict[str, AdvisorSession] = {}

    try:
        while True:
            try:
                stat = SAVE_FILE.stat()
                mtime = stat.st_mtime
                size  = stat.st_size

                changed = (mtime != last_mtime or size != last_size)

                if changed:
                    # Wait for the write to finish settling
                    time.sleep(SETTLE_SECS)

                    # Re-stat after settling
                    stat2 = SAVE_FILE.stat()
                    mtime = stat2.st_mtime
                    size  = stat2.st_size

                    # Copy to workspace for analysis (always)
                    shutil.copy2(SAVE_FILE, WORK_SAVE)

                    # Copy to record folder if --record is active
                    if record_folder is not None:
                        record_seq += 1
                        ts_file = datetime.now().strftime("%Y%m%d%H%M")
                        record_name = "%02d_%s.sl2" % (record_seq, ts_file)
                        shutil.copy2(SAVE_FILE, record_folder / record_name)
                        print("  [recorded %s]" % record_name)

                    ts = datetime.now().strftime("%H:%M:%S")

                    # Detect which slot changed
                    new_playtimes = get_all_playtimes(WORK_SAVE)
                    if fixed_slot is None:
                        if prev_playtimes:
                            changed_slot = detect_changed_slot(prev_playtimes, new_playtimes)
                            if changed_slot is not None:
                                if active_slot != changed_slot:
                                    print("  [switched to slot %d]" % changed_slot)
                                    if record_folder is not None:
                                        (record_folder / "slot.txt").write_text(
                                            str(changed_slot), encoding="utf-8")
                                active_slot = changed_slot
                        if active_slot is None:
                            if new_playtimes:
                                active_slot = min(new_playtimes, key=new_playtimes.get)
                                print("  [auto-detected slot %d (%s)]" % (
                                    active_slot,
                                    "min playtime" if not prev_playtimes else "changed"))
                                if record_folder is not None:
                                    (record_folder / "slot.txt").write_text(
                                        str(active_slot), encoding="utf-8")
                    prev_playtimes = new_playtimes

                    if active_slot is None:
                        print("%s  No occupied slot detected." % ts)
                    else:
                        curr = snap_slot(WORK_SAVE, active_slot)
                        if curr is None:
                            print("%s  Slot %d not readable." % (ts, active_slot))
                        else:
                            print_save_event(prev_snap, curr, ts)

                            char_key = "%s_slot%d" % (curr.name, active_slot)
                            if char_key not in advisor_sessions:
                                advisor_sessions[char_key] = AdvisorSession(
                                    char_key, use_llm=not args.no_llm)
                            same_char = (prev_snap is not None and
                                         prev_snap.name == curr.name)
                            advice = advisor_sessions[char_key].on_save_event(
                                prev_snap if same_char else None, curr)
                            print_advisor(advice)

                            prev_snap = curr

                    last_mtime = mtime
                    last_size  = size

            except FileNotFoundError:
                print("  [save file not found - is DS3 running?]")
            except PermissionError:
                pass   # DS3 may have the file locked during write
            except Exception as e:
                print("  [error: %s]" % e)

            time.sleep(POLL_SECS)

    finally:
        if _log_file is not None:
            print("  Session log saved to: %s" % log_path)
            sys.stdout = sys.__stdout__
            _log_file.close()


if __name__ == "__main__":
    main()
