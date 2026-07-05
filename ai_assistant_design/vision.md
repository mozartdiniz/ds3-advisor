# Vision

A passive companion that watches a player's Dark Souls 3 save file and surfaces contextual guidance: lockout warnings, missable-content nudges, ending steering, build viability checks, and point-of-no-return checklists. The product is meant to *prevent regret* on a first or second playthrough, not to spoon-feed a guide.

Architecture summary (v0):

```
[Windows PC]                  [Home server: Linux/Mac on LAN]          [iPad / phone PWA]
 DS3 save (.sl2)               FastAPI + SQLite (FTS5)
      │                          │
      ▼                          ├─ /ingest   ◄── raw .sl2 (POST) ──┐
 watcher.py                      ├─ decrypt + parse                  │
 (mtime poll, ~2s)               ├─ diff vs prior state (SQLite)     │
      │                          ├─ rule engine (deterministic)      │
      └──── POST raw .sl2 ───────┤                                    
                                 ├─ LLM phrases fired rules           
                                 ├─ persist messages (+ FTS5 mirror)  
                                 │                                    
                                 ├─ /events    (SSE) ───────────►  chat feed
                                 └─ /history?since=...  ────────►  catch-up
```

Raw `.sl2` travels client→server in v0 — see [architecture.md](architecture.md) for the rationale and when to revisit.

---

## Game choice: Dark Souls 3

Decision: build for **DS3** first.

Rationale (vs DS1, DS2, Elden Ring):

- **DS3 has the highest value density per warning.** Quest lockouts in DS3 are notoriously fragile and well-documented — Yoel/Yuria, Anri/Horace, Sirris, Siegward, Greirat, Orbeck, Cornyx/Karla — and players regularly break them by accident.
- **4 endings with clean flag dependencies** make ending steering tractable.
- **Best community modding tooling of any Souls game** (Smithbox, DSMapStudio, Yapped Rollo).
- **This repo already contains** 1,289 wiki markdowns and a full CSV item catalog — equal or better than what we have for DS1.
- DS2 was rejected: smaller modding scene, fewer iconic lockouts, mechanics (Soul Memory, Bonfire Ascetics, Fragrant Branches) don't map cleanly to "do this next" guidance.
- Elden Ring was rejected for v1: highest total addressable value but open world makes "what's next?" a ranking problem with no canonical answer; save format is also a moving target across patches.

DS1 remains useful as a prototype platform — `parse_save.py` already exists and works. Architecture proven on DS1 ports to DS3.

---

## What the save file actually gives us

Decrypted `.sl2` (AES-CBC, key public) exposes a **snapshot of state**, never an event stream:

| Primitive | Notes |
|---|---|
| Inventory | Items + counts per slot type (weapon, armor, ring, good) |
| Stats | Level, attribute spread, souls, hollowing, deaths |
| Event flags | Large bitfield. Each bit = one game-state boolean. Hundreds of thousands of bits; meaningful subset is small. |
| Equipped slots | Weapons, rings, attuned spells |
| Last bonfire rested at | Proxy for "where the player is" |
| Covenant + rank | |
| NG cycle, playtime | |

We recover history via two mechanisms:

- **Diffing snapshots** (between bonfire rests / quits) gives derived events: `bonfire_lit`, `npc_died`, `item_gained`, `level_up`.
- **Current-state predicates** drive most rules: "you have X, missing Y, and flag Z is set."

### Things we genuinely cannot detect

- Real-time advice during combat (save isn't written mid-fight).
- Dialogue lines heard without an associated flag (rare in DS3 — most major lines flip flags).
- Player intent (we see "INT 14, no catalyst" — we don't know if they meant to be a sorcerer).
- Exact ordering of two events that happened between bonfires.
- Things seen vs missed (no fog-of-war).
