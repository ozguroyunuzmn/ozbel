# ÖzBel Android — Kurulum & Yayın

Native Android öğretmen uygulaması (Kotlin + Jetpack Compose).
Site ile aynı akış: **Karekod Okut → Mikrofon İzni → Ölçüm**, ama:
- Gerçek uygulama, **arka planda/kilit ekranında** ölçer (foreground service)
- **Hassasiyet** seçeneği: Çok Duyarlı / Duyarlı / Orta / Düşük
- Firebase'e REST ile yazar → **tahta (ozbel.py) hiç değişmez**

## Gereken
- **Android Studio** (Linux/Pardus'ta da çalışır) — son sürüm
- Google Play Console hesabı (yayın için)

## 1) Projeyi aç
1. Android Studio → **Open** → bu `android/` klasörünü seç
2. İlk açılışta Gradle'ı kendi indirir/senkronlar (birkaç dakika, internet ister)
3. SDK eksikse "Install missing SDK" çıkar → kabul et

## 2) Firebase adresi
`app/src/main/java/com/ozbel/teacher/FirebaseRest.kt` içindeki `DB` zaten dolu
(`ozbel-eb6af...`). Değiştirmen gerekmiyor.

## 3) Telefonda dene
1. Telefonu USB ile bağla (Geliştirici modu + USB hata ayıklama açık)
2. Üstten **Run ▶** → uygulama telefona kurulur
3. Tahtada `ozbel.py` çalışsın → QR'ı uygulamayla okut → mikrofon izni → ölç
4. Telefonu kilitle → ölçüm devam etmeli (bildirimde "ÖzBel çalışıyor")

## 4) Play Store'a yükleme (özet)
1. **İmzalı paket:** Build → **Generate Signed Bundle / APK → Android App Bundle (.aab)**
   - Yeni bir **keystore** oluştur, şifresini KAYBETME (güncellemeler için şart)
2. Play Console → **Create app** → uygulama bilgileri
3. **Production → Create release** → `.aab` yükle
4. Zorunlu formlar: içerik derecelendirme, **gizlilik politikası URL'si** (mikrofon kullanıyor),
   **Data safety** (veri: sadece anlık ses seviyesi sayısı; ses kaydı YOK diye belirt),
   hedef kitle, ekran görüntüleri
5. İnceleme notu: "Sınıf gürültüsünü ölçen okul aracı; arka plan mikrofonu sürekli ölçüm için gerekli."

## Hassasiyet nasıl çalışır
Ölçüm ekranında **5 seviye** vardır (site ile aynı), ölçerken canlı değişir:
| Seviye | Offset |
|--------|--------|
| 🔊 Çok Duyarlı | 105 |
| 🔉 Duyarlı | 100 |
| ⚖️ Orta | 97 |
| 🔈 Az Duyarlı | 92 |
| 🔇 Duyarsız | 87 |

Üstte **cihaz kutusu**: telefon modelini (Build.MODEL) gösterir ve markaya/forma göre
önerilen seviyeyi işaretler ("Öneriyi Uygula"). Öneri kuralı `DeviceRec.kt` içinde —
Xiaomi/Redmi/POCO/Huawei → Duyarlı(100), tablet → Duyarlı(100), Samsung/Pixel/diğer → Orta(97).
İstediğin modeli oraya ekleyip ince ayar yapabiliriz.

Tahtadaki 90 dB eşiği sabit; offset düştükçe aynı ses daha düşük dB gider → daha az öter.

## Mimari
```
Telefon (uygulama)                        Tahta (Pardus)
──────────────────                        ──────────────
QR tara → kod
AudioRecord → dB (+hassasiyet)
foreground service (arka plan)   ─REST─►  Firebase ◄─SSE─ ozbel.py
PUT /sessions/<kod>/{db,teacher,mic}                      90 dB → MP3 uyarı
GET /sessions/<kod>/control (1sn poll)
"Ders Bitti" → lesson=end
```

## Not
- Bu bir **başlangıç iskeleti**. Android Studio'da açınca Gradle sürüm/SDK uyarısı çıkarsa
  birlikte çözeriz — derleme hatalarını bana yaz.
- İleride telefonda **yapay zeka (gürültü/konuşma ayrımı)** de eklenebilir (TFLite YAMNet);
  şimdilik hassasiyet seviyeleriyle çözülüyor.
```
