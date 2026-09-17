"""Editable settings. Defaults here, overrides in data/config.json (written by the PWA). Never delete 'other'."""
import json, os

DATA = os.path.expanduser('~/mealprep/data')
DEFAULTS = {
    # category: [days from purchase to "expires", days past "expires" still fine to eat]
    'categories': {'dairy': [7, 3], 'meat': [3, 0], 'fish': [2, 0], 'produce': [7, 4], 'bread': [4, 3], 'eggs': [21, 14],
                   'pantry': [180, 365], 'frozen': [90, 180], 'drinks': [180, 365], 'sweets': [120, 365], 'other': [14, 30]},
    'tags': {'scharf': 'mag scharf', 'vegetarisch': 'vegetarisch', 'vegan': 'vegan', 'wenig_fleisch': 'wenig Fleisch',
             'fisch': 'mag Fisch', 'pasta': 'mag Pasta', 'reis': 'mag Reis', 'kartoffeln': 'mag Kartoffeln',
             'asiatisch': 'mag asiatisch', 'mediterran': 'mag mediterran', 'orientalisch': 'mag orientalisch',
             'deutsch': 'mag deutsche Hausmannskost', 'neues': 'probiert gern Neues', 'schnell': 'unter der Woche max 30 min',
             'reste': 'kocht gern vor / Reste', 'suess': 'mag süß', 'lowcarb': 'wenig Kohlenhydrate',
             'protein': 'viel Protein', 'glutenfrei': 'glutenfrei', 'laktosefrei': 'laktosefrei', 'koriander': 'kein Koriander'},
    # one suggestion run per meal per day, cron checks every 15 min what is due
    'meals': [{'name': 'Abendessen', 'time': '17:00'}],
}


def load_config():
    try:
        cfg = json.load(open(f'{DATA}/config.json'))
    except (FileNotFoundError, ValueError):
        return json.loads(json.dumps(DEFAULTS))
    cfg.setdefault('meals', DEFAULTS['meals'])  # configs saved before meals existed
    return clean(cfg)


def clean(cfg):
    """Validate a config from the PWA. Bad rows are dropped, 'other' is guaranteed."""
    cats = {}
    for name, v in (cfg.get('categories') or {}).items():
        name = str(name).strip().lower()
        try:
            shelf, grace = int(v[0]), int(v[1])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if name and shelf >= 0 and grace >= 0:
            cats[name] = [shelf, grace]
    cats.setdefault('other', DEFAULTS['categories']['other'])
    tags = {str(k).strip(): str(v).strip() for k, v in (cfg.get('tags') or {}).items() if str(k).strip() and str(v).strip()}
    meals = []
    for m in cfg.get('meals') or []:
        name, t = str(m.get('name', '')).strip(), str(m.get('time', '')).strip()
        if name and len(t) == 5 and t[2] == ':' and t[:2].isdigit() and t[3:].isdigit() and int(t[:2]) < 24 and int(t[3:]) < 60:
            meals.append({'name': name, 'time': t})
    return {'categories': cats, 'tags': tags, 'meals': meals or DEFAULTS['meals']}


def save_config(cfg):
    cfg = clean(cfg)
    os.makedirs(DATA, exist_ok=True)
    json.dump(cfg, open(f'{DATA}/config.json.tmp', 'w'), ensure_ascii=False, indent=1)
    os.replace(f'{DATA}/config.json.tmp', f'{DATA}/config.json')
    return cfg
