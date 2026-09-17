#!/usr/bin/env python3
"""Inventory + history + season -> 2 recipe suggestions in suggestions.json, ntfy push. Run daily from cron."""
import json, os, sys, time, urllib.request, uuid
from intake import DATA, ENV, LLM, load, save, notify

SEASON = {12: 'Winter', 1: 'Winter', 2: 'Winter', 3: 'Frühling', 4: 'Frühling', 5: 'Frühling',
          6: 'Sommer', 7: 'Sommer', 8: 'Sommer', 9: 'Herbst', 10: 'Herbst', 11: 'Herbst'}


def build_prompt(inv, history, today):
    inv = sorted(inv, key=lambda i: i['expires'])
    stock = '\n'.join(f"- {i['name']} ({i['qty']:g} {i['unit']}, haltbar bis {i['expires']})" for i in inv)
    recent = [h for h in history if h['time'] >= time.strftime('%Y-%m-%d', time.localtime(time.time() - 14 * 86400))]
    cooked = ', '.join(h['title'] for h in recent if h.get('made')) or 'nichts erfasst'
    skipped = ', '.join(h['title'] for h in recent if not h.get('made')) or 'nichts'
    return (f"Heute ist {today}, {SEASON[int(today[5:7])]}. Vorrat (zuerst ablaufend):\n{stock}\n\n"
            f"In den letzten 14 Tagen gekocht: {cooked}. Vorgeschlagen aber nicht gekocht: {skipped}.\n\n"
            "Schlage 2 Abendessen vor. Regeln: bald ablaufende Zutaten zuerst verbrauchen. Nur Zutaten aus dem Vorrat "
            "plus Grundzutaten (Salz, Pfeffer, Öl, Gewürze). Nährstoffbalance über die Woche beachten. Wiederhole nichts "
            "aus den letzten 14 Tagen. Genau eines der beiden soll etwas Neues wagen: bekannte Zutat, neue Technik oder "
            "neues Gewürz, nicht beides. Antwort nur als JSON-Array: "
            '[{"title": kurz, "text": 2-3 Sätze Zubereitung, "uses": [Vorratsnamen exakt wie oben]}]')


def ask(prompt):
    req = {'chat_template_kwargs': {'enable_thinking': False}, 'temperature': 0.7, 'max_tokens': 700,
           'messages': [{'role': 'user', 'content': prompt}]}
    r = urllib.request.urlopen(urllib.request.Request(
        LLM, json.dumps(req).encode(), {'Content-Type': 'application/json'}), timeout=900)
    return json.load(r)['choices'][0]['message']['content']


def parse(text):
    a, b = text.find('['), text.rfind(']')
    out = []
    for s in json.loads(text[a:b + 1]) if a >= 0 and b > a else []:
        if s.get('title'):
            out.append({'title': str(s['title']), 'text': str(s.get('text', '')),
                        'uses': [str(u) for u in s.get('uses', []) if u]})
    return out


if __name__ == '__main__':
    today = time.strftime('%Y-%m-%d')
    inv = load(f'{DATA}/inventory.json', [])
    if not inv:
        sys.exit('empty inventory, nothing to suggest')
    hist = load(f'{DATA}/suggestions.json', [])
    raw = ask(build_prompt(inv, hist, today))
    sugs = parse(raw)
    if not sugs:
        sys.exit(f'no suggestions parsed: {raw[:200]}')
    for s in sugs:
        hist.append({**s, 'id': uuid.uuid4().hex[:8], 'time': time.strftime('%Y-%m-%d %H:%M'), 'made': False})
    save(f'{DATA}/suggestions.json', hist)
    notify('Heute kochen?', ' / '.join(s['title'] for s in sugs))
    print(json.dumps(sugs, ensure_ascii=False, indent=1))
