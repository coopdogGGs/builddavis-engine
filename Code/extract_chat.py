"""Extract user messages and AI responses from VS Code Copilot chat JSONL session."""
import json
import sys

SRC = r'REDACTED_PATH\AppData\Roaming\Code\User\workspaceStorage\bc015ee5f3eb128bf42e6031cbcd03ba\chatSessions\3d5d785f-9ee8-4f48-bc81-42e400354c23.jsonl'
DST = r'REDACTED_PATH\OneDrive\Vibe\BuildDavis\Chat4.txt'

print("Reading JSONL...")
all_requests = []
line_num = 0
with open(SRC, 'r', encoding='utf-8', errors='replace') as fh:
    for raw_line in fh:
        line_num += 1
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            data = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        
        # Kind 0 = session header with requests array
        if isinstance(data, dict) and data.get('kind') == 0:
            v = data.get('v', {})
            reqs = v.get('requests', [])
            all_requests.extend(reqs)
            print(f"  Line {line_num}: session header with {len(reqs)} requests")
        
        # Kind 2 = incremental request additions
        elif isinstance(data, dict) and data.get('kind') == 2:
            v = data.get('v', {})
            if isinstance(v, dict):
                reqs = v.get('requests', [])
                all_requests.extend(reqs)
                if reqs:
                    print(f"  Line {line_num}: {len(reqs)} incremental requests")
            elif isinstance(v, list):
                # v is a list of ops
                for op in v:
                    if isinstance(op, dict) and 'requests' in op:
                        reqs = op['requests']
                        all_requests.extend(reqs)
                        print(f"  Line {line_num}: {len(reqs)} requests from op")

print(f"Total lines: {line_num}")
requests = all_requests
print(f"Total requests extracted: {len(requests)}")

with open(DST, 'w', encoding='utf-8') as of:
    of.write("# Chat 4: Exploring Additional POCs for Issue Identification\n\n")
    
    for i, req in enumerate(requests):
        # User message
        msg = req.get('message', {})
        if isinstance(msg, dict):
            text = msg.get('text', '')
        elif isinstance(msg, str):
            text = msg
        else:
            text = str(msg)
        
        if text and len(text.strip()) > 0:
            of.write(f"--- USER {i+1} ---\n")
            of.write(text[:8000] + "\n\n")
        
        # AI response
        resp = req.get('response', [])
        if isinstance(resp, list):
            for part in resp:
                if isinstance(part, dict) and part.get('kind') == 'markdownContent':
                    val = part.get('content', {}).get('value', '')
                    if val and len(val.strip()) > 0:
                        of.write(val[:15000] + "\n\n")
        elif isinstance(resp, dict):
            val = resp.get('value', resp.get('text', ''))
            if val:
                of.write(str(val)[:15000] + "\n\n")

print(f"Written to {DST}")

# Show file size
import os
size = os.path.getsize(DST)
print(f"Output size: {size/1024:.1f} KB")
