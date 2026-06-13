#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ÖzBel — Akıllı Tahta Kulak Sağlığı Sistemi
Native Pardus uygulaması (Python + GTK3)

Mimari (farklı internetler için):
  Telefon (4G) ─► Firebase ◄─ Tahta (FATİH)
  - teacher.html Netlify'da barınır, Firebase'e dB yazar
  - Bu uygulama Firebase'i HTTPS/SSE akışıyla dinler (firewall'dan geçer)
  - QR, Netlify adresini + oturum kodunu gösterir

KURULUM: Aşağıdaki CONFIG bölümünü kendi Firebase/Netlify adreslerinle doldur.
Detay: FIREBASE-KURULUM.md
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf

import os, sys, json, threading, subprocess, tempfile, random, string, time, shutil
import urllib.request, urllib.error

# ═══════════════════════════ CONFIG ═══════════════════════════
FIREBASE_DB = "https://ozbel-eb6af-default-rtdb.europe-west1.firebasedatabase.app"
NETLIFY_URL = "https://glistening-fudge-bca794.netlify.app"
# ══════════════════════════════════════════════════════════════

APP_VERSION = "1.0.9"
UPDATE_JSON = "https://raw.githubusercontent.com/ozguroyunuzmn/ozbel/main/version.json"

SESSION   = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
APP_DIR   = os.path.dirname(os.path.abspath(__file__))
THRESHOLD = 90


# ═══════════════════════════════════════════════════════════════
# Firebase Relay — SSE ile dinler, REST ile yazar
# ═══════════════════════════════════════════════════════════════
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
        self.clear()  # eski veriyi temizle
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
                time.sleep(2)  # bağlantı koptu → yeniden dene

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


# ═══════════════════════════════════════════════════════════════
def make_qr(data, size):
    path = os.path.join(tempfile.gettempdir(), f"ozbel_qr_{abs(hash(data))}.png")
    try:
        subprocess.run(["qrencode", "-o", path, "-s", str(size), "-m", "2", "-l", "M", data],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return path
    except Exception:
        return None


CSS = b"""
window, .screen-bg { background-color:#0d1117; }

/* Tipografi */
.logo-text  { color:#e6edf3; font-size:42px; font-weight:900; letter-spacing:-1px; }
.logo-blue  { color:#1a73e8; font-size:42px; font-weight:900; letter-spacing:-1px; }
.subtitle   { color:#8b949e; font-size:13px; }
.section-title { color:#e6edf3; font-size:18px; font-weight:700; }
.code       { color:#1a73e8; font-size:30px; font-weight:900; letter-spacing:4px; }
.qrlabel    { color:#8b949e; font-size:11px; }
.version    { color:#30363d; font-size:11px; }

/* Durum hapı */
.pill       { color:#7090d0; font-size:13px; font-weight:600;
              background:#0d1629; border:1px solid #1e2d4a;
              border-radius:999px; padding:6px 16px; }
.pill-ok    { color:#1db954; font-size:13px; font-weight:600;
              background:#0d1f0d; border:1px solid #1a3a1a;
              border-radius:999px; padding:6px 16px; }

/* Kart */
.card { background-color:#161b22; border:1px solid #21262d;
        border-radius:16px; padding:20px; }
.card-title { color:#e6edf3; font-size:15px; font-weight:700; }
.step-num   { color:#1a73e8; font-size:11px; font-weight:800;
              background:#0d1f3a; border:1px solid #1a3a6a;
              border-radius:999px; padding:2px 8px; }
.step-txt   { color:#8b949e; font-size:12px; }
.step-txt-b { color:#e6edf3; font-size:12px; font-weight:700; }

/* dB göstergesi */
.db-huge  { color:#e6edf3; font-size:72px; font-weight:900; }
.db-unit  { color:#8b949e; font-size:16px; }
.db-live  { color:#e6edf3; font-size:38px; font-weight:900; }
.db-ok    { color:#1db954; font-size:38px; font-weight:900; }
.db-warn  { color:#e53935; font-size:38px; font-weight:900; }
.db-mid   { color:#ff8f00; font-size:38px; font-weight:900; }

/* Hazır ekranı */
.ready-label { color:#1db954; font-size:20px; font-weight:700;
               background:#0d1f0d; border:1px solid #1a3a1a;
               border-radius:999px; padding:8px 24px; }
.ready-sub   { color:#8b949e; font-size:14px; }

/* Butonlar */
button.outline { background:transparent; color:#8b949e;
                 border:1px solid #30363d; border-radius:10px; padding:8px 20px; }
button.outline:hover { color:#e6edf3; border-color:#8b949e; }
button.green  { background:#1db954; color:#00140a; border-radius:12px;
                padding:12px 32px; font-weight:700; border:none; font-size:14px; }
button.red    { background:#e53935; color:#fff; border-radius:12px;
                padding:12px 32px; font-weight:700; border:none; font-size:14px; }
button.blue   { background:#1a73e8; color:#fff; border-radius:12px;
                padding:10px 24px; font-weight:700; border:none; font-size:13px; }

/* Uyarı ekranı */
.alert-win   { background-color:#0d0000; }
.alert-title { color:#ff1744; font-size:56px; font-weight:900; }
.alert-db    { color:#ff5252; font-size:110px; font-weight:900; }
.alert-unit  { color:#c08080; font-size:28px; font-weight:600; }
.alert-sub   { color:#a06060; font-size:20px; }
"""


class OzBelApp:
    def __init__(self):
        provider = Gtk.CssProvider(); provider.load_from_data(CSS)
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

        self.alert_open  = False
        self.alert_src   = None
        self.alert_count = 0
        self.alert_max_db = 0

        self.relay = FirebaseRelay(self)
        self.relay.start()

    # ── Tepsi (e-Kilit gibi) menüsü ──
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

        self.overlay.add_overlay(box)
        self.overlay.set_overlay_pass_through(box, True)

        # Sol alt — Güncelleme Denetle butonu
        upd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        upd_box.set_halign(Gtk.Align.START)
        upd_box.set_valign(Gtk.Align.END)
        upd_box.set_margin_start(18)
        upd_box.set_margin_bottom(18)
        upd_btn = Gtk.Button(label="🔄  Güncelleme Denetle")
        upd_btn.get_style_context().add_class("outline")
        upd_btn.connect("clicked", self.check_update)
        upd_box.pack_start(upd_btn, False, False, 0)
        self.overlay.add_overlay(upd_box)
        self.overlay.set_overlay_pass_through(upd_box, False)

    def check_update(self, *_):
        threading.Thread(target=self._do_check_update, daemon=True).start()

    def _do_check_update(self):
        try:
            resp = urllib.request.urlopen(UPDATE_JSON, timeout=10).read()
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
            dlg = Gtk.MessageDialog(transient_for=self.win,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text=f"Güncelleme Mevcut — v{latest}")
            dlg.format_secondary_text(
                f"Mevcut sürüm: {APP_VERSION}  →  Yeni sürüm: {latest}\n\n"
                f"Değişiklikler:\n{log_text}\n\n"
                f"Güncelleme indirilip uygulama yeniden başlatılacak. Devam edilsin mi?")
            resp = dlg.run(); dlg.destroy()
            if resp == Gtk.ResponseType.YES:
                threading.Thread(target=self._do_install_update,
                                 args=(py_url,), daemon=True).start()

    def _do_install_update(self, py_url):
        GLib.idle_add(self._show_updating)
        try:
            # Kullanıcı klasörüne indir — sudo gerekmez
            user_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "ozbel")
            os.makedirs(user_dir, exist_ok=True)
            dest = os.path.join(user_dir, "ozbel.py")
            urllib.request.urlretrieve(py_url, dest)
            os.chmod(dest, 0o755)
            self._update_dest = dest
        except Exception as e:
            GLib.idle_add(self._update_dialog, "error", f"İndirme hatası: {e}")
            return

        # Uygulamayı yeniden başlat
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
        i2 = Gtk.MenuItem(label="Bağlantıyı Kopart")
        i2.connect("activate", self.disconnect_teacher); m.append(i2)
        m.show_all()
        m.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, t)

    # ── Küçük "Desibel" penceresi ──
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
        btn = Gtk.Button(label="Bağlantıyı Kopart")
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

        # İçerik — yatayda ortalanmış, max genişlik
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_halign(Gtk.Align.CENTER); box.set_valign(Gtk.Align.CENTER)
        box.set_margin_top(32); box.set_margin_bottom(32)
        box.set_margin_start(40); box.set_margin_end(40)

        # Logo satırı
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

        # Ana yatay alan: sol kart + sağ QR
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=32)
        hbox.set_halign(Gtk.Align.CENTER)

        # Sol — adımlar kartı
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

        # Sağ — QR + kod
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

        # Durum hapı
        self.pill = Gtk.Label(label="●  Öğretmen bekleniyor…")
        self.pill.get_style_context().add_class("pill")
        self.pill.set_halign(Gtk.Align.CENTER)
        box.pack_start(self.pill, False, False, 0)

        # Kapat butonu
        nob = Gtk.Button(label="Kapat")
        nob.get_style_context().add_class("outline")
        nob.set_halign(Gtk.Align.CENTER)
        nob.connect("clicked", self.quit)
        box.pack_start(nob, False, False, 0)

        # Sürüm
        ver = Gtk.Label(label=f"v{APP_VERSION}")
        ver.get_style_context().add_class("version")
        ver.set_halign(Gtk.Align.CENTER)
        box.pack_start(ver, False, False, 0)

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

        btn = Gtk.Button(label="Bağlantıyı Kes")
        btn.get_style_context().add_class("red")
        btn.set_halign(Gtk.Align.CENTER)
        btn.connect("clicked", self.disconnect_teacher)
        box.pack_start(btn, False, False, 0)

        self.stack.add_named(box, "ready")

    # ── Uyarı ekranı ──
    def build_alert(self):
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        b.get_style_context().add_class("alert-win")
        b.set_halign(Gtk.Align.CENTER); b.set_valign(Gtk.Align.CENTER)

        ico = Gtk.Label(); ico.set_markup('<span size="120000">🔇</span>')
        b.pack_start(ico, False, False, 0)

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
        unit.set_margin_bottom(18)
        db_row.pack_start(self.alert_db, False, False, 0)
        db_row.pack_start(unit, False, False, 0)
        b.pack_start(db_row, False, False, 0)

        sub = Gtk.Label(label="Kulak sağlığı için ses seviyesi 90 dB'nin altında olmalıdır")
        sub.get_style_context().add_class("alert-sub")
        sub.set_halign(Gtk.Align.CENTER)
        b.pack_start(sub, False, False, 0)

        self.stack.add_named(b, "alert")

    def gen_qr(self):
        p = make_qr(f"{NETLIFY_URL}/?s={SESSION}", 9)
        if p and os.path.exists(p):
            self.qr_img.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(p, 260, 260, True))

    # ── Olaylar ──
    def on_teacher_connected(self):
        self.pill.set_text("📱  Telefon bağlandı — mikrofon bekleniyor…")
        self.pill.get_style_context().add_class("pill-ok")

    def on_teacher_gone(self):
        self.restore_main()
        self.pill.set_text("●  Bağlantı kesildi — bekleniyor…")
        self.hide_alert()

    def on_mic_ready(self):
        # e-Kilit gibi: pencereyi gizle, tepsiye in, küçük desibel penceresini göster
        self.stack.set_visible_child_name("ready")
        self.win.hide()
        if self.tray:
            self.tray.set_visible(True)
        self.show_dbwin()

    def on_db(self, db):
        self.db_live.set_text(f"{db}  dB")
        self.dbwin_val.set_text(f"{db}  dB")
        if db >= THRESHOLD:
            self.show_alert(db)

    def on_lesson_end(self):
        self.hide_alert()
        self.show_lesson_summary()
        self.restore_main()
        self.pill.set_text("●  Öğretmen bekleniyor…")
        self.alert_count  = 0
        self.alert_max_db = 0

    def show_lesson_summary(self):
        if self.alert_count == 0:
            msg  = "Bu ders boyunca hiç gürültü uyarısı verilmedi. 👏"
            sec  = "Sınıf tüm ders boyunca 90 dB sınırının altında kaldı."
        else:
            msg  = f"Ders Özeti — {self.alert_count} kez uyarı verildi"
            sec  = (
                f"🔔  Uyarı sayısı   : {self.alert_count} kez\n"
                f"📈  En yüksek ses  : {self.alert_max_db} dB\n\n"
                f"Kulak sağlığı için ses seviyesinin 90 dB altında tutulması önerilir."
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
        # Tepsiden ana pencereye geri dön
        self.hide_dbwin()
        if self.tray:
            self.tray.set_visible(False)
        self.stack.set_visible_child_name("setup")
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
            self.stack.set_visible_child_name("alert")
            self.win.show_all()
            self.win.fullscreen()
            self.win.present()
        if self.alert_src:
            GLib.source_remove(self.alert_src)
        self.alert_src = GLib.timeout_add_seconds(6, self._auto_hide)

    def _auto_hide(self):
        self.hide_alert(); self.alert_src = None; return False

    def hide_alert(self):
        if self.alert_open:
            self.alert_open = False
            self.win.unfullscreen()
            self.stack.set_visible_child_name("ready")
            self.win.hide()

    def disconnect_teacher(self, *_):
        self.relay.put("control", "disconnect")
        self.restore_main()
        self.pill.set_text("●  Öğretmen bekleniyor…")
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
        # Yapılandırma yapılmamış — uyar
        dlg = Gtk.MessageDialog(
            message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK,
            text="ÖzBel yapılandırılmamış")
        dlg.format_secondary_text(
            "ozbel.py içindeki FIREBASE_DB ve NETLIFY_URL adreslerini doldurun.\n"
            "Detay: FIREBASE-KURULUM.md")
        dlg.run(); dlg.destroy()
    OzBelApp().run()
