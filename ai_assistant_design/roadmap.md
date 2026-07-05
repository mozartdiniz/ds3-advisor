# Roadmap

> **2026-06-11: the event-flag blocker is solved.** Flags are read structurally
> and semantically (see [flag_research.md](flag_research.md)); NPC quest events
> (Greirat, Yoel/Yuria, Irina/Eygon, Hodrick, Leonhard, Cornyx, Siegward) now
> surface in the simulator/watcher. The roadmap below is reordered accordingly.

---

## Where we left off (2026-06-11, session 11 — parked)

The advisor was refactored into the hybrid pipeline (deterministic engine +
Claude agent + topic dedupe) — full description in
[advisor_and_tips.md → Advisor pipeline](advisor_and_tips.md), change log in
[session_log.md → Session 11](session_log.md). Content coverage and
validation both stop at **Undead Settlement** (the user's validated progress).

State: quest-track (12 saves) and play_00 (40 saves) replays clean; pytest
23 passed / 13 skipped; deterministic output reviewed step-by-step and
duplicate beats resolved via topics.

**Resume checklist:**

1. **Live-test the LLM layer** — never exercised against the real API (no
   key in the dev shell). With `ANTHROPIC_API_KEY` set:
   `python play_simulator.py quest-track --slot 4 --llm` first, then
   `python watcher.py` during real play. Review: message tone (retrospective
   vs urgent), ≤2-message cap, tool usage (get_quest_status / search_wiki),
   prompt-cache hits (`usage.cache_read_input_tokens` > 0 from the 2nd call).
2. **Author checkpoints for the next areas** (Road of Sacrifices, Cathedral,
   Farron Keep) in `data/checkpoints.json` as the player progresses — or via
   the transcript extraction (item 3 below). Remember: `policy` per
   checkpoint, shared `topic` when it overlaps a decision-file beat.
3. Items 1–7 below (KNOWN_FLAGS expansion is still the highest-value data
   work — Greirat outings 2–3 flags directly feed the Irithyll warnings the
   quest files already contain as placeholders).

---

## Recommended next steps (in priority order)

1. **Expand KNOWN_FLAGS along the prevent-regret questlines** — controlled save
   pairs now yield semantic IDs directly (`scripts/diff_controlled_saves.py`).
   Highest value targets:
   - Greirat outings 2–3: sent-to-Irithyll, returned, dead (commons 1227+?,
     talk flags; needed for the Siegward/Patches rescue warnings).
   - Sirris, Anri/Horace, Orbeck, Karla, Patches first-talk + quest steps.
   - Eygon hostility, Irina dark-tome corruption states.
   - Confirm the mid/late-game boss IDs (Dancer 13000890, Oceiros 13000830,
     Twin Princes 13410830, Nameless King 13200850, Champion Gundyr 14000830)
     with one kill each.

2. **Use bonfire-lit flags for area detection** — `data/_bonfire_flags.json`
   LocationEventIds are directly readable now; richer than the single
   "last bonfire" userdata field (e.g. tips keyed to "lit but not yet cleared"
   areas).

3. **Extract checkpoints from FightinCowboy transcript via one LLM call**
   (`scripts/extract_tips_from_transcript.py`) — target schema is now
   `data/checkpoints.json` (policy: retrospective / proactive / reactive —
   see [advisor_and_tips.md](advisor_and_tips.md)); checkpoints can reference
   real flag IDs for both `has_flags` and `missing_flags`.

4. **Mine `data/*.csv` for build-aware item tips** (code only,
   `scripts/build_tips_from_csv.py`).

5. **Quest evaluator content** — fill remaining `decision_making_files/*.json`
   phases with the now-readable flag registry entries; add Sirris, Siegward,
   Anri questline files.

6. **Small parser fields** — item-registry walker (the gaitem walk in
   `parser/flags.py` already parses its structure — surface items from it),
   hollowing count, NG cycle, deaths.

7. **Live memory reading (pymem)** — still the path to real-time (sub-second)
   NPC event detection between saves; the semantic flag IDs and the TGA CT
   pointer chains share the same ID space, so KNOWN_FLAGS transfers as-is.

---

## Open questions

- License/attribution: the structural walk constants come from alfizari's
  GPL-3 editor; the offset tables from the TGA cheat table. Fine for personal
  use; re-evaluate before redistribution.
- Which maps occupy the unidentified block slots (3, 5, 7, 10, 11, 18, 19…)
  and the regions between 0x8200–0x1FE00 (suspected type-5 loot flags) — only
  needed if we want item-pickup flags (inventory diffing covers most of that).
