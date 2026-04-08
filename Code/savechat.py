"""savechat.py — Auto-extract current VS Code Copilot chat to ChatN.txt.

Finds the most recently modified JSONL session file, determines the next
Chat number, extracts USER/AI messages, and writes the transcript.

Usage:
    python Code/savechat.py
    python Code/savechat.py --title "Station Placement Fix"
    python Code/savechat.py --session f43759ec-35c3-4e8d-b93c-842a1baa613e
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

SESSIONS_DIR = Path(
    r"REDACTED_PATH\AppData\Roaming\Code\User\workspaceStorage"
    r"\bc015ee5f3eb128bf42e6031cbcd03ba\chatSessions"
)
WORKSPACE = Path(r"REDACTED_PATH\OneDrive\Vibe\BuildDavis")

SKIP_KINDS = frozenset({
    "toolInvocationSerialized", "thinking", "progressTaskSerialized",
    "steering", "mcpServersStarting", "inlineReference",
    "questionCarousel", "codeblockUri", "agentDetection",
    "usedContext", "toolInvocationMessage",
})


def find_latest_session(session_id: str | None = None) -> Path:
    """Return the JSONL file to extract."""
    if session_id:
        p = SESSIONS_DIR / f"{session_id}.jsonl"
        if not p.exists():
            sys.exit(f"Session not found: {p}")
        return p
    jsonls = sorted(
        SESSIONS_DIR.glob("*.jsonl"),
        key=lambda p: (p.stat().st_mtime, p.stat().st_size),
        reverse=True,
    )
    if not jsonls:
        sys.exit(f"No .jsonl files in {SESSIONS_DIR}")
    return jsonls[0]


def next_chat_number() -> int:
    """Scan workspace root for ChatN.txt and return next N."""
    existing = set()
    for f in WORKSPACE.glob("Chat*.txt"):
        # Also handle chat1.txt (lowercase) and Chat5_continued.txt
        m = re.match(r"[Cc]hat(\d+)", f.stem)
        if m:
            existing.add(int(m.group(1)))
    if not f or not existing:
        return 1
    return max(existing) + 1


def extract_entries(jsonl_path: Path) -> list[tuple[int, str, str]]:
    """Parse JSONL and return (line_idx, 'USER'|'AI', text) entries."""
    with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
        raw_lines = [l.strip() for l in f if l.strip()]

    entries: list[tuple[int, str, str]] = []

    def add_text(li: int, role: str, val):
        if isinstance(val, str) and val.strip() and len(val.strip()) > 2:
            entries.append((li, role, val))

    def process_response_items(li: int, items):
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            kind = item.get("kind", "")
            if kind in SKIP_KINDS:
                continue
            if not kind and "value" in item:
                add_text(li, "AI", item["value"])
            elif kind == "markdownContent":
                c = item.get("content", {})
                val = c.get("value", "") if isinstance(c, dict) else str(c)
                add_text(li, "AI", val)

    for li, raw in enumerate(raw_lines):
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            continue

        v = d.get("v")
        if v is None:
            continue

        # Line 0: session structure with requests[]
        if isinstance(v, dict) and "requests" in v:
            for req in v["requests"]:
                msg = req.get("message", {})
                if isinstance(msg, dict):
                    add_text(li, "USER", msg.get("text", ""))
                process_response_items(li, req.get("response", []))
            continue

        # Dict with value or message
        if isinstance(v, dict):
            if "value" in v:
                add_text(li, "AI", v["value"])
            if "message" in v and isinstance(v["message"], dict):
                add_text(li, "USER", v["message"].get("text", ""))

        # List of items
        if isinstance(v, list):
            for item in v:
                if not isinstance(item, dict):
                    continue
                # User message
                if "message" in item and isinstance(item["message"], dict):
                    add_text(li, "USER", item["message"].get("text", ""))
                if "request" in item and isinstance(item["request"], dict):
                    req = item["request"]
                    if "message" in req and isinstance(req["message"], dict):
                        add_text(li, "USER", req["message"].get("text", ""))
                # AI content
                kind = item.get("kind", "")
                if kind in SKIP_KINDS:
                    continue
                if not kind and "value" in item:
                    add_text(li, "AI", item["value"])
                if kind == "markdownContent":
                    c = item.get("content", {})
                    val = c.get("value", "") if isinstance(c, dict) else str(c)
                    add_text(li, "AI", val)

    return entries


def write_transcript(entries, dst: Path, title: str, chat_num: int):
    """Write formatted transcript to file."""
    user_count = sum(1 for _, t, _ in entries if t == "USER")
    ai_count = sum(1 for _, t, _ in entries if t == "AI")

    with open(dst, "w", encoding="utf-8") as f:
        f.write(f"# Chat {chat_num}: {title}\n\n")
        f.write(f"Extracted: {user_count} user messages, {ai_count} AI response parts\n\n")

        prev_type = None
        for ln, typ, txt in entries:
            if typ == "USER" and prev_type != "USER":
                f.write(f"\n{'='*60}\nUSER (line {ln}):\n{'='*60}\n")
                f.write(txt[:8000] + "\n")
            elif typ == "USER":
                f.write(txt[:8000] + "\n")
            elif typ == "AI" and prev_type != "AI":
                f.write(f"\n--- AI Response (line {ln}) ---\n")
                f.write(txt[:15000] + "\n")
            else:
                f.write(txt[:15000] + "\n")
            prev_type = typ

    return dst.stat().st_size


def main():
    parser = argparse.ArgumentParser(description="Save current chat to ChatN.txt")
    parser.add_argument("--title", default="Untitled Session", help="Short title for this chat")
    parser.add_argument("--session", default=None, help="Specific session UUID (omit to use most recent)")
    args = parser.parse_args()

    src = find_latest_session(args.session)
    chat_num = next_chat_number()
    dst = WORKSPACE / f"Chat{chat_num}.txt"

    print(f"Source:  {src.name} ({src.stat().st_size / 1024:.1f} KB)")
    print(f"Output:  {dst.name} (Chat #{chat_num})")

    entries = extract_entries(src)
    size = write_transcript(entries, dst, args.title, chat_num)

    user_count = sum(1 for _, t, _ in entries if t == "USER")
    ai_count = sum(1 for _, t, _ in entries if t == "AI")

    print(f"\nSaved {user_count} user + {ai_count} AI messages → {dst.name} ({size / 1024:.1f} KB)")
    print(f"\nReminders:")
    print(f"  - Update Code/PHASE4_ISSUES.md if you found new issues")
    print(f"  - Update project state memory if POC status changed")


if __name__ == "__main__":
    main()
