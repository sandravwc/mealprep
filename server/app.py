#!/usr/bin/env python3
"""PWA + API. GET / (page), /api/state, /receipts/<file>; POST /upload (raw image body), /api/remove/<id>."""
import json, os, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from intake import status, load_profile  # noqa: E402
from config import load_config, save_config  # noqa: E402
HOME = os.path.expanduser('~/mealprep')
RECEIPTS, FRIDGE, DATA = f'{HOME}/receipts', f'{HOME}/fridge', f'{HOME}/data'
pending = set()  # files uploaded, intake not finished yet
lock = threading.Lock()


def load(p, default):
    try:
        return json.load(open(p))
    except FileNotFoundError:
        return default


def save_json(p, d):
    json.dump(d, open(p + '.tmp', 'w'), ensure_ascii=False, indent=1)
    os.replace(p + '.tmp', p)


def run_intake(path, script='intake.py'):
    subprocess.run(['python3', f'{HERE}/{script}', path])
    with lock:
        pending.discard(os.path.basename(path))


class H(BaseHTTPRequestHandler):
    def send(self, code, body, ctype='application/json'):
        body = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split('?')[0]
        if p == '/':
            return self.send(200, open(f'{HERE}/index.html', 'rb').read(), 'text/html; charset=utf-8')
        if p == '/manifest.json':
            return self.send(200, open(f'{HERE}/manifest.json', 'rb').read())
        if p == '/api/state':
            recs = load(f'{DATA}/receipts.json', [])
            return self.send(200, {'inventory': [{**i, 'status': status(i)} for i in load(f'{DATA}/inventory.json', [])],
                                   'receipts': [{k: v for k, v in r.items() if k != 'raw'} for r in recs],
                                   'pending': sorted(pending),
                                   'suggestions': load(f'{DATA}/suggestions.json', []),
                                   'profile': load_profile(), 'config': load_config(),
                                   'proposals': load(f'{DATA}/proposals.json', [])})
        for prefix, folder in (('/receipts/', RECEIPTS), ('/fridge/', FRIDGE)):
            if p.startswith(prefix) and '..' not in p:
                try:
                    return self.send(200, open(f'{folder}/{p[len(prefix):]}', 'rb').read(), 'image/jpeg')
                except FileNotFoundError:
                    pass
        self.send(404, {'error': 'not found'})

    def do_POST(self):
        p = self.path.split('?')[0]
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if p == '/upload':
            if not body:
                return self.send(400, {'error': 'empty'})
            fridge = 'kind=fridge' in self.path
            folder, script = (FRIDGE, 'fridge.py') if fridge else (RECEIPTS, 'intake.py')
            name = time.strftime('%Y%m%d-%H%M%S') + '.jpg'
            open(f'{folder}/{name}', 'wb').write(body)
            with lock:
                pending.add(name)
            threading.Thread(target=run_intake, args=(f'{folder}/{name}', script), daemon=True).start()
            return self.send(202, {'file': name})
        if p.startswith('/api/proposal/'):  # /api/proposal/<id>/accept|reject
            pid, action = (p[14:].split('/') + [''])[:2]
            with lock:
                props = load(f'{DATA}/proposals.json', [])
                hit = next((x for x in props if x['id'] == pid), None)
                if hit and action == 'accept':
                    inv = load(f'{DATA}/inventory.json', [])
                    if hit['kind'] == 'add':
                        shelf = load_config()['categories'].get(hit['category'], [14, 30])[0]
                        inv.append({'raw': '', 'name': hit['name'], 'qty': 1.0, 'unit': 'Stück', 'category': hit['category'],
                                    'id': os.urandom(4).hex(), 'bought': time.strftime('%Y-%m-%d'),
                                    'expires': time.strftime('%Y-%m-%d', time.localtime(time.time() + shelf * 86400)),
                                    'receipt': hit.get('file', 'fridge')})
                    else:
                        inv = [i for i in inv if i['id'] != hit.get('item')]
                    save_json(f'{DATA}/inventory.json', inv)
                save_json(f'{DATA}/proposals.json', [x for x in props if x['id'] != pid])
            return self.send(200, {'ok': bool(hit)})
        if p == '/api/profile':
            try:
                d = json.loads(body)
                prof = {'tags': [t for t in d.get('tags', []) if t in load_config()['tags']], 'text': str(d.get('text', ''))[:2000]}
            except (ValueError, AttributeError):
                return self.send(400, {'error': 'bad json'})
            save_json(f'{DATA}/profile.json', prof)
            return self.send(200, {'ok': True})
        if p == '/api/config':
            try:
                return self.send(200, save_config(json.loads(body)))
            except (ValueError, AttributeError):
                return self.send(400, {'error': 'bad json'})
        if p.startswith('/api/rate/'):  # /api/rate/<id>/up|down
            sid, val = (p[10:].split('/') + [''])[:2]
            with lock:
                sug = load(f'{DATA}/suggestions.json', [])
                for s in sug:
                    if s['id'] == sid:
                        s['rating'] = val if val in ('up', 'down') else None
                save_json(f'{DATA}/suggestions.json', sug)
            return self.send(200, {'ok': True})
        if p.startswith('/api/made/'):  # mark cooked, drop used ingredients from stock
            with lock:
                sug = load(f'{DATA}/suggestions.json', [])
                used = {u.lower() for s in sug if s['id'] == p[10:] for u in s['uses']}
                for s in sug:
                    if s['id'] == p[10:]:
                        s['made'] = True
                json.dump(sug, open(f'{DATA}/suggestions.json.tmp', 'w'), ensure_ascii=False, indent=1)
                os.replace(f'{DATA}/suggestions.json.tmp', f'{DATA}/suggestions.json')
                inv = [i for i in load(f'{DATA}/inventory.json', []) if i['name'].lower() not in used]
                json.dump(inv, open(f'{DATA}/inventory.json.tmp', 'w'), ensure_ascii=False, indent=1)
                os.replace(f'{DATA}/inventory.json.tmp', f'{DATA}/inventory.json')
            return self.send(200, {'ok': True})
        if p.startswith('/api/remove/'):
            with lock:
                inv = load(f'{DATA}/inventory.json', [])
                inv = [i for i in inv if i['id'] != p[12:]]
                json.dump(inv, open(f'{DATA}/inventory.json.tmp', 'w'), ensure_ascii=False, indent=1)
                os.replace(f'{DATA}/inventory.json.tmp', f'{DATA}/inventory.json')
            return self.send(200, {'ok': True})
        self.send(404, {'error': 'not found'})

    def log_message(self, fmt, *a):
        if '/api/state' not in fmt % a:
            super().log_message(fmt, *a)


if __name__ == '__main__':
    os.makedirs(RECEIPTS, exist_ok=True)
    os.makedirs(FRIDGE, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', 8090))), H).serve_forever()
