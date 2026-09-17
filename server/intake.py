#!/usr/bin/env python3
"""Receipt photo -> inventory.json. Usage: intake.py [file ...]; no args = every unprocessed file in receipts/."""
import base64, fcntl, json, os, sys, time, urllib.request, uuid

HOME = os.path.expanduser('~/mealprep')
RECEIPTS, DATA = f'{HOME}/receipts', f'{HOME}/data'
ENV = {}
try:
    ENV = dict(l.strip().split('=', 1) for l in open(f'{HOME}/.env') if '=' in l)
except FileNotFoundError:
    pass
LLM = ENV.get('LLM_URL', 'http://127.0.0.1:8080/v1/chat/completions')
SHELF = {'dairy': 7, 'meat': 3, 'fish': 2, 'produce': 7, 'bread': 4, 'eggs': 21,
         'pantry': 180, 'frozen': 90, 'drinks': 180, 'other': 14}  # days
PROMPT = ('German supermarket receipt. Extract every purchased item as a JSON array of objects with keys: '
          'name (full German product name, expand abbreviations: "H-MILCH"->"H-Milch", "BA BANANE"->"Banane", '
          '"HACKFL. GEM."->"Hackfleisch gemischt"), qty (number), unit ("Stück","kg","g","l","ml","Packung"), '
          f'category (one of {list(SHELF)}). Skip Pfand, discounts, totals, payment lines. Output only JSON.')


def load(p, default):
    try:
        return json.load(open(p))
    except FileNotFoundError:
        return default


def save(p, d):
    json.dump(d, open(p + '.tmp', 'w'), ensure_ascii=False, indent=1)
    os.replace(p + '.tmp', p)


def ask_llm(img):
    mime = 'image/png' if img.lower().endswith('.png') else 'image/jpeg'
    b64 = base64.b64encode(open(img, 'rb').read()).decode()
    req = {'chat_template_kwargs': {'enable_thinking': False}, 'temperature': 0, 'max_tokens': 1500,
           'messages': [{'role': 'user', 'content': [
               {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{b64}'}},
               {'type': 'text', 'text': PROMPT}]}]}
    r = urllib.request.urlopen(urllib.request.Request(
        LLM, json.dumps(req).encode(), {'Content-Type': 'application/json'}), timeout=900)
    return json.load(r)['choices'][0]['message']['content']


def parse_items(text, aliases):
    """Model text -> clean item dicts. Tolerates code fences, junk fields, bad numbers."""
    out = []
    a, b = text.find('['), text.rfind(']')
    if a < 0 or b < a:
        return out  # no array = model says this is not a receipt
    for it in json.loads(text[a:b + 1]):
        name = str(it.get('name', '')).strip()
        if not name:
            continue
        cat = it.get('category')
        try:
            qty = float(it.get('qty') or 1)
        except (TypeError, ValueError):
            qty = 1.0
        out.append({'name': aliases.get(name.lower(), name), 'qty': qty,
                    'unit': str(it.get('unit') or 'Stück'), 'category': cat if cat in SHELF else 'other'})
    return out


def intake(path):
    raw = ask_llm(path)
    items = parse_items(raw, load(f'{DATA}/aliases.json', {}))
    today, rid = time.strftime('%Y-%m-%d'), os.path.basename(path)
    inv = load(f'{DATA}/inventory.json', [])
    for it in items:
        exp = time.strftime('%Y-%m-%d', time.localtime(time.time() + SHELF[it['category']] * 86400))
        inv.append({**it, 'id': uuid.uuid4().hex[:8], 'bought': today, 'expires': exp, 'receipt': rid})
    save(f'{DATA}/inventory.json', inv)
    rec = load(f'{DATA}/receipts.json', [])
    rec.append({'file': rid, 'time': today, 'items': items, 'raw': raw})
    save(f'{DATA}/receipts.json', rec)
    return items


def notify(title, msg):
    if 'NTFY_TOPIC' not in ENV:
        return
    hdr = {'Title': title, 'Click': ENV.get('BASE_URL', '')}
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"https://ntfy.sh/{ENV['NTFY_TOPIC']}", msg.encode(), hdr), timeout=15)
    except OSError as e:
        print('ntfy failed:', e, file=sys.stderr)


if __name__ == '__main__':
    os.makedirs(DATA, exist_ok=True)
    fcntl.flock(open(f'{DATA}/.lock', 'w'), fcntl.LOCK_EX)  # ponytail: one intake at a time, fine for one household
    done = {r['file'] for r in load(f'{DATA}/receipts.json', [])}
    files = sys.argv[1:] or sorted(
        f'{RECEIPTS}/{f}' for f in os.listdir(RECEIPTS)
        if not f.startswith('.') and f not in done and os.path.isfile(f'{RECEIPTS}/{f}')
        and time.time() - os.path.getmtime(f'{RECEIPTS}/{f}') > 10)  # skip files still syncing
    for f in files:
        try:
            items = intake(f)
        except Exception as e:  # LLM down or unparsable: log, retry on next cron run
            print(f'{f}: {e}', file=sys.stderr)
            notify('receipt failed, will retry', f'{os.path.basename(f)}: {e}')
            continue
        if items:
            notify(f'{len(items)} items added', ', '.join(i['name'] for i in items))
        else:
            notify('no receipt found', load(f'{DATA}/receipts.json', [])[-1]['raw'][:200])
