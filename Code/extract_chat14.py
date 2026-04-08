"""Extract Chat 14 - corrected for new JSONL format.

The JSONL format stores:
- Line 0: session metadata with initial request in requests[]
- Subsequent lines: incremental updates (v is either a dict or list)
- AI text comes as list items without 'kind' field that have 'value' key
- User messages come as dicts with 'message.text'
"""
import json
import os

SRC = r'REDACTED_PATH\AppData\Roaming\Code\User\workspaceStorage\bc015ee5f3eb128bf42e6031cbcd03ba\chatSessions\f3c3c655-5048-4a8e-b9a0-774f5aa63559.jsonl'
DST = r'REDACTED_PATH\OneDrive\Vibe\BuildDavis\Chat14.txt'

with open(SRC, 'r', encoding='utf-8', errors='replace') as f:
    raw_lines = [l.strip() for l in f if l.strip()]

print(f"Total JSONL lines: {len(raw_lines)}")

entries = []  # (line_idx, type, text)

for li, raw in enumerate(raw_lines):
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        continue
    
    v = d.get('v')
    if v is None:
        continue
    
    # Line 0 has session structure with requests
    if isinstance(v, dict) and 'requests' in v:
        for req in v['requests']:
            msg = req.get('message', {})
            if isinstance(msg, dict):
                txt = msg.get('text', '')
                if txt.strip():
                    entries.append((li, 'USER', txt))
            resp = req.get('response', [])
            if isinstance(resp, list):
                for item in resp:
                    if isinstance(item, dict):
                        kind = item.get('kind', '')
                        if not kind and 'value' in item:
                            val = item['value']
                            if isinstance(val, str) and val.strip():
                                entries.append((li, 'AI', val))
                        elif kind == 'markdownContent':
                            c = item.get('content', {})
                            val = c.get('value', '') if isinstance(c, dict) else str(c)
                            if val.strip():
                                entries.append((li, 'AI', val))
        continue
    
    # Dict with value (text content or user message)
    if isinstance(v, dict):
        if 'value' in v:
            val = v['value']
            if isinstance(val, str) and val.strip() and len(val) > 5:
                entries.append((li, 'AI', val))
        if 'message' in v and isinstance(v['message'], dict):
            txt = v['message'].get('text', '')
            if txt.strip():
                entries.append((li, 'USER', txt))
    
    # List of items
    if isinstance(v, list):
        for item in v:
            if not isinstance(item, dict):
                continue
            
            # User message stored in list item
            if 'message' in item and isinstance(item['message'], dict):
                txt = item['message'].get('text', '')
                if txt.strip():
                    entries.append((li, 'USER', txt))
            # Also check request.message pattern
            if 'request' in item and isinstance(item['request'], dict):
                req = item['request']
                if 'message' in req and isinstance(req['message'], dict):
                    txt = req['message'].get('text', '')
                    if txt.strip():
                        entries.append((li, 'USER', txt))
            
            kind = item.get('kind', '')
            if kind in ('toolInvocationSerialized', 'thinking', 'progressTaskSerialized',
                        'steering', 'mcpServersStarting', 'inlineReference', 'questionCarousel'):
                continue
            if not kind and 'value' in item:
                val = item['value']
                if isinstance(val, str) and val.strip():
                    entries.append((li, 'AI', val))
            if kind == 'markdownContent':
                c = item.get('content', {})
                val = c.get('value', '') if isinstance(c, dict) else str(c)
                if val.strip():
                    entries.append((li, 'AI', val))

user_count = sum(1 for _, t, _ in entries if t == 'USER')
ai_count = sum(1 for _, t, _ in entries if t == 'AI')
print(f"User messages: {user_count}")
print(f"AI response parts: {ai_count}")

with open(DST, 'w', encoding='utf-8') as of:
    of.write("# Chat 14: Platform Decision (Java+Geyser), WorldWarden Planning, Immersive Audio Research\n\n")
    of.write("Key decisions this session:\n")
    of.write("- Reversed Chat 13's Bedrock decision -> Java + Geyser (all consoles supported)\n")
    of.write("- WorldWarden (full WorldGuard port for BDS) scoped and deferred (Microsoft OSS)\n")
    of.write("- DavisAudio custom plugin architecture designed (WorldGuard SessionHandler + OGG sounds)\n")
    of.write("- Two-track plan: Track A = BuildDavis Tour Server, Track B = WorldWarden (deferred)\n\n")
    
    prev_type = None
    for ln, typ, txt in entries:
        if typ == 'USER' and prev_type != 'USER':
            of.write(f"\n{'='*60}\nUSER (line {ln}):\n{'='*60}\n")
            of.write(txt[:8000] + "\n")
        elif typ == 'USER':
            of.write(txt[:8000] + "\n")
        elif typ == 'AI' and prev_type != 'AI':
            of.write(f"\n--- AI Response (line {ln}) ---\n")
            of.write(txt[:15000] + "\n")
        else:
            of.write(txt[:15000] + "\n")
        prev_type = typ

size_kb = os.path.getsize(DST) / 1024
print(f"Written to {DST} ({size_kb:.1f} KB)")
