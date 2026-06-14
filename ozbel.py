#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ÖzBel — Akıllı Tahta Kulak Sağlığı Sistemi
Native Pardus uygulaması (Python + GTK3)
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf

import os, sys, json, threading, subprocess, tempfile, random, string, time, shutil
import urllib.request, urllib.error
from datetime import datetime

# =================== CONFIG ===================
FIREBASE_DB = "https://ozbel-eb6af-default-rtdb.europe-west1.firebasedatabase.app"
NETLIFY_URL = "https://glistening-fudge-bca794.netlify.app"
# ==============================================

APP_VERSION = "1.3.0"
UPDATE_JSON = "https://raw.githubusercontent.com/ozguroyunuzmn/ozbel/main/version.json"

SESSION   = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
APP_DIR   = os.path.dirname(os.path.abspath(__file__))
THRESHOLD = 90
CLASS_PASSWORD = "etap+pardus+ozbel!"

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

def play_alert_sound():
    cmds = [
        ["paplay", "/usr/share/sounds/freedesktop/stereo/bell.oga"],
        ["aplay",  "/usr/share/sounds/alsa/Front_Left.wav"],
    ]
    for cmd in cmds:
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
            if "db" in d and d["db"] is not None:
                GLib.idle_add(self.app.on_db, int(d["db"]))
            if d.get("lesson") == "end": GLib.idle_add(self.app.on_lesson_end)
        elif path == "/teacher":
            GLib.idle_add(self.app.on_teacher_connected if d else self.app.on_teacher_gone)
        elif path == "/mic" and d:
            GLib.idle_add(self.app.on_mic_ready)
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
".logo-text  { color:#f0f4f9; font-size:48px; font-weight:900; letter-spacing:-2px; }\n"
".logo-blue  { color:#3b82f6; font-size:48px; font-weight:900; letter-spacing:-2px; }\n"
".subtitle   { color:#94a3b8; font-size:14px; letter-spacing:.3px; }\n"
".code       { color:#60a5fa; font-size:32px; font-weight:900; letter-spacing:5px; }\n"
".qrlabel    { color:#94a3b8; font-size:11px; }\n"
".version    { color:#3a4452; font-size:11px; }\n"
".pill       { color:#93b4e8; font-size:14px; font-weight:600;"
"              background:#101a2e; border:1px solid #25344f;"
"              border-radius:999px; padding:8px 20px; }\n"
".pill-ok    { color:#4ade80; font-size:14px; font-weight:600;"
"              background:#0d2016; border:1px solid #1c4030;"
"              border-radius:999px; padding:8px 20px; }\n"
".pill-warn  { color:#f87171; font-size:14px; font-weight:600;"
"              background:#21100f; border:1px solid #4a2220;"
"              border-radius:999px; padding:8px 20px; }\n"
".card { background-color:#121821; border:1px solid #222c3a;"
"        border-radius:22px; padding:26px; }\n"
".card-title { color:#f0f4f9; font-size:16px; font-weight:800; }\n"
".step-num   { color:#93c5fd; font-size:12px; font-weight:800;"
"              background:#13243f; border:1px solid #25467a;"
"              border-radius:999px; padding:3px 10px; }\n"
".step-txt   { color:#94a3b8; font-size:13px; }\n"
".step-txt-b { color:#f0f4f9; font-size:13px; font-weight:700; }\n"
".db-huge  { color:#f0f4f9; font-size:80px; font-weight:900; letter-spacing:-2px; }\n"
".db-unit  { color:#94a3b8; font-size:18px; }\n"
".db-live  { color:#f0f4f9; font-size:40px; font-weight:900; }\n"
".db-ok    { color:#22c55e; font-size:40px; font-weight:900; }\n"
".db-warn  { color:#ef4444; font-size:40px; font-weight:900; }\n"
".db-mid   { color:#f59e0b; font-size:40px; font-weight:900; }\n"
".ready-label { color:#4ade80; font-size:22px; font-weight:800;"
"               background:#0d2016; border:1px solid #1c4030;"
"               border-radius:999px; padding:10px 28px; }\n"
".ready-sub   { color:#94a3b8; font-size:15px; }\n"
".conn-timer  { color:#4a5568; font-size:13px; font-weight:600; }\n"
".class-badge { color:#fbbf24; font-size:12px; font-weight:700;"
"               background:#1f1604; border:1px solid #4a3812;"
"               border-radius:999px; padding:4px 14px; }\n"
"button.outline { background:#0f1620; color:#94a3b8;"
"                 border:1px solid #2a3646; border-radius:12px;"
"                 padding:10px 22px; font-weight:600; }\n"
"button.outline:hover { background:#16202e; border-color:#3a4a5e; }\n"
"button.small-outline { background:transparent; color:#6080a8;"
"                       border:1px solid #25344f; border-radius:999px;"
"                       padding:3px 12px; font-size:11px; }\n"
"button.green  { background:linear-gradient(145deg,#34d399,#16a34a);"
"                color:#04140a; border-radius:14px;"
"                padding:14px 36px; font-weight:800; border:none; font-size:15px; }\n"
"button.red    { background:linear-gradient(145deg,#f87171,#dc2626);"
"                color:#fff; border-radius:14px;"
"                padding:14px 36px; font-weight:800; border:none; font-size:15px; }\n"
"button.blue   { background:linear-gradient(145deg,#3b82f6,#1d4ed8);"
"                color:#fff; border-radius:14px;"
"                padding:11px 26px; font-weight:800; border:none; font-size:14px; }\n"
".alert-win   { background-color:#1a0000;"
"               background-image:radial-gradient(circle at 50% 35%, #3a0a0a 0%, #1a0000 55%);}\n"
".alert-badge { color:#fff; font-size:24px; font-weight:800;"
"               background:linear-gradient(145deg,#f87171,#dc2626);"
"               border-radius:999px; padding:12px 40px; }\n"
".alert-title { color:#ff6b6b; font-size:80px; font-weight:900; letter-spacing:-2px; }\n"
".alert-db    { color:#ff1744; font-size:170px; font-weight:900; letter-spacing:-6px; }\n"
".alert-unit  { color:#ff8a80; font-size:38px; font-weight:700; }\n"
".alert-sub   { color:#ffab91; font-size:26px; }\n"
".alert-class { color:#ffb4a0; font-size:20px; font-weight:700;"
"               background:#330a0a; border:1px solid #661c1c;"
"               border-radius:999px; padding:8px 26px; }\n"
)


class OzBelApp:
    def __init__(self):
        self.cfg = load_config()

        provider = Gtk.CssProvider(); provider.load_from_data(CSS.encode())
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

    def _do_check_update(self):
        try:
            # Önbelleği atlamak için zaman damgası ekle
            url = UPDATE_JSON + "?t=" + str(int(time.time()))
            req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
            resp = urllib.request.urlopen(req, timeout=10).read()
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
            url = py_url + "?t=" + str(int(time.time()))
            req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=30) as r:
                content = r.read()
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

    # ── Sınıf adı ──
    def show_class_dialog(self, *_):
        if not self._ask_password():
            return
        self._open_class_dialog()

    def _ask_password(self):
        dlg = Gtk.Dialog(title="Şifre Gerekli", transient_for=self.win, modal=True)
        dlg.set_default_size(360, 150)
        content = dlg.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(20); content.set_margin_bottom(16)
        content.set_margin_start(24); content.set_margin_end(24)
        lbl = Gtk.Label(label="Sınıf değiştirmek için şifreyi girin:")
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
        if pw == CLASS_PASSWORD:
            return True
        err = Gtk.MessageDialog(transient_for=self.win,
            message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK,
            text="Hatalı Şifre")
        err.format_secondary_text("Sınıf değiştirilemedi.")
        err.run(); err.destroy()
        return False

    def _open_class_dialog(self, *_):
        dlg = Gtk.Dialog(title="Sınıf Adı", transient_for=self.win, modal=True)
        dlg.set_default_size(360, 160)
        content = dlg.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(20); content.set_margin_bottom(16)
        content.set_margin_start(24); content.set_margin_end(24)
        lbl = Gtk.Label(label="Bu tahtanın bulunduğu sınıf adını girin:")
        lbl.set_halign(Gtk.Align.START)
        content.pack_start(lbl, False, False, 0)
        entry = Gtk.Entry()
        entry.set_placeholder_text("Örnek: 7-F")
        current = self.cfg.get("class_name", "")
        if current:
            entry.set_text(current)
        content.pack_start(entry, False, False, 0)
        dlg.add_button("İptal", Gtk.ResponseType.CANCEL)
        ok_btn = dlg.add_button("Kaydet", Gtk.ResponseType.OK)
        ok_btn.get_style_context().add_class("blue")
        dlg.set_default_response(Gtk.ResponseType.OK)
        entry.connect("activate", lambda *_: dlg.response(Gtk.ResponseType.OK))
        dlg.show_all()
        resp = dlg.run()
        name = entry.get_text().strip()
        dlg.destroy()
        if resp == Gtk.ResponseType.OK and name:
            self.cfg["class_name"] = name
            save_config(self.cfg)
            self._update_class_label()

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
            self.tray.connect("activate", lambda *_: self.show_dbwin())
            self.tray.connect("popup-menu", self.on_tray_menu)
            self.tray.set_visible(False)
        except Exception:
            self.tray = None

    def on_tray_menu(self, icon, button, t):
        m = Gtk.Menu()
        h = Gtk.MenuItem(label="ÖzBel — Yönetim")
        h.set_sensitive(False); m.append(h)
        m.append(Gtk.SeparatorMenuItem())
        i1 = Gtk.MenuItem(label="Desibel Ölç")
        i1.connect("activate", lambda *_: self.show_dbwin()); m.append(i1)
        i2 = Gtk.MenuItem(label="Bağlantıyı Kes")
        i2.connect("activate", self.disconnect_teacher); m.append(i2)
        m.show_all()
        m.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, t)

    # ── Küçük Desibel penceresi ──
    def build_dbwin(self):
        self.dbwin = Gtk.Window(title="ÖzBel — Desibel")
        self.dbwin.set_default_size(280, 180)
        self.dbwin.set_keep_above(True)
        self.dbwin.set_resizable(False)
        self.dbwin.connect("delete-event", lambda *a: (self.dbwin.hide() or True))
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        b.set_halign(Gtk.Align.CENTER); b.set_valign(Gtk.Align.CENTER)
        b.set_margin_top(14); b.set_margin_bottom(14)
        tl = Gtk.Label(); tl.set_markup('<span foreground="#8b949e">Anlık Ses Seviyesi</span>')
        b.pack_start(tl, False, False, 0)
        self.dbwin_val = Gtk.Label(label="—  dB")
        self.dbwin_val.get_style_context().add_class("db-live")
        b.pack_start(self.dbwin_val, False, False, 0)
        btn = Gtk.Button(label="Bağlantıyı Kes")
        btn.get_style_context().add_class("outline")
        btn.connect("clicked", self.disconnect_teacher)
        b.pack_start(btn, False, False, 0)
        self.dbwin.add(b)

    def show_dbwin(self):
        self.dbwin.show_all()
        self.dbwin.present()

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
        change_btn = Gtk.Button(label="Sınıf Değiştir")
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
        self.restore_main()
        self.pill.set_text("⚠ Bağlantı kesildi — tekrar QR okutun")
        ctx = self.pill.get_style_context()
        ctx.remove_class("pill-ok"); ctx.remove_class("pill")
        ctx.add_class("pill-warn")

    def on_mic_ready(self):
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

    def on_db(self, db):
        self.db_live.set_text(f"{db}  dB")
        self.dbwin_val.set_text(f"{db}  dB")
        if db >= THRESHOLD:
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
