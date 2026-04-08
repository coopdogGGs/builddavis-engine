"""Extract Chat 6 from VS Code Copilot JSONL (incremental patch format)."""
import json, os, sys

SRC = r'REDACTED_PATH\AppData\Roaming\Code\User\workspaceStorage\bc015ee5f3eb128bf42e6031cbcd03ba\chatSessions\4bf9d13c-7f90-408f-baf7-05788ef41357.jsonl'
DST = r'REDACTED_PATH\OneDrive\Vibe\BuildDavis\Chat6.txt'

sys.setrecursionlimit(20000)

# Reconstruct state by replaying patches
print("Reconstructing chat state from JSONL patches...")
state = None

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
        k = d.get('k')
        v = d.get('v')

        if kind == 0:
            # Initial state
            state = v
        elif kind == 1 and k and state is not None:
            # Set value at path
            obj = state
            for step in k[:-1]:
                if isinstance(obj, dict):
                    obj = obj.get(step, {})
                elif isinstance(obj, list) and isinstance(step, int) and step < len(obj):
                    obj = obj[step]
                else:
                    break
            last = k[-1]
            if isinstance(obj, dict):
                obj[last] = v
            elif isinstance(obj, list) and isinstance(last, int) and last < len(obj):
                obj[last] = v
        elif kind == 2 and k and state is not None:
            # Append to list at path
            obj = state
            for step in k:
                if isinstance(obj, dict):
                    obj = obj.get(step, {})
                elif isinstance(obj, list) and isinstance(step, int) and step < len(obj):
                    obj = obj[step]
                else:
                    break
            if isinstance(obj, list) and isinstance(v, list):
                obj.extend(v)

print(f"Total lines processed: {i + 1}")

# Extract requests
requests = state.get('requests', [])
print(f"Total requests (turns): {len(requests)}")

sep = '=' * 60
with open(DST, 'w', encoding='utf-8') as of:
    of.write("# Chat 6: ICONIC-001 Image Library Audit & Replacements\n\n")

    for ri, req in enumerate(requests):
        # User message
        msg = req.get('message', {})
        user_text = msg.get('text', '')
        if user_text:
            of.write(f"\n{sep}\nUSER (turn {ri + 1}):\n{sep}\n")
            of.write(user_text.strip() + "\n")

        # AI response
        response = req.get('response', [])
        ai_texts = []
        for item in response:
            if not isinstance(item, dict):
                continue
            # New format: items with 'value' key directly (no 'kind' field)
            if 'value' in item and 'kind' not in item:
                val = item.get('value', '')
                if isinstance(val, str) and val.strip() and len(val.strip()) > 2:
                    ai_texts.append(val.strip())
            # Old format: markdownContent kind
            elif item.get('kind') == 'markdownContent':
                content = item.get('content', {})
                if isinstance(content, dict):
                    val = content.get('value', '')
                elif isinstance(content, str):
                    val = content
                else:
                    val = ''
                if val and val.strip():
                    ai_texts.append(val.strip())
        if ai_texts:
            of.write(f"\n--- AI Response (turn {ri + 1}) ---\n")
            of.write("\n".join(ai_texts) + "\n")

print(f"Written to {DST} ({os.path.getsize(DST)/1024:.1f} KB)")
