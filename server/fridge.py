#!/usr/bin/env python3
"""Fridge/pantry photo -> proposals.json (add/remove suggestions), never touches stock directly.
Usage: fridge.py [file ...]; no args = every unprocessed file in fridge/."""
import base64, json, os, sys, time, urllib.request, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from intake import DATA, HOME, LLM, cats, load, save, notify, llm, job_lock  # noqa: E402

FRIDGE = f'{HOME}/fridge'
PERISHABLE = {'produce', 'dairy', 'meat', 'fish', 'bread', 'eggs'}  # only these get "remove?" proposals
MISSES = 2  # consecutive scans without the item before proposing removal
SESSION = 3600  # photos within an hour = one scan of the same kitchen


def prompt():
    return ('Photo of a fridge shelf, fridge door or pantry shelf. List every food or drink product you can identify, in German, '
            'as a JSON array of {name, category}. category one of ' + str(list(cats())) + '. Read the labels: give the '
            'specific product name printed on the packaging, brand included if readable. Never a generic group word. '
            'Skip containers whose contents you cannot see, foil bundles and non-food objects. One entry per distinct '
            'product, no quantities, no invented items. Output only JSON.')


def ask_llm(img):
    b64 = base64.b64encode(open(img, 'rb').read()).decode()
    req = {'chat_template_kwargs': {'enable_thinking': False}, 'temperature': 0, 'max_tokens': 800,
           'messages': [{'role': 'user', 'content': [
               {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}},
               {'type': 'text', 'text': prompt()}]}]}
    r = urllib.request.urlopen(urllib.request.Request(
        LLM, json.dumps(req).encode(), {'Content-Type': 'application/json'}), timeout=900)
    return json.load(r)['choices'][0]['message']['content']


def parse_seen(text):
    a, b = text.find('['), text.rfind(']')
    out, known = [], cats()
    for it in json.loads(text[a:b + 1]) if a >= 0 and b > a else []:
        name = str(it.get('name', '') if isinstance(it, dict) else it).strip()
        if name:
            cat = it.get('category') if isinstance(it, dict) else None
            out.append({'name': name, 'category': cat if cat in known else 'other'})
    return out


def same(a, b):
    a, b = a.lower(), b.lower()
    return a == b or (len(a) > 3 and a in b) or (len(b) > 3 and b in a)  # ponytail: substring match, no fuzzy lib


def adds(seen, inv):
    return [{'kind': 'add', 'name': s['name'], 'category': s['category']}
            for s in seen if not any(same(s['name'], i['name']) for i in inv)]


def removes(seen_names, inv, misses):
    """End of a scan: perishables unseen in the whole scan -> miss +1, propose removal at MISSES."""
    props, new_misses = [], {}
    for i in inv:
        if i.get('category') not in PERISHABLE or any(same(n, i['name']) for n in seen_names):
            continue
        new_misses[i['id']] = misses.get(i['id'], 0) + 1
        if new_misses[i['id']] >= MISSES:
            props.append({'kind': 'remove', 'name': i['name'], 'item': i['id']})
    return props, new_misses


def add_proposals(props, fname):
    old = load(f'{DATA}/proposals.json', [])
    keep = [p for p in old if not any(p['kind'] == q['kind'] and same(p['name'], q['name']) for q in props)]
    for p in props:
        p.update({'id': uuid.uuid4().hex[:8], 'time': time.strftime('%Y-%m-%d %H:%M'), 'file': fname})
    save(f'{DATA}/proposals.json', keep + props)


def close_scan(state):
    """Called when the last photo is older than SESSION. Turns the scan's union of seen names into misses."""
    scan = state.get('scan')
    if not scan or time.time() - scan['last'] < SESSION:
        return False
    if scan['seen']:  # a scan that saw nothing is not a scan
        props, state['misses'] = removes(scan['seen'], load(f'{DATA}/inventory.json', []), state.get('misses', {}))
        add_proposals(props, 'scan')
        if props:
            notify(f'{len(props)} x nicht mehr gesehen', ', '.join(p['name'] for p in props)[:400])
    state['scan'] = None
    return True


if __name__ == '__main__':
    os.makedirs(FRIDGE, exist_ok=True)
    _lock = job_lock()
    state = load(f'{DATA}/fridge.json', {'done': [], 'misses': {}})
    state.setdefault('photos', [])
    files = [a for a in sys.argv[1:] if os.path.basename(a) not in state['done']] or sorted(
        f'{FRIDGE}/{f}' for f in os.listdir(FRIDGE)
        if not f.startswith('.') and f not in state['done'] and os.path.isfile(f'{FRIDGE}/{f}')
        and time.time() - os.path.getmtime(f'{FRIDGE}/{f}') > 10)
    for f in files:
        try:
            with llm():
                seen = parse_seen(ask_llm(f))
        except Exception as e:
            print(f'{f}: {e}', file=sys.stderr)
            notify('Schrank-Foto fehlgeschlagen, wird wiederholt', str(e)[:200])
            continue
        props = adds(seen, load(f'{DATA}/inventory.json', []))
        add_proposals(props, os.path.basename(f))
        scan = state.get('scan') or {'last': 0, 'seen': []}
        if time.time() - scan['last'] > SESSION:
            scan = {'last': 0, 'seen': []}
        scan['seen'] = sorted(set(scan['seen']) | {x['name'] for x in seen})
        scan['last'] = time.time()
        state['scan'] = scan
        state['done'].append(os.path.basename(f))
        state['photos'].append({'file': os.path.basename(f), 'time': time.strftime('%Y-%m-%d %H:%M'), 'seen': [x['name'] for x in seen]})
        save(f'{DATA}/fridge.json', state)
        notify(f'Schrank: {len(seen)} gesehen, {len(props)} neu', ', '.join(p['name'] for p in props) or 'nichts Neues')
    if close_scan(state):
        save(f'{DATA}/fridge.json', state)
