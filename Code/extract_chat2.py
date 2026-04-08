"""Extract chat messages from VS Code Copilot JSONL - approach 2."""
import json
import sys

SRC = r'REDACTED_PATH\AppData\Roaming\Code\User\workspaceStorage\bc015ee5f3eb128bf42e6031cbcd03ba\chatSessions\3d5d785f-9ee8-4f48-bc81-42e400354c23.jsonl'
DST = r'REDACTED_PATH\OneDrive\Vibe\BuildDavis\Chat4.txt'

user_msgs = []
ai_parts = []

print("Scanning JSONL lines...")
with open(SRC, 'r', encoding='utf-8', errors='replace') as fh:
    for i, line in enumerate(fh):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        
        v = d.get('v', None)
        if v is None:
            continue
        
        # Walk the structure looking for user messages and AI content
        def extract_from(obj, line_num):
            if not isinstance(obj, (dict, list)):
                return
            if isinstance(obj, dict):
                # User message text
                if 'message' in obj and isinstance(obj['message'], dict):
                    txt = obj['message'].get('text', '')
                    if txt and len(txt.strip()) > 0:
                        user_msgs.append((line_num, txt))
                # AI markdown content
                if obj.get('kind') == 'markdownContent':
                    content = obj.get('content', {})
                    if isinstance(content, dict):
                        val = content.get('value', '')
                    elif isinstance(content, str):
                        val = content
                    else:
                        val = ''
                    if val and len(val.strip()) > 0:
                        ai_parts.append((line_num, val))
                # Recurse
                for k, child in obj.items():
                    if isinstance(child, (dict, list)):
                        extract_from(child, line_num)
            elif isinstance(obj, list):
                for item in obj:
                    extract_from(item, line_num)
        
        extract_from(v, i + 1)

print(f"User messages: {len(user_msgs)}")
print(f"AI response parts: {len(ai_parts)}")

# Write transcript
with open(DST, 'w', encoding='utf-8') as of:
    of.write("# Chat 4: Exploring Additional POCs for Issue Identification\n\n")
    
    # Interleave by line number
    all_items = []
    for ln, txt in user_msgs:
        all_items.append((ln, 'USER', txt))
    for ln, txt in ai_parts:
        all_items.append((ln, 'AI', txt))
    all_items.sort(key=lambda x: x[0])
    
    prev_type = None
    for ln, typ, txt in all_items:
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

import os
print(f"Written to {DST} ({os.path.getsize(DST)/1024:.1f} KB)")
