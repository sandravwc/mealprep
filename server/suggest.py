#!/usr/bin/env python3
"""Inventory + history + season -> 2 recipe suggestions in suggestions.json, ntfy push. Run daily from cron."""
import json, os, sys, time, urllib.request, uuid
from intake import DATA, ENV, LLM, load, save, notify, status, load_profile, profile_text, llm, job_lock
from config import load_config  # noqa: E402

SEASON = {12: 'Winter', 1: 'Winter', 2: 'Winter', 3: 'Frühling', 4: 'Frühling', 5: 'Frühling',
          6: 'Sommer', 7: 'Sommer', 8: 'Sommer', 9: 'Herbst', 10: 'Herbst', 11: 'Herbst'}


WMO = {0: 'sonnig', 1: 'heiter', 2: 'wolkig', 3: 'bedeckt', 45: 'Nebel', 48: 'Nebel', 51: 'Nieselregen', 53: 'Nieselregen',
       55: 'Nieselregen', 61: 'Regen', 63: 'Regen', 65: 'starker Regen', 71: 'Schnee', 73: 'Schnee', 75: 'starker Schnee',
       80: 'Schauer', 81: 'Schauer', 82: 'heftige Schauer', 95: 'Gewitter', 96: 'Gewitter', 99: 'Gewitter'}


def weather():
    """'Wetter: 14 °C, Regen' for the place in .env, or '' if unset or offline. Geocoded once, cached."""
    place = ENV.get('WEATHER_PLACE')
    if not place:
        return ''
    try:
        geo = load(f'{DATA}/weather.json', {})
        if geo.get('place') != place:
            r = json.load(urllib.request.urlopen(
                'https://geocoding-api.open-meteo.com/v1/search?count=1&name=' + urllib.request.quote(place), timeout=10))
            geo = {'place': place, 'lat': r['results'][0]['latitude'], 'lon': r['results'][0]['longitude']}
            save(f'{DATA}/weather.json', geo)
        r = json.load(urllib.request.urlopen(
            f"https://api.open-meteo.com/v1/forecast?latitude={geo['lat']}&longitude={geo['lon']}"
            '&daily=temperature_2m_max,weather_code&timezone=auto&forecast_days=1', timeout=10))
        return f"Wetter heute: {round(r['daily']['temperature_2m_max'][0])} °C, {WMO.get(r['daily']['weather_code'][0], 'wechselhaft')}"
    except (OSError, KeyError, IndexError, ValueError) as e:
        print('weather skipped:', e, file=sys.stderr)
        return ''


MEAL_HINT = {'frühstück': 'Frühstück: schnell, leicht, wenig Aufwand', 'mittagessen': 'Mittagessen: sättigend, unter 30 Minuten',
             'abendessen': 'Abendessen: darf aufwendiger sein', 'snack': 'Snack: klein, kalt oder in 5 Minuten fertig'}


def build_prompt(inv, history, today, profile='', wx='', meal='Abendessen'):
    tiers = {'expired': [], 'soon': [], 'ok': [], 'bad': []}
    for i in sorted(inv, key=lambda i: i['expires']):
        tiers[status(i, today)].append(f"- {i['name']} ({i['qty']:g} {i['unit']}, bis {i['expires']})")
    stock = (f"DRINGEND, Datum überschritten aber noch gut, zuerst verbrauchen:\n{chr(10).join(tiers['expired']) or '- nichts'}\n"
             f"BALD ablaufend:\n{chr(10).join(tiers['soon']) or '- nichts'}\n"
             f"Übriger Vorrat:\n{chr(10).join(tiers['ok']) or '- nichts'}\n"
             f"NICHT verwenden (verdorben):\n{chr(10).join(tiers['bad']) or '- nichts'}")
    recent = [h for h in history if h['time'] >= time.strftime('%Y-%m-%d', time.localtime(time.time() - 14 * 86400))]
    kind = MEAL_HINT.get(meal.lower(), meal)
    cooked = ', '.join(h['title'] for h in recent if h.get('made')) or 'nichts erfasst'
    skipped = ', '.join(h['title'] for h in recent if not h.get('made')) or 'nichts'
    liked = ', '.join(h['title'] for h in history if h.get('rating') == 'up') or 'keine Angabe'
    disliked = ', '.join(h['title'] for h in history if h.get('rating') == 'down') or 'keine Angabe'
    return (f"Heute ist {today}, {SEASON[int(today[5:7])]}. {wx}\nVorrat:\n{stock}\n\n"
            f"Geschmacksprofil: {profile.strip() or 'keine Angabe'}\nHat geschmeckt: {liked}\nHat nicht geschmeckt: {disliked}\n"
            f"In den letzten 14 Tagen gekocht: {cooked}. Vorgeschlagen aber nicht gekocht: {skipped}.\n\n"
            f"Schlage 2 Gerichte vor für: {kind}. Passend zum Wetter (kalt und nass: Suppe, Eintopf, Ofen; heiß: leicht, kalt, Salat). Regeln: DRINGEND vor BALD vor Übrig. NICHT-verwenden-Zutaten nie nutzen. Nur Zutaten aus dem Vorrat "
            "plus Grundzutaten (Salz, Pfeffer, Öl, Gewürze). Nährstoffbalance über die Woche beachten. Wiederhole nichts "
            "aus den letzten 14 Tagen. Genau eines der beiden soll etwas Neues wagen: bekannte Zutat, neue Technik oder "
            "neues Gewürz, nicht beides. Antwort nur als JSON-Array: "
            '[{"emoji": ein passendes Emoji, "title": kurz, "text": 2-3 Sätze Zubereitung, "uses": [Vorratsnamen exakt wie oben]}]')


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
            out.append({'title': str(s['title']), 'text': str(s.get('text', '')), 'emoji': str(s.get('emoji', ''))[:2],
                        'uses': [str(u) for u in s.get('uses', []) if u]})
    return out


def run(meal):
    today = time.strftime('%Y-%m-%d')
    inv = load(f'{DATA}/inventory.json', [])
    if not inv:
        sys.exit('empty inventory, nothing to suggest')
    hist = load(f'{DATA}/suggestions.json', [])
    _lock = job_lock()
    with llm():
        raw = ask(build_prompt(inv, hist, today, profile_text(load_profile()), weather(), meal))
    sugs = parse(raw)
    if not sugs:
        sys.exit(f'no suggestions parsed: {raw[:200]}')
    for s in sugs:
        hist.append({**s, 'id': uuid.uuid4().hex[:8], 'time': time.strftime('%Y-%m-%d %H:%M'), 'meal': meal, 'made': False})
    save(f'{DATA}/suggestions.json', hist)
    notify(f'{meal}?', ' / '.join(s['title'] for s in sugs))
    print(json.dumps(sugs, ensure_ascii=False, indent=1))


def due():
    """Meals whose time fell in the last 15 minutes and have no suggestion today yet."""
    now = time.time()
    today = time.strftime('%Y-%m-%d')
    done = {h.get('meal') for h in load(f'{DATA}/suggestions.json', []) if h['time'].startswith(today)}
    out = []
    for m in load_config()['meals']:
        at = time.mktime(time.strptime(f'{today} {m["time"]}', '%Y-%m-%d %H:%M'))
        if 0 <= now - at < 15 * 60 and m['name'] not in done:
            out.append(m['name'])
    return out


if __name__ == '__main__':
    if sys.argv[1:] == ['--due']:
        for meal in due():
            run(meal)
    else:
        run(sys.argv[1] if sys.argv[1:] else load_config()['meals'][0]['name'])
