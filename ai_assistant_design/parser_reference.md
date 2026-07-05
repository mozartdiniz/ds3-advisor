# Parser Reference

Current state of the save-file parser. For the history of how we got here, see [session_log.md](session_log.md).

---

## Working POC pipeline

Run from `ai_assistant/`:

```
python extract.py <save.sl2>          → writes state.json next to the save
python reason.py  <state.json>        → prints advice grouped by slot
python -m parser.cli <save.sl2>       → tabular summary, no JSON
pytest tests/                         → 9 passing, 13 skipped (corpus saves not on disk)
```

---

## File map

```
dark-souls/  (repo root)
├── DS30000.sl2                       canonical "Wanderer mule" test save (10 slots populated)
├── ai_assistant_design/              design notes (this folder)
├── save_files/                       saves used for validation
│   ├── 01_created_character_nothing_done.sl2   QA playthrough step 1
│   ├── … (20 sequential QA saves, steps 01–20; extended to 40 in session 4)
│   ├── max_level_and_new_game_plus_5/    "1205" lvl 802 NG+5 / 603M souls; bonus "1146" lvl 20
│   ├── sl_715/                            "Morguls" SL715, 99 in 8 attrs + LCK 12, Knight
│   └── the_usurpation_of_fire_ending/     "Male Hero 1" lvl 204 Deprived
└── ai_assistant/
    ├── pyproject.toml                  pycryptodome + pytest, Python 3.9+
    ├── venv/                           local virtualenv
    ├── extract.py                      CLI: save → state.json (includes equipment + flags)
    ├── reason.py                       CLI: state.json → advice  (10 rules)
    ├── snapshot.py                     shared SlotSnap + snap_slot + diff_events (used by watcher/simulator/advisor)
    ├── advisor.py                      orchestrator: AdvisorSession.on_save_event(prev, curr) → messages; CLI one-shot
    ├── advisor_core.py                 deterministic engine: findings (checkpoint policies + quest evaluator),
    │                                   progression high-water mark, topic dedupe, SessionMemory, wiki search
    ├── advisor_agent.py                Claude agent layer (tool_runner; tools = advisor_core query fns);
    │                                   graceful fallback to deterministic text without API key
    ├── advisor_memory/                 per-character session memory JSONs (gitignored)
    ├── quest_evaluator.py              evaluates decision_making_files/*.json against a slot state
    ├── watcher.py                      live save watcher; advisor wired in (--no-llm to disable Claude)
    ├── play_simulator.py               replays numbered .sl2 folder; diffs + advisor (--llm / --no-advisor)
    ├── parser/
    │   ├── bnd4.py                     BND4 container reader
    │   ├── crypto.py                   DS3 AES-CBC key + decrypt
    │   ├── userdata.py                 reads BND4 entry 10 (load-screen index, occupancy, bonfire)
    │   ├── slots.py                    per-slot parsing, dynamic name anchor
    │   ├── stats.py                    9 attributes + level + souls (relative to name)
    │   ├── inventory.py                two-grid parser (consumables grid + key-items grid)
    │   ├── equipment.py                equipment slots reader (weapons, armor, rings — relative to name)
    │   ├── flags.py                    event-flag reader: structural walk + semantic flag-ID codec, KNOWN_FLAGS, diff_flags
    │   └── cli.py                      `python -m parser.cli`
    ├── data/
    │   ├── _weapons.json               weapon ID→name (alfizari)
    │   ├── _armor.json                 armor ID→name (alfizari)
    │   ├── _ring.json                  ring ID→name (alfizari + Way of Blue, Mound-makers added)
    │   ├── _goods_magic.json           consumables + spells ID→name (alfizari)
    │   ├── _event_flags.json           354 event flag IDs→labels (soulsmodding.com, CC BY-SA 4.0)
    │   ├── _bonfire_flags.json         81 LocationEventId → bonfire name (from BonfireWarpParam)
    │   ├── _emevd_flags.json           boss defeat IDs + NPC state ranges from EMEVD
    │   ├── checkpoints.json            advisor checkpoint DB: retrospective/proactive/reactive policies,
    │   │                               area progression order, topics (replaces tips.json)
    │   └── tips.json                   SUPERSEDED by checkpoints.json — kept as reference, nothing loads it
    ├── scripts/                        one-off probes used to discover offsets
    │   ├── scrape_event_flags.py       DokuWiki HTML walker → _event_flags.json
    │   ├── find_flag_start.py          legacy monotonic bit scanner (superseded; see flag_research.md)
    │   ├── diff_controlled_saves.py    diffs controlled save pairs by flag_id
    │   ├── diff_flags.py               diffs two saves' flag region relative to anchor
    │   ├── find_monotonic_flags.py     derives positional-index → event table
    │   ├── parse_emevd_flags.py        extracts SetEventFlag calls from decompiled EMEVD
    │   ├── validate_flags_qa.py        validates KNOWN_FLAGS against all 40 QA saves
    │   ├── diff_greirat_quest.py       semantic flag diff of any two saves (CLI)
    │   ├── decode_flag_diffs.py        corpus-wide semantic flag diff dumps
    │   └── verify_alfizari_walk.py     verification harness for the structural walk
    ├── tests/
    │   ├── test_slots.py               9 tests anchored on Wanderer save — all passing
    │   ├── test_save_corpus.py         parametrised across 3 corpus saves (13 skipped, saves not on disk)
    │   ├── test_bonfires.py            bonfire ID resolution (skipped, corpus saves not on disk)
    │   └── test_reason.py              10 reasoner rules (crafted slot dicts, no corpus saves required)
    ├── play_simulator_save_files/
    │   ├── play_00/                    40-step QA playthrough (steps 01–40, slot 4)
    │   ├── play_01/                    6 controlled save pairs (slot 5 / QA2) — also used for flag-diff labelling
    │   └── greirat-quest/              Greirat questline controlled saves (slot 5)
    ├── decision_making_files/          quest evaluator content (semantic flag IDs, topic-tagged phases/warnings)
    │   ├── greirat_of_the_undead_settlement.json
    │   ├── irina_of_carim.json
    │   └── yoel_and_yuria_of_londor.json
    └── sim_workspace/                  working directory for the simulator's current save copy
```

---

## What the parser extracts today (per slot)

- name, character class (Knight / Mercenary / Warrior / Herald / Thief / Assassin / Sorcerer / Pyromancer / Cleric / Deprived), sex
- level, playtime (ms precision), souls
- 9 attributes (VIG, ATT, END, VIT, STR, DEX, INT, FTH, LCK)
- last bonfire rested at (ID + human-readable name, resolved from `BONFIRE_NAMES`)
- **equipment loadout**: left/right hand weapons, head/chest/hands/legs armor, ring slots 1–4 — item ID + resolved name for each non-empty slot
- **inventory grid**: every non-upgradeable item (consumables, key items, spells, rings, ammo) with category, item ID, count, resolved name — from two grids: consumables at `name+996`, key items at `name+0x7AA8`
- **flags_set**: human-readable labels for all set EzState flags in KNOWN_FLAGS
- occupancy for all 10 character slots (which are populated)

**Gap**: owned weapons/armor that are neither equipped nor in the inventory grid (e.g. stashed extras) are not yet surfaced. The item registry (60-byte records before `name_offset`) covers those — see "Still to map".

---

## Parser progress — field offsets

All offsets relative to `name_offset` unless noted. `name_offset` is found dynamically by searching the slot payload for the UTF-16-LE character name (as read from BND4 entry 10 userdata).

| Field | Source | Offset / location |
|---|---|---|
| Character name | slot payload | UTF-16-LE, up to 16 chars; anchor for `name_offset` |
| Class | slot payload | `name+0x26`, u16 LE — Knight=0, Mercenary=1, Warrior=2, Herald=3, Thief=4, Assassin=5, Sorcerer=6, Pyromancer=7, Cleric=8, Deprived=9 |
| Sex | slot payload | `name+34` (name+0x22), u8 — 0=Female, 1=Male |
| Playtime | slot payload | absolute offset 8, u32 LE, **milliseconds** |
| Level | slot payload | `name-0x3C`, u32 LE |
| Souls | slot payload | `name-0x38`, u32 LE |
| 9 attributes (VIG, ATT, END, STR, DEX, INT, FTH, LCK; VIT at +0x28) | slot payload | `name-0x68` onward, each u32 LE |
| Inventory grid (consumables, rings, spells, ammo, key items) | slot payload | grid 1 at `name+996`; grid 2 (key items) at `name+0x7AA8`; 16-byte records, item_id at +4, count at +8 |
| Item ID → name map | local `data/_*.json` | fetched from alfizari DS3 save editor |
| User-data (per-slot occupancy + load-screen summary) | BND4 entry 10 | `parser/userdata.py` |
| Last bonfire rested at | BND4 entry 10, per-slot record | offset `+50`, u16 LE. Confirmed: 3000, 3100, 4000, 4005, 4100, 5100. Full dict in `BONFIRE_NAMES`. Correct formula: `WarpEventId // 10000 * 10 = area_code`. |
| Currently-equipped weapons | slot payload | `name+492` (left hand), `name+496` (right hand), u32 LE, direct weapon-map lookup |
| Currently-equipped armor | slot payload | `name+540/544/548/552` (head/chest/hands/legs), u32 LE, stored with high byte `0x01`; lookup via lower-3-byte key into armor map |
| Currently-equipped rings | slot payload | `name+556/560/564/568` (ring slots 1–4), u32 LE, direct ring-map lookup |
| Event flags (all systems) | slot payload | structural walk → `event_flag_start` (fixed 0x33E5E section); blob at `+0x5D`; semantic flag-ID codec — see [flag_research.md](flag_research.md) |
| AES key | hardcoded | `fd 46 4d 69 5e 69 a3 9a 10 e3 19 a7 ac e8 b7 fa` |

### Equipment encoding quirks

- Armor item IDs in the equipment region use high byte `0x01` regardless of the canonical `0x1X` category byte in the armor map. The module builds a reverse lookup keyed on the lower 3 bytes.
- Shields (high byte `0x01`) appear identically in both the slot and the weapon map — looked up directly.
- Empty sentinels: `0xFFFFFFFF`, `0x00000000`, `0x0001ADB0`.

---

## Still to map (post-v0 parser work)

### Item registry (owned-but-not-equipped upgradeable items)
The region from `0x60` to `~name_offset` is the **item registry**: 60-byte records, handle at +0, item_id at +4, durability at +8. Covers weapons/armor/rings that are owned but neither equipped nor in the inventory grid. Not yet iterated. Add as `equipment.py` sibling or extend the inventory module.

### Event flags — SOLVED (2026-06-11)
All flag systems (event, object, talk, NPC-state commons) live in ONE world-flag blob located via the structural payload walk. `parser/flags.py` reads them by semantic ID. Remaining flag work is content curation (expanding KNOWN_FLAGS), not parsing. See [flag_research.md](flag_research.md).

### Hollowing count
Likely a small u8/u32 near the stat block. Required for precise Yoel/Yuria path tracking.

### NG cycle
Small u8 near stat block. Dark Tarnished is NG+5; all others NG+0 on the QA corpus.

### Deaths
Likely near the stat block. All zeros on the Wanderer mule save so not yet anchored.
