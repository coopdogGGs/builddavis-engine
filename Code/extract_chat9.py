"""Extract chat messages from VS Code Copilot JSONL - Chat 9.

JSONL format (2025+):
  Line 0 (kind=0): Full initial state with requests[0]
  kind=2, k=['requests']: Append new request(s)
  kind=2, k=['requests', N, 'response']: Append response parts to request N
  kind=1, k=[...]: Set/replace a value at path
"""
import json
import os

SRC = r'REDACTED_PATH\AppData\Roaming\Code\User\workspaceStorage\bc015ee5f3eb128bf42e6031cbcd03ba\chatSessions\c4d377c8-8b90-4ce7-bb76-bc5266a2577b.jsonl'
DST = r'REDACTED_PATH\OneDrive\Vibe\BuildDavis\Chat9.txt'

print("Scanning JSONL lines...")

# Reconstruct requests: list of {message, response_parts}
requests = []

with open(SRC, 'r', encoding='utf-8', errors='replace') as fh:
    for i, line in enumerate(fh):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue

        kind = d.get('kind')
        k = d.get('k', [])
        v = d.get('v')

        if kind == 0 and isinstance(v, dict) and 'requests' in v:
            # Initial state - extract first request(s)
            for req in v['requests']:
                msg = req.get('message', {})
                txt = msg.get('text', '') if isinstance(msg, dict) else ''
                resp = req.get('response', [])
                requests.append({'message': txt, 'response': resp if isinstance(resp, list) else []})

        elif kind == 2 and k == ['requests'] and isinstance(v, list):
            # Appending new request(s)
            for req in v:
                if isinstance(req, dict):
                    msg = req.get('message', {})
                    txt = msg.get('text', '') if isinstance(msg, dict) else ''
                    resp = req.get('response', [])
                    requests.append({'message': txt, 'response': resp if isinstance(resp, list) else []})

        elif kind == 2 and isinstance(k, list) and len(k) == 3 and k[0] == 'requests' and k[2] == 'response':
            # Appending response parts to request k[1]
            idx = k[1]
            if idx < len(requests) and isinstance(v, list):
                requests[idx]['response'].extend(v)

        elif kind == 1 and isinstance(k, list) and len(k) >= 2 and k[0] == 'requests':
            # Set/replace at path - handle response overwrites
            idx = k[1]
            if idx < len(requests) and len(k) == 3 and k[2] == 'response' and isinstance(v, list):
                requests[idx]['response'] = v

print(f"Found {len(requests)} requests")

# Extract AI text from response parts
def extract_ai_text(response_parts):
    """Pull visible text from response parts list."""
    texts = []
    for part in response_parts:
        if not isinstance(part, dict):
            continue
        kind = part.get('kind', '')
        value = part.get('value', '')
        if kind == '' and isinstance(value, str) and value.strip():
            texts.append(value.strip())
        elif kind == 'markdownContent':
            content = part.get('content', {})
            if isinstance(content, dict):
                val = content.get('value', '')
            elif isinstance(content, str):
                val = content
            else:
                val = ''
            if val.strip():
                texts.append(val.strip())
    return '\n\n'.join(texts)

# Write transcript
with open(DST, 'w', encoding='utf-8') as of:
    of.write("# Chat 9: Sector-Based World Architecture & Tier 2D Landmarks\n\n")

    for i, req in enumerate(requests):
        user_text = req['message'].strip()
        ai_text = extract_ai_text(req['response'])

        of.write(f"\n{'='*60}\n")
        of.write(f"USER (request {i}):\n")
        of.write(f"{'='*60}\n")
        of.write(user_text[:8000] + "\n")

        if ai_text:
            of.write(f"\n--- AI Response ---\n")
            of.write(ai_text[:30000] + "\n")
        else:
            of.write(f"\n--- AI Response ---\n(no text extracted)\n")

print(f"Written to {DST} ({os.path.getsize(DST)/1024:.1f} KB)")
