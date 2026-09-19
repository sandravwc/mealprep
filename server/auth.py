"""Password login with a cookie session, token links for ntfy, per-IP ban after failed logins.
Config in .env: PASSWORD (required for HTTPS access), AUTH_TOKEN (auto-generated if missing).
Android has no iptables, so the ban is in-process: FAILS wrong passwords from one IP -> BAN seconds locked."""
import hashlib, hmac, os, secrets, time
from http.cookies import SimpleCookie

HOME = os.path.expanduser('~/mealprep')
FAILS, BAN = 5, 3600
COOKIE = 'mp'
attempts = {}  # ip -> [fail count, first fail time]


def env():
    try:
        return dict(l.strip().split('=', 1) for l in open(f'{HOME}/.env') if '=' in l)
    except FileNotFoundError:
        return {}


def token():
    """Long-lived secret for links and the cookie. Written to .env once."""
    e = env()
    if 'AUTH_TOKEN' not in e:
        with open(f'{HOME}/.env', 'a') as f:
            f.write(f'AUTH_TOKEN={secrets.token_urlsafe(32)}\n')
        e = env()
    return e['AUTH_TOKEN']


def cookie_value():
    return hashlib.sha256(token().encode()).hexdigest()  # cookie != token, so a leaked cookie does not expose links


def check_password(pw):
    return bool(env().get('PASSWORD')) and hmac.compare_digest(pw, env()['PASSWORD'])


def banned(ip):
    n, t = attempts.get(ip, (0, 0))
    if n >= FAILS and time.time() - t < BAN:
        return True
    if time.time() - t >= BAN:
        attempts.pop(ip, None)
    return False


def fail(ip):
    n, t = attempts.get(ip, (0, time.time()))
    attempts[ip] = [n + 1, t]
    return attempts[ip][0]


def authed(handler):
    """True if the request carries the cookie or ?t=<token>. Sets the cookie when the token is in the URL."""
    if 't=' in handler.path and hmac.compare_digest(handler.path.split('t=')[-1].split('&')[0], token()):
        handler.set_cookie = True
        return True
    c = SimpleCookie(handler.headers.get('Cookie', ''))
    return COOKIE in c and hmac.compare_digest(c[COOKIE].value, cookie_value())


def set_cookie_header(handler):
    handler.send_header('Set-Cookie', f'{COOKIE}={cookie_value()}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax; Secure')


LOGIN = '''<!doctype html><html lang="de"><head><meta charset="utf-8"><title>mealprep</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font:16px system-ui;background:#111;color:#eee;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
form{display:flex;flex-direction:column;gap:12px;width:min(90vw,320px)}input,button{font:inherit;padding:12px;border:0;border-radius:8px}
input{background:#222;color:#eee}button{background:#2a6;color:#fff}small{color:#e44}</style></head><body>
<form method="post" action="/login"><b>mealprep</b><input type="password" name="pw" placeholder="Passwort" autofocus>
<button>rein</button>%s</form></body></html>'''
