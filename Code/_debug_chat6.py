"""Debug: inspect response item kinds in reconstructed state."""
import json, sys
sys.setrecursionlimit(20000)
SRC = r'REDACTED_PATH\AppData\Roaming\Code\User\workspaceStorage\bc015ee5f3eb128bf42e6031cbcd03ba\chatSessions\4bf9d13c-7f90-408f-baf7-05788ef41357.jsonl'

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
            state = v
        elif kind == 1 and k and state is not None:
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

reqs = state.get('requests', [])
for ri, req in enumerate(reqs[:5]):
    resp = req.get('response', [])
    msg = req.get('message', {})
    user_text = msg.get('text', '')[:80]
    print(f"Request {ri}: user='{user_text}' | response items: {len(resp)}")
    for j, item in enumerate(resp):
        if isinstance(item, dict):
            k = item.get('kind', '?')
            extra = ''
            if k == '?':
                extra = f" keys={list(item.keys())[:8]}"
                # Check for value/content directly
                for ck in ['value', 'content', 'text', 'markdown']:
                    if ck in item:
                        val = item[ck]
                        if isinstance(val, str):
                            extra += f" {ck}_len={len(val)}"
                        elif isinstance(val, dict) and 'value' in val:
                            extra += f" {ck}.value_len={len(val['value'])}"
            elif k == 'markdownContent':
                c = item.get('content', {})
                if isinstance(c, dict):
                    extra = f" len={len(c.get('value', ''))}"
                elif isinstance(c, str):
                    extra = f" len={len(c)}"
            elif k == 'textEditGroup':
                extra = ' (edit)'
            print(f"  [{j}] kind={k}{extra}")
        else:
            print(f"  [{j}] type={type(item).__name__}")
