#!/usr/bin/env python3
"""PWA + API. GET / (page), /api/state, /receipts/<file>; POST /upload (raw image body), /api/remove/<id>."""
import json, os, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from intake import status  # noqa: E402
HOME = os.path.expanduser('~/mealprep')
RECEIPTS, DATA = f'{HOME}/receipts', f'{HOME}/data'
pending = set()  # files uploaded, intake not finished yet
lock = threading.Lock()


def load(p, default):
    try:
        return json.load(open(p))
    except FileNotFoundError:
        return default


def read_profile():
    try:
        return open(f'{DATA}/profile.txt').read()
    except FileNotFoundError:
        return ''


def save_json(p, d):
    json.dump(d, open(p + '.tmp', 'w'), ensure_ascii=False, indent=1)
    os.replace(p + '.tmp', p)


def run_intake(path):
    subprocess.run(['python3', f'{HERE}/intake.py', path])
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
                                   'profile': read_profile()})
        if p.startswith('/receipts/') and '..' not in p:
            try:
                return self.send(200, open(f'{RECEIPTS}/{p[10:]}', 'rb').read(), 'image/jpeg')
            except FileNotFoundError:
                pass
        self.send(404, {'error': 'not found'})

    def do_POST(self):
        p = self.path.split('?')[0]
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if p == '/upload':
            if not body:
                return self.send(400, {'error': 'empty'})
            name = time.strftime('%Y%m%d-%H%M%S') + '.jpg'
            open(f'{RECEIPTS}/{name}', 'wb').write(body)
            with lock:
                pending.add(name)
            threading.Thread(target=run_intake, args=(f'{RECEIPTS}/{name}',), daemon=True).start()
            return self.send(202, {'file': name})
        if p == '/api/profile':
            open(f'{DATA}/profile.txt', 'w').write(body.decode()[:2000])
            return self.send(200, {'ok': True})
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
    os.makedirs(DATA, exist_ok=True)
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', 8090))), H).serve_forever()
