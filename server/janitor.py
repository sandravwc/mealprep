#!/usr/bin/env python3
"""Daily sanity pass over data/*.json. Removes duplicates, junk, long-expired stock. Pushes a summary when it changed anything."""
import time
from intake import DATA, SHELF, load, save, notify

GRACE = 7  # days past expiry before an item is assumed gone


def clean_inventory(inv, aliases, today):
    seen, out, dropped = set(), [], []
    for i in inv:
        name = str(i.get('name', '')).strip()
        key = (i.get('receipt'), name.lower())
        if not name or aliases.get(name.lower()) == '' or aliases.get(str(i.get('raw', '')).lower()) == '':
            dropped.append(name or '?')
        elif i.get('expires', '9') < today:
            dropped.append(f'{name} (abgelaufen {i["expires"]})')
        elif key in seen:
            dropped.append(f'{name} (doppelt)')
        else:
            seen.add(key)
            i['name'] = name
            if i.get('category') not in SHELF:
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
    cutoff = time.strftime('%Y-%m-%d', time.localtime(time.time() - GRACE * 86400))
    inv, dropped = clean_inventory(load(f'{DATA}/inventory.json', []), load(f'{DATA}/aliases.json', {}), cutoff)
    sug, dup = clean_suggestions(load(f'{DATA}/suggestions.json', []))
    if dropped or dup:
        save(f'{DATA}/inventory.json', inv)
        save(f'{DATA}/suggestions.json', sug)
        msg = ', '.join(dropped) + (f' · {dup} doppelte Rezepte' if dup else '')
        print(msg)
        notify(f'Janitor: {len(dropped) + dup} entfernt', msg[:400])
