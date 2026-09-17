#!/usr/bin/env python3
"""Daily sanity pass over data/*.json. Removes duplicates and junk, never food. Flags items past their grace period. Pushes a summary when it changed anything."""
from intake import DATA, cats, load, save, notify, status

def clean_inventory(inv, aliases):
    seen, out, dropped, known = set(), [], [], cats()
    for i in inv:
        name = str(i.get('name', '')).strip()
        key = (i.get('receipt'), name.lower())
        if not name or aliases.get(name.lower()) == '' or aliases.get(str(i.get('raw', '')).lower()) == '':
            dropped.append(name or '?')
        elif key in seen:
            dropped.append(f'{name} (doppelt)')
        else:
            seen.add(key)
            i['name'] = name
            if i.get('category') not in known:
                i['category'] = 'other'
            out.append(i)
    return out, dropped


def clean_suggestions(sug):
    seen, out = set(), []
    for s in sug:
        if s.get('id') and s['id'] not in seen and s.get('title'):
            seen.add(s['id'])
            out.append(s)
    return out, len(sug) - len(out)


if __name__ == '__main__':
    inv, dropped = clean_inventory(load(f'{DATA}/inventory.json', []), load(f'{DATA}/aliases.json', {}))
    sug, dup = clean_suggestions(load(f'{DATA}/suggestions.json', []))
    rec = list({r['file']: r for r in load(f'{DATA}/receipts.json', [])}.values())  # last record per file wins
    dup += len(load(f'{DATA}/receipts.json', [])) - len(rec)
    props = list({(p['kind'], p['name'].lower()): p for p in load(f'{DATA}/proposals.json', [])}.values())
    dup += len(load(f'{DATA}/proposals.json', [])) - len(props)
    if dropped or dup:
        save(f'{DATA}/inventory.json', inv)
        save(f'{DATA}/suggestions.json', sug)
        save(f'{DATA}/receipts.json', rec)
        save(f'{DATA}/proposals.json', props)
        msg = ', '.join(dropped) + (f' · {dup} doppelte Einträge' if dup else '')
        print(msg)
        notify(f'Janitor: {len(dropped) + dup} entfernt', msg[:400])
    bad = [i['name'] for i in inv if status(i) == 'bad']
    if bad:  # never auto-remove food, just say it
        notify(f'{len(bad)} x entsorgen?', ', '.join(bad)[:400])
