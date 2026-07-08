"""Download transcripts for FightinCowboy's DS3 100% walkthrough playlist.

Playlist: PL7RtZMiaOk8gqctsEgBQ9IhQAnm_P5ILT (16 episodes)

Each transcript is saved to data/transcripts/fightincowboy/ep_NN_<video_id>.txt
as one line per caption snippet, prefixed with a [hh:mm:ss] timestamp so the
progression order survives for later tip mining.

Usage (from ai_assistant/):
    python scripts/fetch_fightincowboy_transcripts.py            # all episodes
    python scripts/fetch_fightincowboy_transcripts.py 3 7        # only eps 3 and 7
"""
import sys
import time
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (episode number, video id) — playlist order
EPISODES = [
    (1,  "2ZnFfnQeihc"),
    (2,  "ozQY4CypZy0"),
    (3,  "nfoxbcwYx3E"),
    (4,  "1c1QCAYs1yE"),
    (5,  "eQgLrtKlZdg"),
    (6,  "u5kDCOgmCxw"),
    (7,  "rfXHAC-nU8Y"),
    (8,  "6hQiF4pJ6uk"),
    (9,  "p15oQOm52XU"),
    (10, "V7DIjNXN0Wc"),
    (11, "j9t3uALAGbU"),
    (12, "D3eFRfG_WgE"),
    (13, "5camcsrwBU4"),
    (14, "QTHovXsM6OU"),
    (15, "Hl8M6LyxPlc"),
    (16, "r4v5qZBERb4"),
]

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "transcripts" / "fightincowboy"


def fetch_snippets(video_id: str):
    """Return a list of (start_seconds, text), across old and new API versions."""
    if hasattr(YouTubeTranscriptApi, "get_transcript"):        # pre-1.0 API
        raw = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        return [(item["start"], item["text"]) for item in raw]
    fetched = YouTubeTranscriptApi().fetch(video_id, languages=["en"])  # 1.x API
    return [(s.start, s.text) for s in fetched]


def hms(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def main() -> int:
    only = {int(a) for a in sys.argv[1:]} or None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failed = []

    for ep, video_id in EPISODES:
        if only and ep not in only:
            continue
        out = OUT_DIR / f"ep_{ep:02d}_{video_id}.txt"
        if out.exists():
            print(f"ep {ep:02d}: already downloaded ({out.name}), skipping")
            continue
        try:
            snippets = fetch_snippets(video_id)
        except Exception as e:  # noqa: BLE001 — report and continue with the rest
            print(f"ep {ep:02d}: FAILED for {video_id}: {e}")
            failed.append(ep)
            continue
        lines = [f"[{hms(start)}] {text.replace(chr(10), ' ')}" for start, text in snippets]
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"ep {ep:02d}: {len(snippets):5d} snippets -> {out.name}")
        time.sleep(2)  # stay under YouTube's rate limits

    if failed:
        print(f"\nFailed episodes: {failed} — re-run with those numbers as args to retry.")
        return 1
    print("\nAll requested transcripts downloaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
