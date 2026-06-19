#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ÖzBel — Akıllı Tahta Kulak Sağlığı Sistemi
Native Pardus uygulaması (Python + GTK3)
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf

import os, sys, json, threading, subprocess, tempfile, random, string, time, shutil, base64
import urllib.request, urllib.error
from datetime import datetime

# =================== CONFIG ===================
FIREBASE_DB = "https://ozbel-eb6af-default-rtdb.europe-west1.firebasedatabase.app"
NETLIFY_URL = "https://glistening-fudge-bca794.netlify.app"
# ==============================================

APP_VERSION = "2.2.4"
# GitHub API üzerinden okunur — raw CDN'in aksine query/no-cache'e saygı duyar,
# böylece 5 dakikalık önbelleğe takılmadan anında günceli görür.
GH_API      = "https://api.github.com/repos/ozguroyunuzmn/ozbel/contents"
UPDATE_JSON = GH_API + "/version.json"
PY_DOWNLOAD = GH_API + "/ozbel.py"

SESSION   = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
APP_DIR   = os.path.dirname(os.path.abspath(__file__))
THRESHOLD = 90
DEFAULT_PASSWORD = "etap+pardus!"
AUTOSTART_FILE = os.path.join(os.path.expanduser("~"), ".config", "autostart", "ozbel.desktop")

# Gurultu tespiti telefondaki yapay zeka (YAMNet) ile yapilir:
# ses telefonda siniflandirilir, sadece "gurultu" karari + dB tahtaya gelir.
NOISE_FRESH_SEC = 3.0   # AI karari bu kadar sn icinde guncellendiyse gecerli say

USER_DIR    = os.path.join(os.path.expanduser("~"), ".local", "share", "ozbel")
CONFIG_FILE = os.path.join(USER_DIR, "config.json")
STATS_FILE  = os.path.join(USER_DIR, "stats.log")


def load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(cfg):
    os.makedirs(USER_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def log_stats(class_name, alert_count, max_db):
    try:
        os.makedirs(USER_DIR, exist_ok=True)
        with open(STATS_FILE, "a", encoding="utf-8") as f:
            dt = datetime.now().strftime("%Y-%m-%d %H:%M")
            cn = class_name if class_name else "?"
            f.write(f"{dt}  Sınıf:{cn}  Uyarı:{alert_count}  MaxdB:{max_db}\n")
    except Exception:
        pass

# Uyari sesi (MP3) — base64 gomulu, otomatik guncellemeyle tahtaya gider
ALERT_MP3_B64 = "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qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqpMQU1FMy4xMDCqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq//NkxHwAAANIAAAAAKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
_alert_path = None

def _ensure_alert_file():
    global _alert_path
    if _alert_path and os.path.exists(_alert_path):
        return _alert_path
    try:
        p = os.path.join(tempfile.gettempdir(), "ozbel_alert.mp3")
        with open(p, "wb") as f:
            f.write(base64.b64decode(ALERT_MP3_B64))
        _alert_path = p
        return p
    except Exception:
        return None

def _play_gst(path):
    try:
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        Gst.init(None)
        player = Gst.ElementFactory.make("playbin", None)
        if player is None:
            return False
        player.set_property("uri", "file://" + path)
        player.set_state(Gst.State.PLAYING)
        bus = player.get_bus()
        def _watch():
            bus.timed_pop_filtered(8 * Gst.SECOND,
                Gst.MessageType.EOS | Gst.MessageType.ERROR)
            player.set_state(Gst.State.NULL)
        threading.Thread(target=_watch, daemon=True).start()
        return True
    except Exception:
        return False

def play_alert_sound():
    path = _ensure_alert_file()
    if path and _play_gst(path):
        return
    if path:
        for cmd in (
            ["gst-play-1.0", "--quiet", path],
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
            ["mpv", "--no-video", "--really-quiet", path],
            ["cvlc", "--play-and-exit", "--intf", "dummy", path],
            ["mpg123", "-q", path],
        ):
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                continue
    for cmd in (["paplay", "/usr/share/sounds/freedesktop/stereo/bell.oga"],
                ["aplay", "/usr/share/sounds/alsa/Front_Left.wav"]):
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            continue


# ================================================================
# Firebase Relay — SSE ile dinler, REST ile yazar
# ================================================================
class FirebaseRelay(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.running = True

    def url(self, suffix=""):
        return f"{FIREBASE_DB}/sessions/{SESSION}{suffix}.json"

    def put(self, key, value):
        try:
            data = json.dumps(value).encode()
            req = urllib.request.Request(self.url("/" + key), data=data, method='PUT')
            urllib.request.urlopen(req, timeout=10).read()
        except Exception:
            pass

    def clear(self):
        try:
            req = urllib.request.Request(self.url(), data=b'null', method='PUT')
            urllib.request.urlopen(req, timeout=10).read()
        except Exception:
            pass

    def run(self):
        self.clear()
        while self.running:
            try:
                req = urllib.request.Request(
                    self.url(), headers={"Accept": "text/event-stream"})
                with urllib.request.urlopen(req, timeout=320) as resp:
                    event = None
                    for raw in resp:
                        if not self.running:
                            break
                        line = raw.decode('utf-8', 'ignore').rstrip('\n').rstrip('\r')
                        if line.startswith('event:'):
                            event = line[6:].strip()
                        elif line.startswith('data:'):
                            self.handle(event, line[5:].strip())
            except Exception:
                time.sleep(2)

    def handle(self, event, data):
        if event not in ('put', 'patch') or data in ('null', ''):
            return
        try:
            j = json.loads(data)
        except Exception:
            return
        path = j.get("path", "/")
        d    = j.get("data")

        if path == "/" and isinstance(d, dict):
            if d.get("teacher"): GLib.idle_add(self.app.on_teacher_connected)
            if d.get("mic"):     GLib.idle_add(self.app.on_mic_ready)
            if "ai" in d:        GLib.idle_add(self.app.on_ai, bool(d["ai"]))
            if "noise" in d:     GLib.idle_add(self.app.on_noise, bool(d["noise"]))
            if "db" in d and d["db"] is not None:
                GLib.idle_add(self.app.on_db, int(d["db"]))
            if d.get("lesson") == "end": GLib.idle_add(self.app.on_lesson_end)
        elif path == "/teacher":
            GLib.idle_add(self.app.on_teacher_connected if d else self.app.on_teacher_gone)
        elif path == "/mic" and d:
            GLib.idle_add(self.app.on_mic_ready)
        elif path == "/ai":
            GLib.idle_add(self.app.on_ai, bool(d))
        elif path == "/noise":
            GLib.idle_add(self.app.on_noise, bool(d))
        elif path == "/db" and d is not None:
            GLib.idle_add(self.app.on_db, int(d))
        elif path == "/lesson" and d == "end":
            GLib.idle_add(self.app.on_lesson_end)


# ================================================================
def make_qr(data, size):
    path = os.path.join(tempfile.gettempdir(), f"ozbel_qr_{abs(hash(data))}.png")
    try:
        subprocess.run(["qrencode", "-o", path, "-s", str(size), "-m", "2", "-l", "M", data],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return path
    except Exception:
        return None


CSS = (
"window { background-color:#080b12;"
"         background-image:radial-gradient(circle at 12% 0%, #11203a 0%, #080b12 45%);}\n"
".screen-bg { background-color:#080b12; }\n"
"@keyframes badgePulse { 0% { opacity:0.65; } 50% { opacity:1; } 100% { opacity:0.65; } }\n"
"@keyframes dbGlow { 0% { text-shadow:0 0 30px rgba(255,23,68,0.6); }"
"                    50% { text-shadow:0 0 70px rgba(255,23,68,1); }"
"                    100% { text-shadow:0 0 30px rgba(255,23,68,0.6); } }\n"
".logo-text  { color:#f0f4f9; font-size:50px; font-weight:900; letter-spacing:-2px;"
"              text-shadow:0 2px 20px rgba(255,255,255,0.12); }\n"
".logo-blue  { color:#3b82f6; font-size:50px; font-weight:900; letter-spacing:-2px;"
"              text-shadow:0 0 28px rgba(59,130,246,0.7); }\n"
".subtitle   { color:#94a3b8; font-size:14px; letter-spacing:.3px; }\n"
".code       { color:#60a5fa; font-size:34px; font-weight:900; letter-spacing:6px;"
"              text-shadow:0 0 22px rgba(96,165,250,0.6); }\n"
".qrlabel    { color:#94a3b8; font-size:11px; }\n"
".version    { color:#3a4452; font-size:11px; }\n"
".pill       { color:#93b4e8; font-size:14px; font-weight:600;"
"              background:linear-gradient(145deg,#13203a,#0d1626); border:1px solid #25344f;"
"              border-radius:999px; padding:9px 22px;"
"              box-shadow:0 6px 18px -8px rgba(0,0,0,0.7); }\n"
".pill-ok    { color:#4ade80; font-size:14px; font-weight:700;"
"              background:linear-gradient(145deg,#0e2418,#0a1a12); border:1px solid #1c4030;"
"              border-radius:999px; padding:9px 22px;"
"              box-shadow:0 8px 22px -8px rgba(34,197,94,0.45); }\n"
".pill-warn  { color:#f87171; font-size:14px; font-weight:700;"
"              background:linear-gradient(145deg,#2a1110,#1c0c0b); border:1px solid #4a2220;"
"              border-radius:999px; padding:9px 22px;"
"              box-shadow:0 8px 22px -8px rgba(239,68,68,0.45); }\n"
".card { background-image:linear-gradient(160deg,#161d29,#10151d);"
"        border:1px solid #243043; border-radius:24px; padding:28px;"
"        box-shadow:0 30px 60px -25px rgba(0,0,0,0.8); }\n"
".card-title { color:#f0f4f9; font-size:17px; font-weight:800; }\n"
".step-num   { color:#93c5fd; font-size:12px; font-weight:800;"
"              background:linear-gradient(145deg,#1a2e4f,#11203a); border:1px solid #2a4a80;"
"              border-radius:999px; padding:3px 11px;"
"              box-shadow:0 4px 12px -4px rgba(59,130,246,0.5); }\n"
".step-txt   { color:#94a3b8; font-size:13px; }\n"
".step-txt-b { color:#f0f4f9; font-size:13px; font-weight:700; }\n"
".db-huge  { color:#f0f4f9; font-size:88px; font-weight:900; letter-spacing:-3px;"
"            text-shadow:0 0 50px rgba(96,165,250,0.45); }\n"
".db-unit  { color:#94a3b8; font-size:18px; }\n"
".db-live  { color:#f0f4f9; font-size:42px; font-weight:900;"
"            text-shadow:0 0 24px rgba(96,165,250,0.4); }\n"
".db-ok    { color:#22c55e; font-size:42px; font-weight:900; }\n"
".db-warn  { color:#ef4444; font-size:42px; font-weight:900; }\n"
".db-mid   { color:#f59e0b; font-size:42px; font-weight:900; }\n"
".ready-label { color:#4ade80; font-size:23px; font-weight:800;"
"               background:linear-gradient(145deg,#0e2418,#0a1a12); border:1px solid #1c4030;"
"               border-radius:999px; padding:11px 30px;"
"               box-shadow:0 10px 28px -10px rgba(34,197,94,0.5);"
"               text-shadow:0 0 18px rgba(74,222,128,0.6); }\n"
".ready-sub   { color:#94a3b8; font-size:15px; }\n"
".dock { background-image:linear-gradient(160deg,#161d29,#10151d);"
"        border:1px solid #2a3646; border-radius:20px;"
"        box-shadow:0 24px 50px -18px rgba(0,0,0,0.85); }\n"
".conn-timer  { color:#4a5568; font-size:13px; font-weight:600; }\n"
".class-badge { color:#fbbf24; font-size:12px; font-weight:700;"
"               background:linear-gradient(145deg,#241a06,#1a1304); border:1px solid #4a3812;"
"               border-radius:999px; padding:5px 16px;"
"               box-shadow:0 6px 16px -6px rgba(245,158,11,0.4); }\n"
"button.outline { background:linear-gradient(145deg,#131c28,#0e151e); color:#94a3b8;"
"                 border:1px solid #2a3646; border-radius:13px;"
"                 padding:11px 24px; font-weight:600;"
"                 box-shadow:0 6px 16px -8px rgba(0,0,0,0.6);"
"                 transition:all 180ms ease; }\n"
"button.outline:hover { background:linear-gradient(145deg,#1a2636,#141d29);"
"                       border-color:#3f5572; color:#cdd9e8; }\n"
"button.small-outline { background:transparent; color:#6080a8;"
"                       border:1px solid #25344f; border-radius:999px;"
"                       padding:3px 12px; font-size:11px;"
"                       transition:all 180ms ease; }\n"
"button.small-outline:hover { color:#93c5fd; border-color:#3a5a8a; }\n"
"button.green  { background:linear-gradient(145deg,#3bdc9f,#15a34a);"
"                color:#04140a; border-radius:15px;"
"                padding:15px 38px; font-weight:800; border:none; font-size:15px;"
"                box-shadow:0 14px 34px -12px rgba(34,197,94,0.75);"
"                transition:all 160ms ease; }\n"
"button.green:hover { box-shadow:0 18px 42px -10px rgba(34,197,94,0.9); }\n"
"button.red    { background:linear-gradient(145deg,#fb7d7d,#dc2626);"
"                color:#fff; border-radius:15px;"
"                padding:15px 38px; font-weight:800; border:none; font-size:15px;"
"                box-shadow:0 14px 34px -12px rgba(239,68,68,0.7);"
"                transition:all 160ms ease; }\n"
"button.red:hover { box-shadow:0 18px 42px -10px rgba(239,68,68,0.9); }\n"
"button.blue   { background:linear-gradient(145deg,#4a90f6,#1d4ed8);"
"                color:#fff; border-radius:15px;"
"                padding:12px 28px; font-weight:800; border:none; font-size:14px;"
"                box-shadow:0 14px 34px -12px rgba(59,130,246,0.75);"
"                transition:all 160ms ease; }\n"
"button.blue:hover { box-shadow:0 18px 42px -10px rgba(59,130,246,0.95); }\n"
".alert-win   { background-color:#1a0000;"
"               background-image:radial-gradient(circle at 50% 32%, #4a0c0c 0%, #240202 50%, #120000 100%);}\n"
".alert-badge { color:#fff; font-size:26px; font-weight:800;"
"               background:linear-gradient(145deg,#fb7d7d,#dc2626);"
"               border-radius:999px; padding:13px 44px;"
"               box-shadow:0 0 50px -6px rgba(239,68,68,0.9);"
"               animation:badgePulse 1.4s ease-in-out infinite; }\n"
".alert-title { color:#ff6b6b; font-size:84px; font-weight:900; letter-spacing:-2px;"
"               text-shadow:0 0 40px rgba(255,82,82,0.7); }\n"
".alert-db    { color:#ff1744; font-size:180px; font-weight:900; letter-spacing:-6px;"
"               text-shadow:0 0 60px rgba(255,23,68,0.85);"
"               animation:dbGlow 1.4s ease-in-out infinite; }\n"
".alert-unit  { color:#ff8a80; font-size:40px; font-weight:700; }\n"
".alert-sub   { color:#ffab91; font-size:26px; }\n"
".alert-class { color:#ffb4a0; font-size:21px; font-weight:700;"
"               background:linear-gradient(145deg,#3d0c0c,#280707); border:1px solid #661c1c;"
"               border-radius:999px; padding:9px 28px;"
"               box-shadow:0 10px 28px -10px rgba(239,68,68,0.6); }\n"
)


class OzBelApp:
    def __init__(self):
        self.cfg = load_config()
        # Ayarlar yalnizca bu tahtaya ozeldir (yerel config.json)
        self.password  = self.cfg.get("password") or DEFAULT_PASSWORD
        self.threshold = int(self.cfg.get("threshold") or THRESHOLD)

        provider = Gtk.CssProvider()
        try:
            provider.load_from_data(CSS.encode())
        except Exception:
            pass  # CSS parse hatasinda uygulama yine de acilsin
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.win = Gtk.Window(title="ÖzBel")
        self.win.set_default_size(1000, 700)
        self.win.maximize()
        self.win.connect("destroy", self.quit)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.overlay = Gtk.Overlay()
        self.overlay.add(self.stack)
        self.win.add(self.overlay)

        self.build_setup()
        self.build_ready()
        self.build_alert()
        self.build_dbwin()
        self.build_tray()
        self.build_corner_qr()

        self.win.show_all()
        self.stack.set_visible_child_name("setup")

        self.alert_open   = False
        self.alert_src    = None
        self.alert_count  = 0
        self.alert_max_db = 0
        self.connect_time = None
        self.timer_src    = None
        self._sound_cooldown = 0
        self.mic_active   = False  # ready ekranina gecildi mi
        self.ai_active    = False  # telefonda YAMNet calisiyor mu
        self.last_noise   = False  # AI son karari: gurultu mu
        self.noise_time   = 0      # son AI karari zamani

        self.relay = FirebaseRelay(self)
        self.relay.start()

    # ── Köşe elemanları ──
    def build_corner_qr(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_halign(Gtk.Align.END)
        box.set_valign(Gtk.Align.END)
        box.set_margin_end(18)
        box.set_margin_bottom(18)

        qr_path = make_qr(NETLIFY_URL, 3)
        if qr_path and os.path.exists(qr_path):
            img = Gtk.Image()
            img.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(qr_path, 90, 90, True))
            box.pack_start(img, False, False, 0)

        lbl = Gtk.Label()
        lbl.set_markup(
            '<span foreground="#8b949e" font_size="9000">'
            'Telefonunuzdan kamera uygulamasını\naçıp bu küçük karekodu okutunuz'
            '</span>'
        )
        lbl.set_justify(Gtk.Justification.CENTER)
        box.pack_start(lbl, False, False, 0)

        self.corner_box = box
        self.overlay.add_overlay(box)
        self.overlay.set_overlay_pass_through(box, True)

        # Sol alt butonlar
        btn_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        btn_col.set_halign(Gtk.Align.START)
        btn_col.set_valign(Gtk.Align.END)
        btn_col.set_margin_start(18)
        btn_col.set_margin_bottom(18)

        upd_btn = Gtk.Button(label="Güncelleme Denetle")
        upd_btn.get_style_context().add_class("outline")
        upd_btn.connect("clicked", self.check_update)
        btn_col.pack_start(upd_btn, False, False, 0)

        stats_btn = Gtk.Button(label="İstatistikleri Göster")
        stats_btn.get_style_context().add_class("outline")
        stats_btn.connect("clicked", self.show_stats_log)
        btn_col.pack_start(stats_btn, False, False, 0)

        self.corner_btns = btn_col
        self.overlay.add_overlay(btn_col)
        self.overlay.set_overlay_pass_through(btn_col, False)

    def _hide_corners(self):
        self.corner_box.hide()
        self.corner_btns.hide()

    def _show_corners(self):
        self.corner_box.show()
        self.corner_btns.show()

    # ── Güncelleme ──
    def check_update(self, *_):
        threading.Thread(target=self._do_check_update, daemon=True).start()

    def _gh_fetch(self, url, timeout=15):
        # GitHub API'den ham dosya içeriği — raw CDN önbelleğine takılmaz
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github.raw",
            "User-Agent": "ozbel-updater",
            "Cache-Control": "no-cache",
        })
        return urllib.request.urlopen(req, timeout=timeout).read()

    def _do_check_update(self):
        try:
            resp = self._gh_fetch(UPDATE_JSON, timeout=10)
            info = json.loads(resp)
            latest    = info.get("version", "")
            py_url    = info.get("url", "")
            changelog = info.get("changelog", [])
        except Exception as e:
            GLib.idle_add(self._update_dialog, "error", str(e))
            return

        if not latest or not py_url:
            GLib.idle_add(self._update_dialog, "error", "Sunucu yanıtı geçersiz.")
            return

        if latest == APP_VERSION:
            GLib.idle_add(self._update_dialog, "latest", latest)
            return

        GLib.idle_add(self._update_dialog, "available", latest, py_url, changelog)

    def _update_dialog(self, state, *args):
        if state == "error":
            dlg = Gtk.MessageDialog(transient_for=self.win,
                message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK,
                text="Güncelleme Kontrolü Başarısız")
            dlg.format_secondary_text(args[0])
            dlg.run(); dlg.destroy()

        elif state == "latest":
            dlg = Gtk.MessageDialog(transient_for=self.win,
                message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
                text="Güncel")
            dlg.format_secondary_text(f"ÖzBel {APP_VERSION} zaten en güncel sürüm.")
            dlg.run(); dlg.destroy()

        elif state == "available":
            latest, py_url, changelog = args
            log_text = "\n".join(f"• {c}" for c in changelog) if changelog else "—"

            dlg = Gtk.Dialog(title="Güncelleme Mevcut", transient_for=self.win, modal=True)
            dlg.set_default_size(440, 300)
            dlg.add_button("Vazgeç", Gtk.ResponseType.NO)
            ok_btn = dlg.add_button("Güncelle", Gtk.ResponseType.YES)
            ok_btn.get_style_context().add_class("blue")
            dlg.set_default_response(Gtk.ResponseType.YES)

            content = dlg.get_content_area()
            content.set_spacing(10)
            content.set_margin_top(16); content.set_margin_bottom(8)
            content.set_margin_start(20); content.set_margin_end(20)

            head = Gtk.Label()
            head.set_markup(f"<b>v{APP_VERSION}  →  v{latest}</b>")
            head.set_halign(Gtk.Align.START)
            content.pack_start(head, False, False, 0)

            yenilik = Gtk.Label(label="Yenilikler:")
            yenilik.set_halign(Gtk.Align.START)
            content.pack_start(yenilik, False, False, 0)

            # Kaydırılabilir changelog — uzasa bile butonlar görünür kalır
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_min_content_height(120)
            scroll.set_max_content_height(160)
            log_lbl = Gtk.Label(label=log_text)
            log_lbl.set_halign(Gtk.Align.START)
            log_lbl.set_xalign(0)
            log_lbl.set_line_wrap(True)
            scroll.add(log_lbl)
            content.pack_start(scroll, True, True, 0)

            foot = Gtk.Label(label="İndirilip uygulama yeniden başlatılacak.")
            foot.set_halign(Gtk.Align.START)
            content.pack_start(foot, False, False, 0)

            dlg.show_all()
            resp = dlg.run(); dlg.destroy()
            if resp == Gtk.ResponseType.YES:
                threading.Thread(target=self._do_install_update,
                                 args=(py_url,), daemon=True).start()

    def _do_install_update(self, py_url):
        GLib.idle_add(self._show_updating)
        try:
            os.makedirs(USER_DIR, exist_ok=True)
            dest = os.path.join(USER_DIR, "ozbel.py")
            # İndirme de API üzerinden — güncel .py'yi kesin alır (önbellek takılmaz)
            content = self._gh_fetch(PY_DOWNLOAD, timeout=30)
            with open(dest, "wb") as f:
                f.write(content)
            os.chmod(dest, 0o755)
            self._update_dest = dest
        except Exception as e:
            GLib.idle_add(self._update_dialog, "error", f"İndirme hatası: {e}")
            return
        GLib.idle_add(self._restart_app)

    def _show_updating(self):
        dlg = Gtk.MessageDialog(transient_for=self.win,
            message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.NONE,
            text="Güncelleme İndiriliyor…")
        dlg.format_secondary_text("Lütfen bekleyin.")
        dlg.show_all()
        self._updating_dlg = dlg

    def _restart_app(self):
        try: self._updating_dlg.destroy()
        except Exception: pass
        new_file = getattr(self, '_update_dest', os.path.abspath(__file__))
        subprocess.Popen(["python3", new_file],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        GLib.timeout_add(800, self._do_quit)

    def _do_quit(self):
        try: self.relay.running = False
        except Exception: pass
        Gtk.main_quit()
        return False

    # ── Ayarlar ──
    def show_class_dialog(self, *_):
        if not self._ask_password():
            return
        self._open_settings()

    def _ask_password(self):
        dlg = Gtk.Dialog(title="Şifre Gerekli", transient_for=self.win, modal=True)
        dlg.set_default_size(360, 150)
        content = dlg.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(20); content.set_margin_bottom(16)
        content.set_margin_start(24); content.set_margin_end(24)
        lbl = Gtk.Label(label="Ayarları açmak için şifreyi girin:")
        lbl.set_halign(Gtk.Align.START)
        content.pack_start(lbl, False, False, 0)
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_placeholder_text("Şifre")
        content.pack_start(entry, False, False, 0)
        dlg.add_button("İptal", Gtk.ResponseType.CANCEL)
        ok_btn = dlg.add_button("Onayla", Gtk.ResponseType.OK)
        ok_btn.get_style_context().add_class("blue")
        dlg.set_default_response(Gtk.ResponseType.OK)
        entry.connect("activate", lambda *_: dlg.response(Gtk.ResponseType.OK))
        dlg.show_all()
        resp = dlg.run()
        pw = entry.get_text()
        dlg.destroy()
        if resp != Gtk.ResponseType.OK:
            return False
        if pw == self.password:
            return True
        err = Gtk.MessageDialog(transient_for=self.win,
            message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK,
            text="Hatalı Şifre")
        err.format_secondary_text("Ayarlar açılamadı.")
        err.run(); err.destroy()
        return False

    def _settings_row(self, label_text):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl = Gtk.Label(label=label_text)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_xalign(0)
        lbl.set_size_request(150, -1)
        row.pack_start(lbl, False, False, 0)
        return row

    def _open_settings(self, *_):
        dlg = Gtk.Dialog(title="ÖzBel — Ayarlar", transient_for=self.win, modal=True)
        dlg.set_default_size(440, 420)
        content = dlg.get_content_area()
        content.set_spacing(14)
        content.set_margin_top(20); content.set_margin_bottom(16)
        content.set_margin_start(26); content.set_margin_end(26)

        title = Gtk.Label()
        title.set_markup('<b>Bu Tahtanın Ayarları</b>')
        title.set_halign(Gtk.Align.START)
        content.pack_start(title, False, False, 0)
        info = Gtk.Label(label="Ayarlar yalnızca bu tahtaya kaydedilir.")
        info.set_halign(Gtk.Align.START)
        info.get_style_context().add_class("subtitle")
        content.pack_start(info, False, False, 0)

        # Sınıf adı
        r1 = self._settings_row("Sınıf adı")
        e_class = Gtk.Entry()
        e_class.set_placeholder_text("Örnek: 7-F")
        e_class.set_text(self.cfg.get("class_name", ""))
        e_class.set_hexpand(True)
        r1.pack_start(e_class, True, True, 0)
        content.pack_start(r1, False, False, 0)

        # Uyarı eşiği (dB)
        r2 = self._settings_row("Kaç dB'de ötsün")
        adj = Gtk.Adjustment(value=self.threshold, lower=60, upper=120, step_increment=1, page_increment=5)
        sp_db = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        sp_db.set_value(self.threshold)
        r2.pack_start(sp_db, False, False, 0)
        content.pack_start(r2, False, False, 0)

        # Başlangıçta otomatik aç
        r3 = self._settings_row("Sistemle başlat")
        sw_auto = Gtk.Switch()
        sw_auto.set_active(self._autostart_enabled())
        sw_auto.set_halign(Gtk.Align.START)
        r3.pack_start(sw_auto, False, False, 0)
        content.pack_start(r3, False, False, 0)

        # Şifre değiştir
        r4 = self._settings_row("Yeni şifre")
        e_pw = Gtk.Entry()
        e_pw.set_visibility(False)
        e_pw.set_placeholder_text("Boş bırakırsan değişmez")
        e_pw.set_hexpand(True)
        r4.pack_start(e_pw, True, True, 0)
        content.pack_start(r4, False, False, 0)

        content.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 6)

        # Tamamen sil
        del_btn = Gtk.Button(label="🗑  Uygulamayı Tamamen Sil")
        del_btn.get_style_context().add_class("red")
        del_btn.connect("clicked", lambda *_: self._confirm_uninstall(dlg))
        content.pack_start(del_btn, False, False, 0)

        dlg.add_button("İptal", Gtk.ResponseType.CANCEL)
        ok_btn = dlg.add_button("Kaydet", Gtk.ResponseType.OK)
        ok_btn.get_style_context().add_class("blue")
        dlg.set_default_response(Gtk.ResponseType.OK)

        dlg.show_all()
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            name = e_class.get_text().strip()
            self.cfg["class_name"] = name
            self.threshold = int(sp_db.get_value())
            self.cfg["threshold"] = self.threshold
            new_pw = e_pw.get_text().strip()
            if new_pw:
                self.password = new_pw
                self.cfg["password"] = new_pw
            self._set_autostart(sw_auto.get_active())
            self.cfg["autostart"] = sw_auto.get_active()
            save_config(self.cfg)
            self._update_class_label()
        dlg.destroy()

    # ── Otomatik başlatma (kullanıcıya özel) ──
    def _autostart_enabled(self):
        if os.path.exists(AUTOSTART_FILE):
            try:
                with open(AUTOSTART_FILE, encoding="utf-8") as f:
                    return "Hidden=true" not in f.read()
            except Exception:
                return True
        # Dosya yoksa sistem autostart'i (varsa) gecerli kabul et
        return self.cfg.get("autostart", True)

    def _set_autostart(self, enabled):
        try:
            os.makedirs(os.path.dirname(AUTOSTART_FILE), exist_ok=True)
            if enabled:
                with open(AUTOSTART_FILE, "w", encoding="utf-8") as f:
                    f.write(
                        "[Desktop Entry]\nType=Application\nName=ÖzBel\n"
                        "Exec=ozbel\nIcon=audio-volume-high\nTerminal=false\n"
                        "X-GNOME-Autostart-enabled=true\nX-GNOME-Autostart-Delay=5\n")
            else:
                # Sistem genelindeki autostart'i da bastirmak icin Hidden=true
                with open(AUTOSTART_FILE, "w", encoding="utf-8") as f:
                    f.write(
                        "[Desktop Entry]\nType=Application\nName=ÖzBel\n"
                        "Exec=ozbel\nHidden=true\nX-GNOME-Autostart-enabled=false\n")
        except Exception:
            pass

    # ── Tamamen sil ──
    def _confirm_uninstall(self, parent):
        dlg = Gtk.MessageDialog(transient_for=parent,
            message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.YES_NO,
            text="Uygulamayı Tamamen Sil")
        dlg.format_secondary_text(
            "ÖzBel bu tahtadan kaldırılacak: ayarlar, kayıtlar ve "
            "otomatik başlatma silinecek, uygulama kapanacak.\n\nEmin misiniz?")
        resp = dlg.run(); dlg.destroy()
        if resp != Gtk.ResponseType.YES:
            return
        self._do_uninstall()

    def _do_uninstall(self):
        # Kullanici verilerini ve autostart'i temizle
        try: shutil.rmtree(USER_DIR, ignore_errors=True)
        except Exception: pass
        try:
            if os.path.exists(AUTOSTART_FILE):
                os.remove(AUTOSTART_FILE)
        except Exception: pass
        # Sistem paketini kaldirmayi dene (yetki gerekebilir)
        removed = False
        for cmd in (["pkexec", "apt-get", "remove", "-y", "ozbel"],
                    ["pkexec", "dpkg", "-r", "ozbel"]):
            try:
                if subprocess.call(cmd) == 0:
                    removed = True
                    break
            except Exception:
                continue
        msg = Gtk.MessageDialog(transient_for=self.win,
            message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
            text="ÖzBel Kaldırıldı")
        if removed:
            msg.format_secondary_text("Uygulama tamamen kaldırıldı. Pencere kapanacak.")
        else:
            msg.format_secondary_text(
                "Ayarlar ve veriler silindi, uygulama kapanıyor.\n"
                "Sistemden tamamen kaldırmak için yönetici hesabında:\n"
                "sudo apt remove ozbel")
        msg.run(); msg.destroy()
        self.quit()

    def _update_class_label(self):
        name = self.cfg.get("class_name", "")
        if name:
            self.class_lbl.set_text(f"{name} — Test Aşamasında Çalışılıyor")
        else:
            self.class_lbl.set_text("Sınıf ayarlanmadı")

    # ── İstatistik logu ──
    def show_stats_log(self, *_):
        try:
            if not os.path.exists(STATS_FILE):
                text = "Henüz hiç ders istatistiği kaydedilmedi."
            else:
                with open(STATS_FILE, encoding="utf-8") as f:
                    lines = f.readlines()
                text = "".join(lines[-30:]) if lines else "Kayıt boş."
        except Exception as e:
            text = f"Hata: {e}"
        dlg = Gtk.MessageDialog(transient_for=self.win,
            message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK,
            text="Ders İstatistikleri (Son 30)")
        dlg.format_secondary_text(text)
        dlg.run(); dlg.destroy()

    # ── Tepsi ──
    def build_tray(self):
        try:
            self.tray = Gtk.StatusIcon.new_from_icon_name("audio-volume-high")
            self.tray.set_title("ÖzBel")
            self.tray.set_tooltip_text("ÖzBel — Kulak Sağlığı")
            # Hoparlor ikonuna basinca sol alt kutu gizlen/gorun (toggle)
            self.tray.connect("activate", lambda *_: self.toggle_dbwin())
            self.tray.connect("popup-menu", self.on_tray_menu)
            self.tray.set_visible(False)
        except Exception:
            self.tray = None

    def on_tray_menu(self, icon, button, t):
        m = Gtk.Menu()
        h = Gtk.MenuItem(label="ÖzBel — Yönetim")
        h.set_sensitive(False); m.append(h)
        m.append(Gtk.SeparatorMenuItem())
        i1 = Gtk.MenuItem(label="Göster / Gizle")
        i1.connect("activate", lambda *_: self.toggle_dbwin()); m.append(i1)
        i2 = Gtk.MenuItem(label="Bağlantıyı Kes")
        i2.connect("activate", self.disconnect_teacher); m.append(i2)
        m.show_all()
        m.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, t)

    # ── Sol alt sabit kontrol kutusu ──
    def build_dbwin(self):
        self.dbwin = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.dbwin.set_decorated(False)        # baslik cubugu yok -> tasinamaz
        self.dbwin.set_resizable(False)
        self.dbwin.set_keep_above(True)
        self.dbwin.set_skip_taskbar_hint(True)
        self.dbwin.set_skip_pager_hint(True)
        self.dbwin.set_accept_focus(False)
        self.dbwin.connect("delete-event", lambda *a: (self.dbwin.hide() or True))

        self.db_visible = False

        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        b.get_style_context().add_class("dock")
        b.set_margin_top(16); b.set_margin_bottom(16)
        b.set_margin_start(18); b.set_margin_end(18)

        hdr = Gtk.Label(); hdr.set_markup('<b>ÖzBel</b>')
        hdr.set_halign(Gtk.Align.CENTER)
        b.pack_start(hdr, False, False, 0)

        self.dbwin_val = Gtk.Label(label="—  dB")
        self.dbwin_val.get_style_context().add_class("db-live")
        self.dbwin_val.set_halign(Gtk.Align.CENTER)
        self.dbwin_val.set_no_show_all(True)   # show_all gizliyi acmasin
        b.pack_start(self.dbwin_val, False, False, 0)

        self.db_btn = Gtk.Button(label="Desibel Ölç")
        self.db_btn.get_style_context().add_class("outline")
        self.db_btn.connect("clicked", self.toggle_db_value)
        b.pack_start(self.db_btn, False, False, 0)

        dc = Gtk.Button(label="Bağlantıyı Kes")
        dc.get_style_context().add_class("red")
        dc.connect("clicked", self.disconnect_teacher)
        b.pack_start(dc, False, False, 0)

        self.dbwin.add(b)

    def toggle_db_value(self, *_):
        self.db_visible = not self.db_visible
        self.dbwin_val.set_visible(self.db_visible)
        self.db_btn.set_label("Gizle" if self.db_visible else "Desibel Ölç")
        self._place_dbwin()

    def _place_dbwin(self):
        # Sol alt koseye sabitle
        try:
            screen = self.dbwin.get_screen()
            sh = screen.get_height()
            _, h = self.dbwin.get_size()
            self.dbwin.move(20, sh - h - 60)
        except Exception:
            pass

    def show_dbwin(self):
        self.dbwin_val.set_visible(self.db_visible)
        self.dbwin.show()
        self.dbwin.get_child().show_all()
        self.dbwin_val.set_visible(self.db_visible)
        self._place_dbwin()
        GLib.timeout_add(50, lambda: (self._place_dbwin(), False)[1])

    def toggle_dbwin(self):
        if self.dbwin.get_visible():
            self.dbwin.hide()
        else:
            self.show_dbwin()

    def hide_dbwin(self):
        try: self.dbwin.hide()
        except Exception: pass

    # ── Kurulum ekranı ──
    def build_setup(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_halign(Gtk.Align.FILL); outer.set_valign(Gtk.Align.FILL)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_halign(Gtk.Align.CENTER); box.set_valign(Gtk.Align.CENTER)
        box.set_margin_top(32); box.set_margin_bottom(32)
        box.set_margin_start(40); box.set_margin_end(40)

        logo_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        logo_row.set_halign(Gtk.Align.CENTER)
        l1 = Gtk.Label(label="Öz"); l1.get_style_context().add_class("logo-text")
        l2 = Gtk.Label(label="Bel"); l2.get_style_context().add_class("logo-blue")
        logo_row.pack_start(l1, False, False, 0)
        logo_row.pack_start(l2, False, False, 0)
        box.pack_start(logo_row, False, False, 0)

        sub = Gtk.Label(label="Akıllı Tahta  •  Kulak Sağlığı Koruma Sistemi")
        sub.get_style_context().add_class("subtitle")
        sub.set_halign(Gtk.Align.CENTER)
        box.pack_start(sub, False, False, 0)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=32)
        hbox.set_halign(Gtk.Align.CENTER)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.get_style_context().add_class("card")
        card.set_margin_top(4)

        ct = Gtk.Label(label="Nasıl Başlanır?")
        ct.get_style_context().add_class("card-title")
        ct.set_halign(Gtk.Align.START)
        card.pack_start(ct, False, False, 0)

        steps = [
            ("1", "Sağdaki QR kodu", "telefon kameranızla okutun"),
            ("2", "Açılan sayfada", "mikrofon iznini verin"),
            ("3", "Sistem hazır —", "90 dB'i aşınca uyarı çıkar"),
        ]
        for num, bold, rest in steps:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.set_margin_top(2)
            n = Gtk.Label(label=num); n.get_style_context().add_class("step-num")
            n.set_valign(Gtk.Align.CENTER)
            row.pack_start(n, False, False, 0)
            txt_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            b_lbl = Gtk.Label(label=bold); b_lbl.get_style_context().add_class("step-txt-b")
            b_lbl.set_halign(Gtk.Align.START)
            r_lbl = Gtk.Label(label=rest); r_lbl.get_style_context().add_class("step-txt")
            r_lbl.set_halign(Gtk.Align.START)
            txt_box.pack_start(b_lbl, False, False, 0)
            txt_box.pack_start(r_lbl, False, False, 0)
            row.pack_start(txt_box, False, False, 0)
            card.pack_start(row, False, False, 0)

        hbox.pack_start(card, False, False, 0)

        qr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        qr_box.set_halign(Gtk.Align.CENTER)
        self.qr_img = Gtk.Image()
        qr_box.pack_start(self.qr_img, False, False, 0)
        self.code_lbl = Gtk.Label(label=SESSION)
        self.code_lbl.get_style_context().add_class("code")
        self.code_lbl.set_halign(Gtk.Align.CENTER)
        qr_box.pack_start(self.code_lbl, False, False, 0)
        ql = Gtk.Label(label="Kameranızla okutun")
        ql.get_style_context().add_class("qrlabel")
        ql.set_halign(Gtk.Align.CENTER)
        qr_box.pack_start(ql, False, False, 0)
        hbox.pack_start(qr_box, False, False, 0)

        box.pack_start(hbox, False, False, 0)

        self.pill = Gtk.Label(label="Öğretmen bekleniyor…")
        self.pill.get_style_context().add_class("pill")
        self.pill.set_halign(Gtk.Align.CENTER)
        box.pack_start(self.pill, False, False, 0)

        nob = Gtk.Button(label="Kapat")
        nob.get_style_context().add_class("outline")
        nob.set_halign(Gtk.Align.CENTER)
        nob.connect("clicked", self.quit)
        box.pack_start(nob, False, False, 0)

        ver = Gtk.Label(label=f"v{APP_VERSION}")
        ver.get_style_context().add_class("version")
        ver.set_halign(Gtk.Align.CENTER)
        box.pack_start(ver, False, False, 0)

        # Sınıf etiketi + değiştir butonu
        badge_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        badge_row.set_halign(Gtk.Align.CENTER)
        self.class_lbl = Gtk.Label(label="")
        self.class_lbl.get_style_context().add_class("class-badge")
        badge_row.pack_start(self.class_lbl, False, False, 0)
        change_btn = Gtk.Button(label="⚙ Ayarlar")
        change_btn.get_style_context().add_class("small-outline")
        change_btn.connect("clicked", self.show_class_dialog)
        badge_row.pack_start(change_btn, False, False, 0)
        box.pack_start(badge_row, False, False, 4)

        self._update_class_label()

        outer.pack_start(box, True, True, 0)
        self.stack.add_named(outer, "setup")

    # ── Hazır ekranı ──
    def build_ready(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER); box.set_valign(Gtk.Align.CENTER)

        ico = Gtk.Label(); ico.set_markup('<span size="80000">🎙️</span>')
        box.pack_start(ico, False, False, 0)

        rl = Gtk.Label(label="● Sistem Aktif")
        rl.get_style_context().add_class("ready-label")
        rl.set_halign(Gtk.Align.CENTER)
        box.pack_start(rl, False, False, 0)

        rs = Gtk.Label(label="Öğretmenin telefon mikrofonu bağlı — anlık ölçüm yapılıyor")
        rs.get_style_context().add_class("ready-sub")
        rs.set_halign(Gtk.Align.CENTER)
        box.pack_start(rs, False, False, 0)

        db_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        db_row.set_halign(Gtk.Align.CENTER)
        self.db_live = Gtk.Label(label="—")
        self.db_live.get_style_context().add_class("db-huge")
        db_unit = Gtk.Label(label="dB")
        db_unit.get_style_context().add_class("db-unit")
        db_unit.set_valign(Gtk.Align.END)
        db_unit.set_margin_bottom(14)
        db_row.pack_start(self.db_live, False, False, 0)
        db_row.pack_start(db_unit, False, False, 0)
        box.pack_start(db_row, False, False, 0)

        self.conn_time_lbl = Gtk.Label(label="")
        self.conn_time_lbl.get_style_context().add_class("conn-timer")
        self.conn_time_lbl.set_halign(Gtk.Align.CENTER)
        box.pack_start(self.conn_time_lbl, False, False, 0)

        btn = Gtk.Button(label="Bağlantıyı Kes")
        btn.get_style_context().add_class("red")
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", self.disconnect_teacher)
        box.pack_start(btn, False, False, 0)

        self.stack.add_named(box, "ready")

    # ── Uyarı ekranı ──
    def build_alert(self):
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        b.get_style_context().add_class("alert-win")
        b.set_halign(Gtk.Align.CENTER); b.set_valign(Gtk.Align.CENTER)

        badge = Gtk.Label(label="⚠  GÜRÜLTÜ UYARISI")
        badge.get_style_context().add_class("alert-badge")
        badge.set_halign(Gtk.Align.CENTER)
        b.pack_start(badge, False, False, 0)

        ti = Gtk.Label(label="LÜTFEN SESSİZ OLUN!")
        ti.get_style_context().add_class("alert-title")
        ti.set_halign(Gtk.Align.CENTER)
        b.pack_start(ti, False, False, 0)

        db_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        db_row.set_halign(Gtk.Align.CENTER)
        self.alert_db = Gtk.Label(label="—")
        self.alert_db.get_style_context().add_class("alert-db")
        unit = Gtk.Label(label="dB")
        unit.get_style_context().add_class("alert-unit")
        unit.set_valign(Gtk.Align.END)
        unit.set_margin_bottom(28)
        db_row.pack_start(self.alert_db, False, False, 0)
        db_row.pack_start(unit, False, False, 0)
        b.pack_start(db_row, False, False, 0)

        sub = Gtk.Label(label="Kulak sağlığı için ses seviyesi 90 dB'nin altında olmalıdır")
        sub.get_style_context().add_class("alert-sub")
        sub.set_halign(Gtk.Align.CENTER)
        b.pack_start(sub, False, False, 0)

        self.alert_class = Gtk.Label(label="")
        self.alert_class.get_style_context().add_class("alert-class")
        self.alert_class.set_halign(Gtk.Align.CENTER)
        b.pack_start(self.alert_class, False, False, 0)

        self.stack.add_named(b, "alert")

    def gen_qr(self):
        p = make_qr(f"{NETLIFY_URL}/?s={SESSION}", 9)
        if p and os.path.exists(p):
            self.qr_img.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(p, 260, 260, True))

    # ── Olaylar ──
    def on_teacher_connected(self):
        self.pill.set_text("📱 Telefon bağlandı — mikrofon bekleniyor…")
        ctx = self.pill.get_style_context()
        ctx.remove_class("pill"); ctx.remove_class("pill-warn")
        ctx.add_class("pill-ok")

    def on_teacher_gone(self):
        self._stop_timer()
        self.last_noise = False
        self.mic_active = False
        self.restore_main()
        self.pill.set_text("⚠ Bağlantı kesildi — tekrar QR okutun")
        ctx = self.pill.get_style_context()
        ctx.remove_class("pill-ok"); ctx.remove_class("pill")
        ctx.add_class("pill-warn")

    def on_mic_ready(self):
        if self.mic_active:
            return  # zaten gecildi
        self.mic_active   = True
        self.connect_time = time.time()
        self.stack.set_visible_child_name("ready")
        self.win.hide()
        if self.tray:
            self.tray.set_visible(True)
        self.show_dbwin()
        if self.timer_src:
            GLib.source_remove(self.timer_src)
        self.timer_src = GLib.timeout_add_seconds(1, self._update_timer)

    def _update_timer(self):
        if self.connect_time is None:
            self.timer_src = None
            return False
        elapsed = int(time.time() - self.connect_time)
        m, s = divmod(elapsed, 60)
        self.conn_time_lbl.set_text(f"Bağlı: {m} dk {s:02d} sn")
        return True

    def _stop_timer(self):
        if self.timer_src:
            GLib.source_remove(self.timer_src)
            self.timer_src = None
        self.connect_time = None
        self.conn_time_lbl.set_text("")

    def on_ai(self, active):
        self.ai_active = active

    def on_noise(self, is_noise):
        self.last_noise = is_noise
        self.noise_time = time.time()

    def on_db(self, db):
        # dB akiyorsa mikrofon kesin aktiftir; "mic" event'i kacsa bile ekrani gecir
        if not self.mic_active:
            self.on_mic_ready()

        self.db_live.set_text(f"{db}  dB")
        self.dbwin_val.set_text(f"{db}  dB")

        # 90 dB asilmadiysa hicbir sey yapma
        if db < self.threshold:
            return

        # GUVENLIK AGI: cok yuksek ses (esik+6, orn. 96+) zaten zararli —
        # AI ne derse desin (bagiris/islik konusma sanilsa bile) OT.
        if db >= self.threshold + 6:
            self.show_alert(db)
            return

        # Esik..esik+6 arasi: tek kisi yuksekce konusuyor olabilir.
        # Yapay zeka aktifse SADECE taze 'gurultu' karariyla ot.
        if self.ai_active:
            fresh = (time.time() - self.noise_time) < NOISE_FRESH_SEC
            if not (fresh and self.last_noise):
                return
        self.show_alert(db)

    def on_lesson_end(self):
        self._stop_timer()
        self.hide_alert()
        self.show_lesson_summary()
        self.restore_main()
        self.pill.set_text("Öğretmen bekleniyor…")
        ctx = self.pill.get_style_context()
        ctx.remove_class("pill-ok"); ctx.remove_class("pill-warn")
        ctx.add_class("pill")
        self.alert_count  = 0
        self.alert_max_db = 0
        self.last_noise   = False
        self.mic_active   = False

    def show_lesson_summary(self):
        class_name = self.cfg.get("class_name", "")
        log_stats(class_name, self.alert_count, self.alert_max_db)

        if self.alert_count == 0:
            msg = "Bu ders boyunca hiç gürültü uyarısı verilmedi. 👏"
            sec = "Sınıf tüm ders boyunca 90 dB sınırının altında kaldı."
        else:
            msg = f"Ders Özeti — {self.alert_count} kez uyarı verildi"
            sec = (
                f"🔔  Uyarı sayısı  : {self.alert_count} kez\n"
                f"📈  En yüksek ses : {self.alert_max_db} dB\n\n"
                "Kulak sağlığı için ses seviyesinin 90 dB altında tutulması önerilir."
            )
        dlg = Gtk.MessageDialog(
            transient_for=self.win,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=msg)
        dlg.format_secondary_text(sec)
        dlg.run()
        dlg.destroy()

    def restore_main(self):
        self.hide_dbwin()
        if self.tray:
            self.tray.set_visible(False)
        self.stack.set_visible_child_name("setup")
        self._show_corners()
        self.win.show_all()
        self.win.present()

    # ── Uyarı ──
    def show_alert(self, db):
        self.alert_db.set_text(f"{db}")
        if db > self.alert_max_db:
            self.alert_max_db = db
        if not self.alert_open:
            self.alert_open  = True
            self.alert_count += 1
            cn = self.cfg.get("class_name", "")
            self.alert_class.set_text(f"📍 {cn}" if cn else "")
            self._hide_corners()
            self.stack.set_visible_child_name("alert")
            self.win.show_all()
            self.alert_class.set_visible(bool(cn))
            self._hide_corners()
            self.win.fullscreen()
            self.win.present()
        now = time.time()
        if now - self._sound_cooldown >= 3:
            self._sound_cooldown = now
            threading.Thread(target=play_alert_sound, daemon=True).start()
        if self.alert_src:
            GLib.source_remove(self.alert_src)
        self.alert_src = GLib.timeout_add_seconds(6, self._auto_hide)

    def _auto_hide(self):
        self.hide_alert(); self.alert_src = None; return False

    def hide_alert(self):
        if self.alert_open:
            self.alert_open = False
            self.win.unfullscreen()
            self._show_corners()
            self.stack.set_visible_child_name("ready")
            self.win.hide()

    def disconnect_teacher(self, *_):
        self._stop_timer()
        self.last_noise = False
        self.mic_active = False
        self.relay.put("control", "disconnect")
        self.restore_main()
        self.pill.set_text("Öğretmen bekleniyor…")
        ctx = self.pill.get_style_context()
        ctx.remove_class("pill-ok"); ctx.remove_class("pill-warn")
        ctx.add_class("pill")
        self.hide_alert()

    def quit(self, *_):
        try: self.relay.running = False
        except Exception: pass
        Gtk.main_quit()

    def run(self):
        self.gen_qr()
        Gtk.main()


if __name__ == "__main__":
    if "XXXX" in FIREBASE_DB or "XXXX" in NETLIFY_URL:
        dlg = Gtk.MessageDialog(
            message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK,
            text="ÖzBel yapılandırılmamış")
        dlg.format_secondary_text(
            "ozbel.py içindeki FIREBASE_DB ve NETLIFY_URL adreslerini doldurun.")
        dlg.run(); dlg.destroy()
    OzBelApp().run()
