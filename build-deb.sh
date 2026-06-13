#!/bin/bash
# ÖzBel .deb paketleyici (native Python/GTK uygulaması)
# Derleme gerektirmez — Linux'ta dpkg-deb yeterli.
# Çıktı: ozbel_1.0.0_all.deb  → Pardus'ta çift tıkla kur
set -e

VERSION="1.0.0"
PKG="ozbel_${VERSION}_all"

echo "▶ .deb yapısı oluşturuluyor..."
rm -rf "$PKG"

install -d "$PKG/opt/ozbel"
install -d "$PKG/usr/bin"
install -d "$PKG/usr/share/applications"
install -d "$PKG/etc/xdg/autostart"
install -d "$PKG/DEBIAN"

# Uygulama dosyası (teacher.html artık Netlify'da, pakete gerek yok)
install -m 644 ozbel.py "$PKG/opt/ozbel/"

# /usr/bin/ozbel başlatıcı
cat > "$PKG/usr/bin/ozbel" << 'BIN'
#!/bin/bash
# Güncelleme varsa kullanıcı klasöründeki yeni sürümü çalıştır
USER_PY="$HOME/.local/share/ozbel/ozbel.py"
if [ -f "$USER_PY" ]; then
  exec python3 "$USER_PY" "$@"
else
  exec python3 /opt/ozbel/ozbel.py "$@"
fi
BIN
chmod 755 "$PKG/usr/bin/ozbel"

# Uygulama menüsü girişi (Pardus menüsünde/aramada "ÖzBel")
cat > "$PKG/usr/share/applications/ozbel.desktop" << 'MENU'
[Desktop Entry]
Type=Application
Name=ÖzBel
GenericName=Kulak Sağlığı Sistemi
Comment=Akıllı Tahta Kulak Sağlığı Koruma Sistemi
Exec=ozbel
Icon=audio-volume-high
Terminal=false
Categories=Education;Utility;
Keywords=ozbel;ses;desibel;kulak;saglik;mikrofon;gurultu;
StartupNotify=true
MENU

# Otomatik başlatma (her açılışta)
cat > "$PKG/etc/xdg/autostart/ozbel.desktop" << 'AUTO'
[Desktop Entry]
Type=Application
Name=ÖzBel
Comment=Kulak Sağlığı Koruma Sistemi
Exec=ozbel
Icon=audio-volume-high
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
AUTO

# DEBIAN/control
cat > "$PKG/DEBIAN/control" << CTRL
Package: ozbel
Version: $VERSION
Section: education
Priority: optional
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-3.0, qrencode
Maintainer: ÖzBel
Description: Akıllı Tahta Kulak Sağlığı Koruma Sistemi
 Sınıf gürültüsü 90 dB'i aşınca tahtada native uyarı gösterir.
 Öğretmenin telefon mikrofonu WebSocket ile tahtaya bağlanır.
 Python + GTK3 ile yazılmış yerli uygulama.
CTRL

# Kurulum sonrası: eski kullanıcı kopyalarını temizle
cat > "$PKG/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
# Eski ~/.local/share/ozbel/ozbel.py varsa sil (launcher artık /opt/ozbel/ kullanır)
for userdir in /home/*; do
  rm -f "$userdir/.local/share/ozbel/ozbel.py"
done
exit 0
POSTINST
chmod 755 "$PKG/DEBIAN/postinst"

# Kaldırılırken çalışanı durdur
cat > "$PKG/DEBIAN/prerm" << 'PRERM'
#!/bin/bash
pkill -f /opt/ozbel/ozbel.py 2>/dev/null || true
pkill -f ozbel.py 2>/dev/null || true
exit 0
PRERM
chmod 755 "$PKG/DEBIAN/prerm"

echo "▶ Paketleniyor..."
dpkg-deb --build --root-owner-group "$PKG"
rm -rf "$PKG"

echo ""
echo "✅  Hazır: ${PKG}.deb"
echo "    → Pardus'a kopyala → Çift tıkla → Yükle → Bitti!"
echo "    → Menüde 'ÖzBel' diye aratıp açabilirsin, her açılışta otomatik başlar."
