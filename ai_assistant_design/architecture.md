# Architectural Decisions

---

## Parsing & transport

- **v0 sends the raw `.sl2` to the server**, which decrypts and parses it. The earlier draft argued for client-side parsing on trust grounds (uploading saves clones the character) — that concern applies to a multi-tenant SaaS, not to a personal home server. A dumb client is much faster to iterate. **Revisit before exposing this beyond a single user**: at that point switch to client-side parse + state-summary upload.
- **Watcher polls file mtime every ~2s.** Native FS events (`watchdog` / `ReadDirectoryChangesW`) are an upgrade path, not a starting point.
- **The save is written at discrete moments only**: bonfire rest, quit-to-menu, death, certain story events / cutscenes. Nothing to miss by polling.
- **Steam Cloud can rewrite the file** when the game isn't running. Dedupe on **parsed-state diff**, not mtime alone — a touch with no state change produces no events.
- **Read shared, wait for size to stabilise** (two consecutive polls ~200ms apart with the same size) before parsing, to avoid torn reads while DS3 is mid-write.

## Rule engine + LLM

- **Rule engine is deterministic.** The LLM is for *phrasing* and *ranking*, not for deciding what triggers. Hallucinated quest advice is the worst possible failure mode.
- **Most save events produce zero messages.** Cap at 2–3 messages per save event even if more rules fire. A chat feed becomes noise fast if every bonfire rest generates five lines.

## Storage

- **SQLite on the server.** Single file, zero ops, plenty fast for one user.
- **Prior parsed state lives on the server** (the side that diffs).
- **Chat history is persisted**; an **FTS5 virtual table** gives free full-text search alongside structured filters (category, date, character, rule_id).

## Client / UX

- **Windows watcher**: plain Python script run from a venv. PyInstaller + tray icon deferred until a non-dev user needs it.
- **Surface**: mobile-first React PWA (Vite + Tailwind + shadcn), running on iPad / phone as a second screen while playing.
- **Push channel**: Server-Sent Events. Traffic is asymmetric (server push + occasional client request) — WebSockets aren't justified.
- **Network**: LAN-only for v0. No Tailscale / Cloudflare Tunnel yet. Plain HTTP on the LAN; HTTPS becomes necessary if/when we install as a real iOS PWA or expose beyond the house.
- **Character selection is app-level.** First run: parser lists all populated slots (name + level + last-played); user picks one and that choice is sticky. Feed and prior-state are per-character.

---

## Deferred to post-v0

### Interactive agent ("ask the companion") — planned v1

v0 ships **proactive only**: the server notices, the server speaks. The companion is a one-way feed. We deliberately defer the two-way conversation to land reasoning over states first.

When we add it:

- Add `POST /ask` alongside the SSE feed. Traffic stays asymmetric — still no WebSocket needed.
- Agent answers are grounded in three tools:
  - `query_state(...)` — current parsed save (flags, inventory, NPC statuses, last bonfire)
  - `evaluate_rule_hypothetical(...)` — "would rule X fire if I did Y?", using the existing predicate library
  - `search_wiki(...)` — RAG over the 1,289 wiki markdowns in `data/wiki/`
- Build a **wiki RAG index**: `sqlite-vec` (or Anthropic embeddings) over the wiki corpus. Static content, cheap to maintain, no incremental indexing needed.

Example interactions to design toward:
- "Should I kill Abyss Watchers now?" → agent calls `evaluate_rule_hypothetical(boss=AbyssWatchers)` to enumerate triggered lockouts, summarises.
- "Tell me about Yuria's questline." → wiki RAG.
- "Where can I find a catalyst from here?" → wiki RAG + `query_state(last_bonfire=...)`.

### Other deferred items

- PyInstaller package + system tray for non-dev users on Windows.
- iOS PWA install + web push notifications (iOS 16.4+ supports push for installed PWAs).
- Tailscale or Cloudflare Tunnel for off-LAN access.
- `watchdog`-based native FS events on Windows — only if mtime polling shows up as a problem.
- Multi-user / multi-tenant: at that point, revisit "raw `.sl2` upload" and switch to client-side parse + state-summary upload.

---

## Live Memory Reading (Alternative Approach)

Not yet implemented — requires DS3 running on the same machine. Deferred until tested on the gaming PC.

### Motivation

The save file is only written at discrete moments (bonfire rest, death, quit to menu). NPC dialogue flags flip in RAM immediately when the dialogue node fires but are **not flushed to disk until the player quits**. If a player talks to Greirat, sends him on a mission, and dies — the flag never appears in the save file for that session. Memory reading solves this.

### Comparison with save file approach

| Dimension | Save file | Memory reading |
|---|---|---|
| **Trigger** | DS3 writes the file (bonfire, death, quit) | Your poll interval (e.g. 200–500ms) |
| **NPC dialogue flags** | Only after quit | Live — fires within 500ms |
| **Quest flag transitions** | Only after quit | Real-time |
| **Player position / zone** | Not available | Available |
| **Enemy HP / aggro** | Not available | Available |
| **Inventory, stats, equipment** | Full snapshot | Same, live |
| **Latency** | 1–3s (poll + settle) | ~200–500ms |
| **Complexity** | Already built | Needs pymem + offset table |
| **EAC risk** | None | Incompatible online — safe offline only |

Memory reading is a **strict superset** of the save file. The save file approach remains sufficient for post-bonfire summaries; memory reading unlocks real-time NPC tracking.

### What memory reading adds to the pipeline

The save file diff already covers ~26 of 40 first-playthrough milestones. The ~14 "silent" steps — pure NPC-dialogue milestones — are exactly what memory reading unlocks:

| Currently silent step | What memory reading would expose |
|---|---|
| Talk to Greirat (pre-rescue) | Dialogue flag fires immediately |
| Send Greirat to scavenge | Quest state flag 1421 (recruited) → 1422+ |
| Talk to Irina in sewer | Dialogue flag → can trigger tip before quit |
| Yoel free-level draws mid-session | Hollowing + Dark Sigil flag in real time |
| NPC killed without saving | Death flag visible before next bonfire |

### Option A: External process memory reading (recommended starting point)

No mod, no DLL injection. Read the DS3 process RAM from Python via `pymem`.

```python
import pymem
pm = pymem.Pymem("DarkSoulsIII.exe")
# read a u32 at a known base + offset chain
value = pymem.process.read_int(pm.process_handle, base + offset)
```

- The DS3 community has documented most critical offsets via Cheat Engine tables (event flags, player stats, position, NPC quest states).
- Poll on a timer; compare against previous read to emit events.
- Integrates cleanly alongside the existing save file watcher — run both in parallel.
- **EAC**: never run while connected to multiplayer. Offline/single-player: safe.

**Key library**: `pymem` (pip). Alternative: `pyMeow` (wraps Frida).

### Option B: DLL injection mod

Inject a DLL into DS3 via **Mod Engine 2**. Hook game functions to get push-style callbacks on events instead of polling.

- More accurate event timing; zero polling overhead.
- Significantly more complex: need to reverse-engineer DS3 function signatures.
- Use only if Option A's polling latency proves insufficient (unlikely for this use case).

### Integration plan (when ready to implement)

1. Install `pymem` in the venv.
2. Build a `memory_reader.py` module: find DS3 base address, walk pointer chains to the event-flag region and NPC state arrays.
3. Poll every 200–500ms in a background thread; emit events when a flag transitions 0→1.
4. Feed events into the same `advisor.get_tips()` pipeline the watcher uses.
5. Optionally suppress the save-file watcher's flag diff when memory reader is active (to avoid double-reporting).

### Resources for offset research

- **DS3 Cheat Engine tables** (community-maintained) — document player stats, event flags, NPC state machine ranges, position, enemy HP.
- **SpeedSouls / DS3 practice tools** — open source, read DS3 memory directly; good code reference.
- **EMEVD flag ranges** already in `data/_emevd_flags.json` — NPC state machine IDs are the primary targets.
