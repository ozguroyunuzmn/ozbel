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

APP_VERSION = "1.0.1"
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
window { background-color: #0d1117; }
.title    { color:#e6edf3; font-size:34px; font-weight:800; }
.subtitle { color:#8b949e; font-size:14px; }
.card-title { color:#e6edf3; font-size:22px; font-weight:700; }
.qrlabel  { color:#8b949e; font-size:12px; }
.code     { color:#1a73e8; font-size:26px; font-weight:900; }
.pill     { color:#7090d0; font-size:14px; font-weight:600; }
.pill-ok  { color:#1db954; font-size:14px; font-weight:600; }
.ready-title { color:#1db954; font-size:52px; font-weight:900; }
.ready-sub   { color:#8b949e; font-size:18px; }
.db-live     { color:#e6edf3; font-size:40px; font-weight:900; }
.card { background-color:#161b22; border:1px solid #30363d; border-radius:16px; padding:24px; }
button.outline { background:transparent; color:#8b949e; border:1px solid #30363d; border-radius:10px; padding:8px 20px; }
button.green   { background:#1db954; color:#00140a; border-radius:12px; padding:12px 30px; font-weight:700; border:none; }
.alert-win   { background-color:#1a0000; }
.alert-title { color:#e53935; font-size:44px; font-weight:900; }
.alert-db    { color:#e53935; font-size:80px; font-weight:900; }
.alert-sub   { color:#c08080; font-size:22px; }
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

        self.alert_open = False
        self.alert_src  = None

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
            # Yeni ozbel.py'yi indir
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".py")
            urllib.request.urlretrieve(py_url, tmp.name)
            tmp.close()

            # Mevcut dosyayı yedekle ve değiştir
            current = os.path.abspath(__file__)
            shutil.copy2(current, current + ".bak")
            shutil.move(tmp.name, current)
            os.chmod(current, 0o755)
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
        try: self.relay.running = False
        except Exception: pass
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])

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
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        box.set_halign(Gtk.Align.CENTER); box.set_valign(Gtk.Align.CENTER)

        t = Gtk.Label(label="🔊  ÖzBel"); t.get_style_context().add_class("title")
        box.pack_start(t, False, False, 0)
        s = Gtk.Label(label="Akıllı Tahta Kulak Sağlığı Koruma Sistemi")
        s.get_style_context().add_class("subtitle"); box.pack_start(s, False, False, 0)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.get_style_context().add_class("card")
        ct = Gtk.Label(label="Kulak Sağlığı Sistemini Kurmak İster misiniz?")
        ct.get_style_context().add_class("card-title"); card.pack_start(ct, False, False, 0)
        for txt in [
            "Aşağıdaki QR'ı telefon kameranızla okutun",
            "Açılan sayfada mikrofon izni verin",
            "Sistem hazır — sınıf 90 dB'i aşınca uyarı çıkar",
        ]:
            r = Gtk.Label(); r.set_markup(f'<span foreground="#8b949e">•  {txt}</span>')
            r.set_halign(Gtk.Align.START); card.pack_start(r, False, False, 0)
        box.pack_start(card, False, False, 0)

        self.qr_img = Gtk.Image(); box.pack_start(self.qr_img, False, False, 0)
        self.code_lbl = Gtk.Label(label=f"Kod: {SESSION}")
        self.code_lbl.get_style_context().add_class("code")
        box.pack_start(self.code_lbl, False, False, 0)
        ql = Gtk.Label(label="↑ Telefon kameranızla bu kareyi okutun")
        ql.get_style_context().add_class("qrlabel"); box.pack_start(ql, False, False, 0)

        self.pill = Gtk.Label(label="●  Öğretmen bekleniyor…")
        self.pill.get_style_context().add_class("pill")
        box.pack_start(self.pill, False, False, 0)

        nob = Gtk.Button(label="Gerek Yok — Kapat")
        nob.get_style_context().add_class("outline"); nob.set_halign(Gtk.Align.CENTER)
        nob.connect("clicked", self.quit); box.pack_start(nob, False, False, 0)

        self.stack.add_named(box, "setup")

    # ── Hazır ekranı ──
    def build_ready(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.set_halign(Gtk.Align.CENTER); box.set_valign(Gtk.Align.CENTER)
        ico = Gtk.Label(); ico.set_markup('<span size="70000">✅</span>')
        box.pack_start(ico, False, False, 0)
        rt = Gtk.Label(label="Hazırsınız!"); rt.get_style_context().add_class("ready-title")
        box.pack_start(rt, False, False, 0)
        rs = Gtk.Label(label="Öğretmenin telefon mikrofonu aktif — sistem çalışıyor")
        rs.get_style_context().add_class("ready-sub"); box.pack_start(rs, False, False, 0)
        self.db_live = Gtk.Label(label="—  dB"); self.db_live.get_style_context().add_class("db-live")
        box.pack_start(self.db_live, False, False, 0)
        btn = Gtk.Button(label="Bağlantıyı Kes"); btn.get_style_context().add_class("green")
        btn.set_halign(Gtk.Align.CENTER); btn.connect("clicked", self.disconnect_teacher)
        box.pack_start(btn, False, False, 0)
        self.stack.add_named(box, "ready")

    # ── Uyarı penceresi ──
    def build_alert(self):
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        b.get_style_context().add_class("alert-win")
        b.set_halign(Gtk.Align.CENTER); b.set_valign(Gtk.Align.CENTER)
        e = Gtk.Label(); e.set_markup('<span size="90000">🔇</span>'); b.pack_start(e, False, False, 0)
        ti = Gtk.Label(label="Lütfen Sessiz Olun!"); ti.get_style_context().add_class("alert-title")
        b.pack_start(ti, False, False, 0)
        self.alert_db = Gtk.Label(label="—  dB"); self.alert_db.get_style_context().add_class("alert-db")
        b.pack_start(self.alert_db, False, False, 0)
        sub = Gtk.Label(label="Kulak sağlığınız için ses 90 dB'nin altında olmalı")
        sub.get_style_context().add_class("alert-sub"); b.pack_start(sub, False, False, 0)
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
        self.restore_main()
        self.pill.set_text("●  Öğretmen bekleniyor…")
        self.hide_alert()

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
        self.alert_db.set_text(f"{db}  dB")
        if not self.alert_open:
            self.alert_open = True
            self.stack.set_visible_child_name("alert")
        if self.alert_src:
            GLib.source_remove(self.alert_src)
        self.alert_src = GLib.timeout_add_seconds(6, self._auto_hide)

    def _auto_hide(self):
        self.hide_alert(); self.alert_src = None; return False

    def hide_alert(self):
        if self.alert_open:
            self.alert_open = False
            # Önceki ekrana geri dön
            if self.win.get_visible():
                self.stack.set_visible_child_name("ready")
            else:
                self.stack.set_visible_child_name("setup")

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
