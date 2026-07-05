"""advisor_agent.py - LLM layer of the advisor.

The deterministic engine (advisor_core) decides WHAT is worth saying; this
module decides HOW to say it. It is only invoked when a save event produced
new findings, so most save events cost zero tokens.

The agent gets the save-event context + findings and can call back into the
deterministic code (state summary, quest status, area checklist, wiki search)
before writing at most two short player-facing messages.

Requires ANTHROPIC_API_KEY (or any credential the anthropic SDK resolves).
When unavailable, phrase() returns None and callers fall back to the
deterministic rendering in advisor_core.format_findings().
"""
from __future__ import annotations

import json
import os
from typing import Optional

import advisor_core
from advisor_core import AdvisorEngine, AdvisorReport

MODEL = os.environ.get("DS3_ADVISOR_MODEL", "claude-opus-4-8")
MAX_TOKENS = 1024

# Module-level context the tools read. Set by phrase() before each run so the
# tool list stays byte-identical across calls (keeps the prompt cache warm).
_CTX: dict = {"engine": None, "snap": None}

SYSTEM = """You are a Dark Souls 3 companion watching the player's save file. \
You speak to the player between bonfire rests, like a knowledgeable friend \
watching them play - never like a walkthrough.

You receive a save event: what just changed, plus FINDINGS produced by a \
deterministic rule engine. Findings are pre-validated against the save file - \
treat them as ground truth about what the player has and hasn't done.

Rules:
- Write at MOST 2 short messages (a few sentences each), as plain paragraphs \
separated by a blank line. Often 1 is enough.
- Pick what matters most: quest-breaking warnings ALWAYS come first, then \
missed content, then quest steps. Drop the rest - unmentioned findings will \
be resurfaced later by the engine if still relevant.
- Missed-content findings are retrospective: the player already moved past \
the area. Tone: "by the way, back in <area> you missed..." plus how to go \
back. Never scold.
- Quest warnings are the one case to be direct and urgent: say exactly what \
breaks and what to do RIGHT NOW to avoid it.
- NEVER spoil content ahead of the player's position beyond what a finding \
itself says. No future bosses, areas, or plot.
- Ground every game fact in the findings or in tool results. If you want \
extra color (item location detail, quest nuance), call search_wiki or \
get_quest_status first - do not rely on memory for specifics.
- React to milestones in the events naturally (a boss kill deserves a quick \
nod) but only if you are already sending a message.
- Do not repeat advice listed in recently_delivered.
- Output ONLY the player-facing messages. No preamble, no headers, no lists \
of findings, no meta-commentary."""


def _tools():
    """Build the tool list (closures over _CTX via module globals)."""
    from anthropic import beta_tool

    @beta_tool
    def get_player_state() -> str:
        """Get the player's current state: level, build, stats, last bonfire,
        key items, and which quest/boss flags are set."""
        return _CTX["engine"].state_summary(_CTX["snap"])

    @beta_tool
    def get_quest_status(quest: str) -> str:
        """Get the evaluated status of an NPC questline (current phase, next
        steps, active warnings).

        Args:
            quest: Quest or NPC name, e.g. "greirat", "irina", "yoel".
        """
        return _CTX["engine"].quest_status(quest, _CTX["snap"])

    @beta_tool
    def get_area_checklist(area: str) -> str:
        """List all known checkpoints for a game area and whether each is
        still open for this player.

        Args:
            area: Area name, e.g. "Undead Settlement", "High Wall of Lothric".
        """
        return _CTX["engine"].area_checklist(area, _CTX["snap"])

    @beta_tool
    def search_wiki(query: str) -> str:
        """Search the local Dark Souls 3 wiki dump for item locations, NPC
        questline details, boss info, etc. Returns top page snippets.

        Args:
            query: Search terms, e.g. "Loretta bone location", "Yoel of Londor".
        """
        return advisor_core.search_wiki(query)

    return [get_player_state, get_quest_status, get_area_checklist, search_wiki]


_TOOLS = None


def _get_client():
    try:
        import anthropic
    except ImportError:
        return None
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        # let the SDK try its other credential sources, but don't crash later
        try:
            return anthropic.Anthropic()
        except Exception:
            return None
    return anthropic.Anthropic()


def llm_available() -> bool:
    return _get_client() is not None


def phrase(report: AdvisorReport, engine: AdvisorEngine) -> Optional[str]:
    """Turn a report with findings into 1-2 player-facing messages via Claude.

    Returns None when the LLM is unavailable or errors - callers should fall
    back to advisor_core.format_findings(report.findings).
    """
    global _TOOLS
    if not report.findings:
        return None

    client = _get_client()
    if client is None:
        return None

    _CTX["engine"] = engine
    _CTX["snap"] = report.snapshot
    if _TOOLS is None:
        _TOOLS = _tools()

    payload = {
        "save_event": report.events,
        "findings": [f.to_dict() for f in report.findings],
        "quest_phase_changes": report.quest_phase_changes,
        "recently_delivered": report.memory.data.get("recent_advice", []),
        "recent_events": report.memory.data.get("recent_events", [])[-15:],
    }

    try:
        runner = client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[{
                "type": "text",
                "text": SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=_TOOLS,
            messages=[{
                "role": "user",
                "content": json.dumps(payload, indent=1),
            }],
        )
        last = None
        for message in runner:
            last = message
        if last is None:
            return None
        text = "\n".join(
            b.text for b in last.content if b.type == "text").strip()
        return text or None
    except Exception as e:
        print("  [advisor LLM unavailable: %s]" % e)
        return None
