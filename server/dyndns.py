#!/usr/bin/env python3
"""Keep an A record on the current public IP via the AutoDNS API. Cron every 5 min.
Public IP: router over UPnP if enabled, else an account-free echo service.
Credentials: reused from acme.sh (~/.acme.sh/account.conf), nothing stored twice."""
import os, re, socket, sys, urllib.request
from xml.sax.saxutils import escape

HOME = os.path.expanduser('~')
ENV = {}
try:
    ENV = dict(l.strip().split('=', 1) for l in open(f'{HOME}/mealprep/.env') if '=' in l)
except FileNotFoundError:
    pass
ZONE, HOST = ENV.get('DYNDNS_ZONE', 'xn--bdk.dog'), ENV.get('DYNDNS_HOST', 'poco')
SYSTEM_NS = ENV.get('DYNDNS_NS', 'a.ns14.net')
STATE = f'{HOME}/mealprep/data/dyndns.ip'


def creds():
    c = {}
    for l in open(f'{HOME}/.acme.sh/account.conf'):
        m = re.match(r"SAVED_AUTODNS_(USER|PASSWORD|CONTEXT)='(.*)'", l.strip())
        if m:
            c[m.group(1)] = m.group(2)
    return c['USER'], c['PASSWORD'], c['CONTEXT']


def ip_upnp():
    """Ask the router. Works only with UPnP on. Returns '' otherwise."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.sendto(b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 1\r\n'
                 b'ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n', ('239.255.255.250', 1900))
        loc = re.search(rb'LOCATION:\s*(\S+)', s.recvfrom(4096)[0], re.I).group(1).decode()
        xml = urllib.request.urlopen(loc, timeout=3).read().decode(errors='replace')
        for st in ('WANIPConnection:1', 'WANPPPConnection:1'):
            m = re.search(r'service:' + st + r'</serviceType>.*?<controlURL>([^<]+)', xml, re.S)
            if not m:
                continue
            url = re.match(r'https?://[^/]+', loc).group(0) + m.group(1)
            body = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
                    f'<u:GetExternalIPAddress xmlns:u="urn:schemas-upnp-org:service:{st}"/></s:Body></s:Envelope>')
            r = urllib.request.urlopen(urllib.request.Request(url, body.encode(), {
                'Content-Type': 'text/xml', 'SOAPAction': f'"urn:schemas-upnp-org:service:{st}#GetExternalIPAddress"'}), timeout=3)
            return re.search(r'<NewExternalIPAddress>([^<]*)', r.read().decode()).group(1)
    except (OSError, AttributeError):
        pass
    return ''


def ip_echo():
    for url in ('https://ifconfig.co/ip', 'https://icanhazip.com'):
        try:
            return urllib.request.urlopen(url, timeout=10).read().decode().strip()
        except OSError:
            continue
    return ''


def valid(ip):
    return bool(re.fullmatch(r'(\d{1,3}\.){3}\d{1,3}', ip)) and not ip.startswith(('10.', '192.168.', '127.'))


def current_record():
    """A records for HOST from DNS, so a manual change or a fresh boot does not trust a stale cache."""
    try:
        return sorted({a[4][0] for a in socket.getaddrinfo(f'{HOST}.{ZONE}', None, socket.AF_INET)})
    except OSError:
        return []


def update(old_ips, new_ip):
    user, pw, ctx = creds()
    rem = ''.join(f'<rr_rem><name>{HOST}</name><type>A</type><value>{o}</value></rr_rem>' for o in old_ips)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?><request><auth><user>{escape(user)}</user><password>{escape(pw)}</password>'
           f'<context>{ctx}</context></auth><task><code>0202001</code><default>{rem}'
           f'<rr_add><name>{HOST}</name><ttl>300</ttl><type>A</type><value>{new_ip}</value></rr_add></default>'
           f'<zone><name>{ZONE}</name><system_ns>{SYSTEM_NS}</system_ns></zone></task></request>')
    r = urllib.request.urlopen(urllib.request.Request('https://gateway.autodns.com', xml.encode(),
                               {'Content-Type': 'text/xml'}), timeout=30).read().decode()
    if '<type>success</type>' not in r:
        raise RuntimeError(re.sub(r'<password>.*?</password>', '', r)[:300])


if __name__ == '__main__':
    ip = ip_upnp() or ip_echo()
    if not valid(ip):
        sys.exit(f'no usable public ip: {ip!r}')
    try:
        last = open(STATE).read().strip()
    except FileNotFoundError:
        last = ''
    if ip == last and '--force' not in sys.argv:
        sys.exit(0)
    old = current_record()
    if old != [ip]:
        update(old, ip)  # ponytail: whole A set replaced, single-host zone, fine
        print(f'{HOST}.{ZONE}: {old} -> {ip}')
    open(STATE, 'w').write(ip)
