# DS3 AI Companion — Design Notes Index

Split from `ai_assistant_design.md` (repo root). Each file covers a focused topic.

---

## Files

| File | What you'll find there |
|------|------------------------|
| [vision.md](vision.md) | Project vision, why DS3, save-file capabilities and limitations |
| [parser_reference.md](parser_reference.md) | File map, run commands, slot field offsets, current parser capabilities, still-to-map items |
| [flag_research.md](flag_research.md) | Event-flag architecture (SOLVED 2026-06-11): structural walk, semantic flag-ID codec, validated KNOWN_FLAGS |
| [advisor_and_tips.md](advisor_and_tips.md) | Advisor pipeline (deterministic engine + Claude agent, session 11), checkpoint policies, reasoner rules, suggestion catalog (A–H), v1 scope |
| [architecture.md](architecture.md) | Transport/storage/UX decisions, deferred items, live memory reading plan |
| [roadmap.md](roadmap.md) | Next steps in priority order, pending work, open questions |
| [resources.md](resources.md) | External links, local data inventory, DS1 prototype reference |
| [session_log.md](session_log.md) | Chronological per-session notes (sessions 2–9, 2026-05-27 to 2026-05-31) |
| [gotchas.md](gotchas.md) | Runtime gotchas, controlled-saves workflow |
| [controlled_saves_protocol.md](controlled_saves_protocol.md) | Capture protocol for controlled save pairs (save discipline, checkpoint sequence, info.txt format) |

---

## Quick lookup

| Looking for... | Go to |
|----------------|-------|
| How to run the POC | [parser_reference.md → Working POC pipeline](parser_reference.md) |
| Directory / file structure | [parser_reference.md → File map](parser_reference.md) |
| Parser field offsets table | [parser_reference.md → Parser progress](parser_reference.md) |
| What the parser can currently extract | [parser_reference.md → What the parser extracts today](parser_reference.md) |
| Items not yet parsed | [parser_reference.md → Still to map](parser_reference.md) |
| How event flags work in DS3 | [flag_research.md → The working model](flag_research.md) |
| What flag ID corresponds to what event | [flag_research.md → Validated flag IDs](flag_research.md) |
| How to label a new flag (controlled saves) | [flag_research.md → Workflow](flag_research.md) |
| What the reasoner currently fires | [advisor_and_tips.md → Reasoner rules](advisor_and_tips.md) |
| Checkpoint schema + policies (retrospective/proactive/reactive) | [advisor_and_tips.md → Advisor pipeline](advisor_and_tips.md) |
| Full suggestion catalog (120–180 target rules) | [advisor_and_tips.md → Suggestion catalog](advisor_and_tips.md) |
| Why we chose DS3 over DS1/DS2/Elden Ring | [vision.md → Game choice](vision.md) |
| Why we send raw .sl2 to server in v0 | [architecture.md → Parsing & transport](architecture.md) |
| Live memory reading plan (pymem) | [architecture.md → Live Memory Reading](architecture.md) |
| Interactive agent / v1 chat plan | [architecture.md → Deferred to post-v0](architecture.md) |
| What to build next | [roadmap.md](roadmap.md) |
| External tools and repos (DSMapStudio, alfizari, etc.) | [resources.md → Public resources](resources.md) |
| Python version, AES key, save file paths | [gotchas.md](gotchas.md) |
| What happened in session N | [session_log.md](session_log.md) |
