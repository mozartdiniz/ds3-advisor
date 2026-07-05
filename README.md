# DS3 Advisor

An AI companion that watches your **Dark Souls III** save file while you play. It decrypts and parses the save, tracks event flags and quest state, and speaks up only when it matters: before you break an NPC questline, miss unique content, or lock yourself out of an ending.

It never touches the game process or modifies anything — it only *reads* the save file DS3 writes on every bonfire rest, death, or quit-to-menu.

---

## Quick start (Windows, game installed)

From clone to advice in five steps:

```powershell
# 1. Clone and enter the project
git clone git@github.com:mozartdiniz/ds3-advisor.git
cd ds3-advisor\ai_assistant

# 2. Install dependencies (Python 3.9+, tested on 3.10)
pip install pycryptodome anthropic

# 3. Point the watcher at your save folder
#    It's %APPDATA%\DarkSoulsIII\<your-numeric-steam-id>\
$env:DS3_SAVE_PATH = "$env:APPDATA\DarkSoulsIII\0110000100000000"

# 4. (Optional) API key for Claude-phrased advice.
#    Without it the advisor still works, using deterministic messages.
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# 5. Run the watcher
python watcher.py
```

Now play the game. Every time you **rest at a bonfire, die, or quit to menu**, DS3 writes the save and within a couple of seconds the watcher prints what changed — and, when relevant, advice:

```
============================================================
  SAVE DETECTED  14:23:07
  Ashen  |  Level 42  |  18,500 souls  |  Undead Settlement
============================================================
  Got Loretta's Bone
  Rested at Undead Settlement  (from Dilapidated Bridge)

--- ADVISOR ---
You picked up Loretta's Bone. Bring it back to Greirat at
Firelink Shrine — this is what unlocks his first pillage trip.
```

Useful variations:

```powershell
python watcher.py --no-llm     # deterministic advice only, zero API calls
python watcher.py --record     # also archive every save for later replay
$env:DS3_SLOT = "4"            # pin a character slot (default: auto-detect)
```

> **Note:** no save files ship with this repo (they are gitignored). Everything runs against *your* save. Tests that depend on reference saves are skipped automatically when the files aren't on disk.

---

## Repository layout

| Folder | What it is |
|--------|------------|
| `ai_assistant/` | All the code: save parser, rule engine, quest evaluator, LLM advisor, watcher, simulator, research scripts |
| `ai_assistant_design/` | Design notes and research documentation — no code, but the best place to understand *how* everything works |
| `data/` | DS3 knowledge base: 47 item CSVs and 1,289 wiki markdown files (used by the advisor's wiki search) |
| `all-params/` | Raw game param tables (CSV) exported from the game files |
| `play_simulator_save_files/` | Folders of recorded save sequences for offline replay (contents gitignored) |

---

## `ai_assistant/` — the code

### Main tools

#### `watcher.py` — live companion (the main entry point)

Polls the save folder and runs the full advisor pipeline on every new save. See Quick start above.

Environment variables: `DS3_SAVE_PATH` (save folder), `DS3_SLOT` (0–9, default auto), `DS3_POLL` (poll seconds, default 1.0), `DS3_SETTLE` (write-settle seconds, default 2.0). Flags: `--record` (archive saves + session log), `--no-llm`.

#### `extract.py` — save → JSON

Decrypts a `.sl2` and dumps every occupied slot (name, class, level, stats, souls, inventory, equipment, last bonfire, known event flags) as JSON.

```powershell
python extract.py C:\path\to\DS30000.sl2                # print to stdout
python extract.py C:\path\to\DS30000.sl2 -o state.json  # write to file
```

#### `reason.py` — JSON → rule-based advice

Pure-Python rule engine (no LLM, no network). Reads a `state.json` from `extract.py` and fires build/covenant/quest/ending rules per slot.

```powershell
python reason.py state.json            # all slots
python reason.py state.json --slot 0   # one slot
```

#### `advisor.py` — one-shot advisor on a save file

Runs the same advisor pipeline the watcher uses, once, against any save. Good for "what would you tell me right now?".

```powershell
python advisor.py C:\path\to\DS30000.sl2 0        # slot 0, deterministic
python advisor.py C:\path\to\DS30000.sl2 0 --llm  # Claude-phrased (needs API key)
```

#### `play_simulator.py` — offline replay

Replays a folder of numbered `.sl2` snapshots from `play_simulator_save_files/`, printing diffs and advice between each pair. No game needed — this is the main development/QA tool.

```powershell
python play_simulator.py play_00                       # replay, 3s between steps
python play_simulator.py play_00 --interval 0          # as fast as possible
python play_simulator.py play_01 --slot 5 --log        # explicit slot, write log
python play_simulator.py play_00 --llm                 # with Claude phrasing
```

#### `quest_evaluator.py` — questline status for one NPC

Evaluates a questline definition from `decision_making_files/` against a save and prints the current phase, warnings, and next steps.

```powershell
python quest_evaluator.py C:\path\to\DS30000.sl2 decision_making_files\greirat_of_the_undead_settlement.json 4
```

(Last argument is the slot; omit to evaluate all occupied slots.)

#### `python -m parser.cli` — quick tabular summary

```powershell
python -m parser.cli C:\path\to\DS30000.sl2
```

Prints one line per slot: name, class, level, playtime, souls, item counts, location.

### Libraries (imported, not run directly)

| File | Role |
|------|------|
| `parser/` | Save-format layer: BND4 container, AES-CBC decryption, slot/stats/inventory/equipment/flags parsing |
| `snapshot.py` | `SlotSnap` capture + diff-to-events (shared by watcher, simulator, advisor) |
| `advisor_core.py` | Deterministic engine: checkpoint policies, quest evaluation, session memory/dedupe |
| `advisor_agent.py` | Claude phrasing layer (model via `DS3_ADVISOR_MODEL`, default `claude-opus-4-8`); falls back to deterministic text without an API key |
| `quest_evaluator.py` | Also importable: `evaluate_quest(quest, slot_state)` |

### Data folders

| Folder | Contents |
|--------|----------|
| `data/` | Item-ID → name maps, event-flag dictionaries, bonfire flags, `checkpoints.json` (advisor content) |
| `decision_making_files/` | Questline definitions (Greirat, Irina, Yoel/Yuria) — semantic flag conditions, phases, warnings |
| `sim_workspace/` | Scratch folder the watcher/simulator copies saves into (gitignored) |

### `scripts/` — research & flag-labelling tools

These were built while reverse-engineering the save format. The ones you're most likely to want:

```powershell
# Diff two saves and print which event flags flipped (semantic IDs)
python scripts\diff_controlled_saves.py before.sl2 after.sl2 --slot 5

# Same idea, tuned for quest tracking (also reports untracked flag events)
python scripts\diff_greirat_quest.py before.sl2 after.sl2 --slot 4

# Validate the flag decoder against a 40-step QA save corpus
python scripts\validate_flags_qa.py
```

The rest (`probe_*.py`, `find_*.py`, `verify_*.py`, `parse_emevd_flags.py`, `scrape_event_flags.py`) are one-off investigation tools kept for reference; each has a docstring explaining what it probes.

### `tests/`

```powershell
python -m pytest tests/ -q
```

Tests anchored on reference saves skip automatically when those saves aren't on disk.

---

## `ai_assistant_design/` — the documentation

Design notes and research logs, split by topic. **Start with [`ai_assistant_design/index.md`](ai_assistant_design/index.md)** — it indexes everything and has a "looking for X → go to Y" table.

| Doc | What's inside |
|-----|---------------|
| `vision.md` | What this project is, why DS3 |
| `parser_reference.md` | File map, run commands, save-format offsets, parser capabilities |
| `flag_research.md` | How DS3 event flags actually work in the save (structural walk + semantic flag-ID codec) |
| `advisor_and_tips.md` | Advisor pipeline design, checkpoint policies, suggestion catalog |
| `architecture.md` | Transport/storage/UX decisions, live memory-reading plan |
| `controlled_saves_protocol.md` | How to capture clean save pairs for labelling new flags |
| `roadmap.md` | What's next |
| `gotchas.md` | Runtime gotchas worth reading before touching the code |
| `session_log.md` | Chronological research notes |

`ai_assistant_design.md` (repo root) is the original monolithic design doc these were split from — kept for history.

---

## How it works (one paragraph)

DS3 saves are BND4 containers with AES-CBC-encrypted entries — one per character slot. The parser decrypts a slot, anchors on the character name, and walks the payload structurally to find stats, inventory, equipment, and the event-flag region (flags are addressed by semantic ID, e.g. `1225` = "Greirat recruited"). `snapshot.py` turns two consecutive saves into a list of events ("got item X", "flag Y set", "rested at Z"); `advisor_core.py` matches those events against checkpoint policies and questline definitions; and if anything is worth saying, `advisor_agent.py` has Claude phrase it in one or two short messages (or falls back to fixed text without an API key).
