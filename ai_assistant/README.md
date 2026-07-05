# DS3 AI Assistant — Tool Reference

Three main tools, each with a distinct role:

| Tool | What it does |
|------|-------------|
| `watcher.py` | Watches the live save file and prints what changed after each bonfire rest / death |
| `play_simulator.py` | Replays a folder of recorded `.sl2` saves offline |
| `reason.py` | Reads a `state.json` (from `extract.py`) and fires rule-based advice |

---

## watcher.py

Monitors `DS30000.sl2` in real time. Every time DS3 writes a save (bonfire rest, quit to menu, death), it prints a diff of what changed: level-ups, souls gained/lost, items picked up or dropped, equipment changes, and named event flags.

### Quick start

```bash
# Default: reads from the Windows AppData path (update DS3_SAVE_PATH for your machine)
DS3_SAVE_PATH="/path/to/DarkSoulsIII/save_folder" python watcher.py
```

Then rest at any bonfire in-game — output appears within a couple of seconds.

### Record mode

```bash
python watcher.py --record
```

Saves a numbered copy of every detected save to `../play_simulator_save_files/play_NN_auto/` (the next unused slot). Also writes a `session_YYYYMM.log` file and a `slot.txt` hint for `play_simulator.py`. Use this to capture a session for later replay or debugging.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DS3_SAVE_PATH` | Windows AppData path | Folder containing `DS30000.sl2` |
| `DS3_SLOT` | `auto` | Character slot to watch (0–9). Auto-detects by playtime change |
| `DS3_POLL` | `1.0` | Poll interval in seconds |
| `DS3_SETTLE` | `2.0` | Seconds to wait after a file change before reading (lets DS3 finish writing) |

### Example output

```
============================================================
  SAVE DETECTED  14:23:07
  Ashen  |  Level 42  |  18,500 souls  |  Undead Settlement
============================================================
  Got Loretta's Bone
  Rested at Undead Settlement  (from Dilapidated Bridge)
  Souls: 12,000 -> 18,500  (+6,500)
```

---

## play_simulator.py

Replays a folder of `.sl2` snapshots in sequence, printing the diff between each consecutive pair. No game running required. Useful for reviewing what happened during a session or for testing the parser against recorded saves.

Save folders live in `../play_simulator_save_files/`. The naming convention is:

```
play_simulator_save_files/
  play_00/          # manually curated saves
  play_00_auto/     # auto-recorded by watcher --record
  play_01/
  ...
```

Files inside a play folder must start with a number (`01_...`, `02_...`, etc.) — that's the sort order.

### Usage

```bash
python play_simulator.py <folder-name> [options]
```

```bash
# Replay a manually curated session
python play_simulator.py play_00

# Replay an auto-recorded session (slot is read from slot.txt automatically)
python play_simulator.py play_03_auto

# Faster replay, explicit slot, write a log file
python play_simulator.py play_01 --interval 0.5 --slot 2 --log
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--interval N` | `3.0` | Seconds to pause between steps |
| `--slot N` | `auto` | Character slot to read (0–9). Auto-detects if `slot.txt` exists in the folder |
| `--log` | off | Write a `session_replay_YYYYMM.log` to the play folder |

### Auto-detection logic

Without `--slot`: compares playtime between saves 1 and 2 to find which slot changed. Falls back to the slot with the lowest playtime (freshest character). If the folder was created by `watcher --record`, the `slot.txt` file overrides auto-detection automatically.

---

## reason.py

Rule-based advisor. Reads a `state.json` produced by `extract.py` and fires a set of rules against each occupied character slot. No LLM, no network — pure Python rules.

### Pipeline

```bash
# Step 1: extract state from a save file
python extract.py /path/to/DS30000.sl2 -o state.json

# Step 2: run the advisor
python reason.py state.json
python reason.py state.json --slot 0   # single slot only
```

### What rules fire

| Category | Rule | Triggers when |
|----------|------|---------------|
| `build` | `E.int_no_catalyst` | INT ≥ 14 but no staff in inventory |
| `build` | `E.faith_no_chime` | FAITH ≥ 14 but no chime/talisman |
| `build` | `E.caster_no_flame` | INT ≥ 12 and FAITH ≥ 12 but nothing to cast with |
| `build` | `E.low_vigor` | Level ≥ 25 with Vigor < 18 |
| `build` | `E.stat_overinvest` | Any stat past its hard cap (VIG 50, END 40, others 60) |
| `build` | `E.ludleth_trades_available` | Boss souls in inventory that Ludleth can transpose |
| `covenant` | `F.covenant_badges` | Covenant badges in inventory |
| `tip` | `H.key_item_nudges` | Notable key items present (Loretta's Bone, Eyes of a Fire Keeper, etc.) |
| `tip/checklist` | `H.area.*` | Based on last bonfire — area-specific NPC/quest reminders |
| `ending` | `D.usurpation_path_active` | Dark Sigil in inventory |

Rules are sorted by severity: `warning` → `nudge` → `info`.

### Example output

```
# /path/to/DS30000.sl2
# saved 2026-05-31T14:20:00+00:00

Slot 0: Ashen — Knight / Male / lvl 42
-------------------------------------------

[NUDGE  ] [build] Vigor 15 is low for level 42
  rule: E.low_vigor
  At level 42 your Vigor is only 15 ...

[INFO   ] [build] 2 boss soul(s) you could trade at Ludleth
  rule: E.ludleth_trades_available
  ...
```

---

## extract.py (helper)

Converts a `.sl2` to a readable JSON state file. Used as input for `reason.py`.

```bash
python extract.py DS30000.sl2                   # prints to stdout
python extract.py DS30000.sl2 -o state.json     # writes to file
```

Output includes all occupied slots with: character name, class, sex, level, playtime, souls, full stats, inventory (with item IDs and counts), equipment, last bonfire, and known event flags.
