#!/usr/bin/env python3
"""PWA + API. GET / (page), /api/state, /receipts/<file>; POST /upload (raw image body), /api/remove/<id>."""
import json, os, ssl, subprocess, sys, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from intake import status, load_profile  # noqa: E402
from config import load_config, save_config  # noqa: E402
import auth  # noqa: E402
HOME = os.path.expanduser('~/mealprep')
RECEIPTS, FRIDGE, DISHES, DATA = f'{HOME}/receipts', f'{HOME}/fridge', f'{HOME}/dishes', f'{HOME}/data'
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


def pending():
    """Photos on disk that no result record mentions yet. Survives restarts, unlike an in-memory set."""
    done = {r['file'] for r in load(f'{DATA}/receipts.json', [])} | set(load(f'{DATA}/fridge.json', {}).get('done', []))
    return sorted(f for d in (RECEIPTS, FRIDGE) for f in os.listdir(d) if not f.startswith('.') and f not in done)


class H(BaseHTTPRequestHandler):
    set_cookie = False

    def send(self, code, body, ctype='application/json'):
        body = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        if self.set_cookie:
            auth.set_cookie_header(self)
        self.end_headers()
        self.wfile.write(body)

    def gate(self):
        """False = request already answered (login page, 401 or ban). Plain HTTP on the LAN stays open."""
        if not self.tls:
            return True
        ip = self.client_address[0]
        if auth.banned(ip):
            print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} AUTH BANNED {ip} {self.path[:60]}', file=sys.stderr, flush=True)
            self.send(429, b'gesperrt', 'text/plain')
            return False
        if auth.authed(self):
            return True
        print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} AUTH DENY {ip} {self.command} {self.path[:60]}', file=sys.stderr, flush=True)
        if self.path.startswith('/api/') or self.path.startswith('/upload'):
            self.send(401, {'error': 'login'})
        else:
            self.send(200, (auth.LOGIN % '').encode(), 'text/html; charset=utf-8')
        return False

    def do_GET(self):
        p = self.path.split('?')[0]
        if p == '/manifest.json':
            return self.send(200, open(f'{HERE}/manifest.json', 'rb').read())
        if not self.gate():
            return
        if p == '/':
            return self.send(200, open(f'{HERE}/index.html', 'rb').read(), 'text/html; charset=utf-8')
        if p == '/api/state':
            recs = load(f'{DATA}/receipts.json', [])
            return self.send(200, {'inventory': [{**i, 'status': status(i)} for i in load(f'{DATA}/inventory.json', [])],
                                   'receipts': [{k: v for k, v in r.items() if k != 'raw'} for r in recs],
                                   'pending': pending(),
                                   'fridge': load(f'{DATA}/fridge.json', {}).get('photos', []),
                                   'suggestions': load(f'{DATA}/suggestions.json', []),
                                   'profile': load_profile(), 'config': load_config(),
                                   'proposals': load(f'{DATA}/proposals.json', [])})
        for prefix, directory in (('/receipts/', RECEIPTS), ('/fridge/', FRIDGE), ('/dishes/', DISHES)):
            if p.startswith(prefix) and '..' not in p:
                try:
                    return self.send(200, open(f'{directory}/{p[len(prefix):]}', 'rb').read(), 'image/jpeg')
                except FileNotFoundError:
                    pass
        self.send(404, {'error': 'not found'})

    def do_POST(self):
        p = self.path.split('?')[0]
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if p == '/logout':
            self.send_response(303)
            self.send_header('Set-Cookie', f'{auth.COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax; Secure')
            self.send_header('Location', '/')
            self.send_header('Content-Length', '0')
            return self.end_headers()
        if p == '/login' and self.tls:
            ip = self.client_address[0]
            if auth.banned(ip):
                return self.send(429, b'gesperrt', 'text/plain')
            pw = urllib.parse.parse_qs(body.decode()).get('pw', [''])[0]
            if auth.check_password(pw):
                auth.attempts.pop(ip, None)
                self.set_cookie = True
                self.send_response(303)
                auth.set_cookie_header(self)
                self.send_header('Location', '/')
                self.send_header('Content-Length', '0')
                return self.end_headers()
            n = auth.fail(ip)
            print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} AUTH FAIL from {ip} ({n}/{auth.FAILS})', file=sys.stderr, flush=True)
            return self.send(200, (auth.LOGIN % '<small>falsch</small>').encode(), 'text/html; charset=utf-8')
        if not self.gate():
            return
        if p == '/upload':
            if not body:
                return self.send(400, {'error': 'empty'})
            if 'kind=dish' in self.path:  # plate photo for a cooked recipe: ?kind=dish&id=<suggestion id>
                sid = self.path.split('id=')[-1].split('&')[0]
                with lock:
                    sug = load(f'{DATA}/suggestions.json', [])
                    hit = next((x for x in sug if x['id'] == sid), None)
                    if not hit:
                        return self.send(404, {'error': 'no such recipe'})
                    hit['photo'] = f'{sid}.jpg'
                    open(f'{DISHES}/{sid}.jpg', 'wb').write(body)
                    save_json(f'{DATA}/suggestions.json', sug)
                return self.send(200, {'photo': hit['photo']})
            fridge = 'kind=fridge' in self.path
            directory, script = (FRIDGE, 'fridge.py') if fridge else (RECEIPTS, 'intake.py')
            name = time.strftime('%Y%m%d-%H%M%S') + '-' + os.urandom(2).hex() + '.jpg'  # two uploads in one second must not collide
            open(f'{directory}/{name}', 'wb').write(body)
            threading.Thread(target=run_intake, args=(f'{directory}/{name}', script), daemon=True).start()
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
        if p.startswith('/api/made/'):  # mark cooked, drop used ingredients from stock, remember them for undo
            with lock:
                sug = load(f'{DATA}/suggestions.json', [])
                hit = next((x for x in sug if x['id'] == p[10:]), None)
                if hit and not hit.get('made'):
                    used = {u.lower() for u in hit['uses']}
                    inv = load(f'{DATA}/inventory.json', [])
                    hit['removed'] = [i for i in inv if i['name'].lower() in used]
                    hit['made'] = True
                    save_json(f'{DATA}/inventory.json', [i for i in inv if i['name'].lower() not in used])
                    save_json(f'{DATA}/suggestions.json', sug)
            return self.send(200, {'ok': bool(hit)})
        if p.startswith('/api/unmade/'):  # misclick: back to open, ingredients back to stock
            with lock:
                sug = load(f'{DATA}/suggestions.json', [])
                hit = next((x for x in sug if x['id'] == p[12:]), None)
                if hit and hit.get('made'):
                    inv = load(f'{DATA}/inventory.json', [])
                    have = {i['id'] for i in inv}
                    inv += [i for i in hit.pop('removed', []) if i['id'] not in have]
                    hit['made'] = False
                    save_json(f'{DATA}/inventory.json', inv)
                    save_json(f'{DATA}/suggestions.json', sug)
            return self.send(200, {'ok': bool(hit)})
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


def serve(port, tls=None):
    handler = type('H', (H,), {'tls': bool(tls)})
    srv = ThreadingHTTPServer(('0.0.0.0', port), handler)
    if tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(f'{tls}/fullchain.pem', f'{tls}/key.pem')
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    srv.serve_forever()


if __name__ == '__main__':
    os.makedirs(RECEIPTS, exist_ok=True)
    os.makedirs(FRIDGE, exist_ok=True)
    os.makedirs(DISHES, exist_ok=True)
    tls = f'{HOME}/tls'
    if os.path.exists(f'{tls}/fullchain.pem') and not auth.env().get('PASSWORD'):
        print('PASSWORD missing in .env, not serving HTTPS', file=sys.stderr, flush=True)
    elif os.path.exists(f'{tls}/fullchain.pem'):  # acme.sh installs here and restarts us on renewal
        threading.Thread(target=serve, args=(int(os.environ.get('TLS_PORT', 8443)), tls), daemon=True).start()
    serve(int(os.environ.get('PORT', 8090)))  # plain HTTP stays for the LAN and as fallback
