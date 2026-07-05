"""advisor.py - orchestrates the DS3 advisor pipeline for one character.

    save event (watcher / simulator)
        -> advisor_core.AdvisorEngine.process()   deterministic, zero tokens
        -> gate: no new findings -> say nothing   (most save events end here)
        -> advisor_agent.phrase()                 Claude phrases 1-2 messages
           (falls back to deterministic text when no API key / LLM disabled)

Usage as a library:

    from advisor import AdvisorSession
    session = AdvisorSession(char_key="Greirat_slot5", use_llm=True)
    text = session.on_save_event(prev_snap, curr_snap)   # None = stay silent

Standalone (one-shot analysis of a save file):

    python advisor.py <save.sl2> [slot] [--llm]
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from snapshot import SlotSnap
from advisor_core import AdvisorEngine, SessionMemory, format_findings
import advisor_agent


class AdvisorSession:
    """Holds the engine + per-character memory across save events."""

    def __init__(self, char_key: str, use_llm: bool = True, persist: bool = True):
        self.engine = AdvisorEngine()
        self.memory = SessionMemory(char_key, persist=persist)
        self.use_llm = use_llm

    def on_save_event(self, prev: Optional[SlotSnap], curr: SlotSnap) -> Optional[str]:
        """Process one save event. Returns advisor text to show, or None."""
        report = self.engine.process(prev, curr, self.memory)

        if not report.findings:
            self.memory.save()
            return None

        text = None
        if self.use_llm:
            text = advisor_agent.phrase(report, self.engine)
        if text is None:
            text = format_findings(report.findings)

        self.memory.mark_delivered(report.findings)
        self.memory.save()
        return text or None


# ---------------------------------------------------------------------------
# Standalone: analyse a single save file (no prior state)
# ---------------------------------------------------------------------------

def main() -> None:
    from snapshot import snap_slot

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_llm = "--llm" in sys.argv

    if not args:
        print("Usage: python advisor.py <save.sl2> [slot] [--llm]")
        sys.exit(1)

    sl2 = Path(args[0])
    slot_idx = int(args[1]) if len(args) > 1 else 4

    curr = snap_slot(sl2, slot_idx)
    if curr is None:
        print("Slot %d not occupied." % slot_idx)
        sys.exit(1)

    session = AdvisorSession(char_key="cli_%s_slot%d" % (curr.name, slot_idx),
                             use_llm=use_llm, persist=False)

    print("\nCharacter: %s  Level %d  |  %s" % (
        curr.name, curr.level, curr.bonfire_name or curr.bonfire_id))

    text = session.on_save_event(None, curr)
    if text:
        print("\n=== ADVISOR ===\n")
        print(text)
    else:
        print("\nNothing to say for the current state.")


if __name__ == "__main__":
    main()
