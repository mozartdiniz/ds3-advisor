# Gotchas & Workflows

---

## Gotchas worth remembering

- **Python 3.10** on Windows (`C:\Program Files\Python310\python.exe` — no venv in repo, install deps globally with pip).
- **Save file at `DS30000.sl2`** is the Wanderer mule (downloaded from internet, 10 slots Alpha…Kappa) — used as the canonical test fixture for `tests/test_slots.py`. **Not** to be confused with an actual game save.
- **QA character is slot 4** ("QA"), QA2 character is slot 5 ("QA2"). quest-track corpus character is "quest_track" slot 4; greirat-quest corpus character is "Greirat" slot 5.
- **Item ID JSONs in `data/_*.json`** are from alfizari's GPL-3 DS3 editor. They're cached locally; license-compatible for personal use but re-evaluate before any redistribution. (The flag-section structural walk in `parser/flags.py` is also derived from that GPL-3 source.)
- **AES key**: `fd 46 4d 69 5e 69 a3 9a 10 e3 19 a7 ac e8 b7 fa` — public, sourced from `jtesta/souls_givifier`.
- **Reasoner output is VERY verbose for save-editor mule saves** (every soul triggers Ludleth advice). That's correct rule behaviour, but for a chat-UX layer we'll want per-save rate-limits. Not urgent.
- **`crypto.decrypt_entry()` strips the 4-byte length prefix.** alfizari's published payload offsets assume the prefix is present — everything in `parser/flags.py` is already adjusted (−4); remember this when porting any other offset from their source.
- **Event flags: never use positional offsets.** The flag section slides with three variable-size structures (gaitem registry, two counted tables). Always go through `parser.flags.find_flag_blob()` + semantic flag IDs. See [flag_research.md](flag_research.md).
- **Volatile flags**: map locals 5000–6999 (e.g. 14005xxx), 74000103–108, 74000810–813, commons 4175/4180 toggle with NPC schedules / event-script runtime — never use them as tip triggers.
- **name_offset is dynamic** — varies across saves because the item registry before the name has variable size. Still true for stats/inventory/equipment parsing (those remain name-anchored); flags no longer depend on it.

---

## Controlled-saves workflow (flag labelling)

Controlled save pairs live under `play_simulator_save_files/` (e.g. `play_01/`), numbered:

```
play_simulator_save_files/play_01/
  01_-_Before_Talk_to_Greirat.sl2
  02_-_After_Talk_to_Greirat.sl2
  ...
```

Then run:
```
python scripts/diff_controlled_saves.py before.sl2 after.sl2 --slot N
python scripts/diff_greirat_quest.py a.sl2 b.sl2 --slot N   # any two saves
```

Output is **semantic flag IDs** (e.g. `74000300`). Add the meaningful ones to
`KNOWN_FLAGS` in `parser/flags.py` and an expectation row in
`scripts/validate_flags_qa.py`; reference them directly in `data/tips.json`
triggers and `decision_making_files/*.json` flag registries.
