# Resources

---

## Public resources catalogued

| Resource | What it provides | Status |
|---|---|---|
| [soulsmodding.com DS3 event flag list](https://soulsmodding.com/doku.php?id=ds3-refmat:event-flag-list) | ~200+ semantically labeled flag IDs (bosses, NPCs, covenants, story progression). Last updated March 2025. CC BY-SA 4.0. | Primary flag dictionary — scraped into `data/_event_flags.json`. |
| [mamalakic/darksouls3-auto-tracker](https://github.com/mamalakic/darksouls3-auto-tracker) | Python+Flask. Decrypts DS3 `.sl2`, parses inventory, diffs against achievement lists. | Reference code only (2 commits, unmaintained). Inventory-only — no flag reading. |
| [alfizari/Dark-Souls-3-Save-Editor-PS4-PC](https://github.com/alfizari/Dark-Souls-3-Save-Editor-PS4-PC) | Full DS3 save editor; exposes slot offsets for stats, equipment, inventory. GPL-3. | Source for item ID maps (`_weapons.json`, `_armor.json`, etc.) and offset tables. |
| [jtesta/souls_givifier](https://github.com/jtesta/souls_givifier) | GPL-3 multi-game (DSR/DS2/DS3/ER) save modifier. Python + JS. | Confirms AES-based encryption family; dynamic name offset approach (use name as needle). |
| [Meowmaritus boss EventEntityIDs gist](https://gist.github.com/Meowmaritus/8f16d27988f907ddedf882405642b096) | ~40 DS3 bosses + variants (DLC included) keyed by entity ID. | Cross-reference for boss-kill rules. |
| [Smithbox](https://github.com/vawser/Smithbox) / [DSMapStudio](https://github.com/soulsmods/DSMapStudio) | Full modding tools. Expose param tables, EMEVD scripts, BonfireWarpParam. | Ground truth for flag IDs and param data. Used to derive `_emevd_flags.json` and `_bonfire_flags.json`. |
| [EMEVD format docs](http://soulsmodding.wikidot.com/format:emevd) | The event-script format that generates flags. | Reference only — we consume flags, don't parse EMEVD. |
| [JKAnderson/EventPocket](https://github.com/JKAnderson/EventPocket) | Realtime flag viewer for DS1/DSR. | Pattern reference for "watch flags live". |

---

## What we have locally

- `data/` — 47 CSV files covering every item category (weapons, armor, rings, sorceries/miracles/pyromancies, ashes, gestures, sacred chimes, staves, boss souls, boss soul weapons, multiplayer items, upgrade materials, achievements).
- `data/wiki/` — 1,289 wiki markdown files.
- `data/wiki/` — the scraped wiki pages, one Markdown file each.
- `scraper.py`, `wiki_md_scraper.py` — scraping infrastructure.
- `DS30000.sl2` — canonical "Wanderer mule" test save (10 slots Alpha…Kappa, downloaded from internet).
- `ai_assistant/data/_*.json` — item ID maps from alfizari, event flag dict from soulsmodding, EMEVD flags, bonfire flags.

---

## What still needs to be built (toward v1)

In rough dependency order:

1. ~~Flag reader~~ **DONE (2026-06-11)** — structural walk + semantic flag IDs in `parser/flags.py`; remaining work is KNOWN_FLAGS curation (see [roadmap.md](roadmap.md)).
2. **Watcher daemon** — file mtime poller; emits `(prev_state, new_state)` pairs. Architecture sketched in [architecture.md](architecture.md).
3. **Event synthesizer** — diffs two states → list of events.
4. **FastAPI server** — `/ingest`, `/events` (SSE), `/history` endpoints.
5. **SQLite storage** — state persistence + FTS5 chat history.
6. **LLM layer** — ranks + rephrases fired rules into friendly text (zero-token rule engine already done).
7. **React PWA** — mobile-first chat feed for iPad / phone.
8. **Rule authoring** — the long tail; see [advisor_and_tips.md → Suggestion catalog](advisor_and_tips.md).

---

## Reference: existing DS1 prototype

`/Users/mozartdiniz/Dev/dark-souls/DS/parse_save.py` — working DS1 inventory extractor + achievement diff report. Demonstrates the parser → ID map → category diff → report flow. Architecture transfers; offsets and ID maps do not.
