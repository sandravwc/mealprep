#!/usr/bin/env python3
"""Fridge/pantry photo -> proposals.json (add/remove suggestions), never touches stock directly.
Usage: fridge.py [file ...]; no args = every unprocessed file in fridge/."""
import base64, fcntl, json, os, sys, time, urllib.request, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from intake import DATA, HOME, LLM, cats, load, save, notify  # noqa: E402

FRIDGE = f'{HOME}/fridge'
PERISHABLE = {'produce', 'dairy', 'meat', 'fish', 'bread', 'eggs'}  # only these get "remove?" proposals
MISSES = 2  # consecutive photos without the item before proposing removal


def prompt():
    return ('Photo of a fridge or pantry. List every food or drink item you can actually see, in German, as a JSON array '
            'of {name, category}. category one of ' + str(list(cats())) + '. One entry per distinct product, no quantities, '
            'no guesses about hidden items. Output only JSON.')


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


def diff(seen, inv, misses):
    """seen items vs stock -> (proposals, updated misses). misses = {item id: consecutive photos not seen}."""
    props = []
    for s in seen:
        if not any(same(s['name'], i['name']) for i in inv):
            props.append({'kind': 'add', 'name': s['name'], 'category': s['category']})
    if not seen:
        return props, misses  # not a fridge photo, count nothing
    new_misses = {}
    for i in inv:
        if i.get('category') not in PERISHABLE:
            continue
        if any(same(s['name'], i['name']) for s in seen):
            continue
        new_misses[i['id']] = misses.get(i['id'], 0) + 1
        if new_misses[i['id']] >= MISSES:
            props.append({'kind': 'remove', 'name': i['name'], 'item': i['id']})
    return props, new_misses


if __name__ == '__main__':
    os.makedirs(FRIDGE, exist_ok=True)
    _lock = open(f'{DATA}/.lock', 'w')
    fcntl.flock(_lock, fcntl.LOCK_EX)
    state = load(f'{DATA}/fridge.json', {'done': [], 'misses': {}})
    files = [a for a in sys.argv[1:] if os.path.basename(a) not in state['done']] or sorted(
        f'{FRIDGE}/{f}' for f in os.listdir(FRIDGE)
        if not f.startswith('.') and f not in state['done'] and os.path.isfile(f'{FRIDGE}/{f}')
        and time.time() - os.path.getmtime(f'{FRIDGE}/{f}') > 10)
    for f in files:
        try:
            seen = parse_seen(ask_llm(f))
        except Exception as e:
            print(f'{f}: {e}', file=sys.stderr)
            notify('Kühlschrank-Foto fehlgeschlagen, wird wiederholt', str(e)[:200])
            continue
        props, state['misses'] = diff(seen, load(f'{DATA}/inventory.json', []), state['misses'])
        old = load(f'{DATA}/proposals.json', [])
        keep = [p for p in old if not any(p['kind'] == q['kind'] and same(p['name'], q['name']) for q in props)]
        for p in props:
            p.update({'id': uuid.uuid4().hex[:8], 'time': time.strftime('%Y-%m-%d %H:%M'), 'file': os.path.basename(f)})
        save(f'{DATA}/proposals.json', keep + props)
        state['done'].append(os.path.basename(f))
        save(f'{DATA}/fridge.json', state)
        adds = [p['name'] for p in props if p['kind'] == 'add']
        rems = [p['name'] for p in props if p['kind'] == 'remove']
        notify(f'Kühlschrank: {len(seen)} gesehen, +{len(adds)} −{len(rems)}',
               (('neu: ' + ', '.join(adds)) if adds else '') + (('  weg? ' + ', '.join(rems)) if rems else '') or 'nichts Neues')
