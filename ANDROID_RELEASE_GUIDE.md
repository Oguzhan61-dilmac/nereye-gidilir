# Gezi Atlası - Google Play Console & Android TWA (.AAB) Paketleme Rehberi

Bu rehber, **Gezi Atlası (`geziatlasi.com.tr`)** projesinin Google Play Console'a yüklenebilir **`.aab` (Android App Bundle)** ve test amaçlı **`.apk`** formatında nasıl derlendiğini, imzalandığını ve Play Store'a hazırlandığını açıklar.

---

## 1. Mimari ve Hazırlanan Dosyalar

Projemiz, **Trusted Web Activity (TWA)** mimarisiyle web sitemizi yerel bir Android uygulaması kabuğuna dönüştürür.

| Dosya | Konum | Açıklama |
|---|---|---|
| `manifest.json` | Kök Dizin (`/`) | PWA manifesti: isim, renkler (`#5c4033`, `#f4ecdf`), başlangıç URL'si ve 192x192 / 512x512 ikonlar. |
| `sw.js` | Kök Dizin (`/`) | Service Worker: App Shell, statik varlıklar ve JSON veri dosyaları için çevrimdışı önbellekleme (offline cache). |
| `twa-manifest.json` | Kök Dizin (`/`) & `android-twa/` | Bubblewrap yapılandırması: Paket adı `tr.com.geziatlasi.app`, host `geziatlasi.com.tr`, tema ve imza ayarları. |
| `android.keystore` | Kök Dizin & `android-release/` | Google Play Console için sürüm imza anahtarı. |
| `.well-known/assetlinks.json` | `/.well-known/` | Digital Asset Links: TWA'nın tarayıcı adres çubuğu olmadan tam ekran çalışmasını sağlar. |
| `build_aab.sh` | Kök Dizin | Bash/Linux/macOS derleme betiği. |
| `build_aab.ps1` | Kök Dizin | Windows PowerShell tek tıkla derleme betiği. |

---

## 2. Keystore ve İmza Bilgileri

Uygulamanın sürüm paketleri (`.aab` ve `.apk`) halihazırda imzalanmıştır:

- **Keystore Dosyası:** `android.keystore` (veya `android-release/android.keystore`)
- **Key Alias:** `geziatlasi`
- **Keystore Parolası:** `geziatlasi123`
- **Key Parolası:** `geziatlasi123`
- **SHA-256 Sertifika Parmak İzi:**
  ```text
  82:54:EA:D5:16:C7:C5:49:0F:22:67:FB:F3:46:84:D7:78:0D:37:0F:2D:C3:23:8A:59:4B:4B:B0:EB:F2:3B:69
  ```

---

## 3. `.aab` ve `.apk` Dosyalarını Derleme

### Yöntem A: Otomatik Script İle (Önerilen)

**Windows (PowerShell):**
```powershell
.\build_aab.ps1
```

**Linux / macOS / Git Bash:**
```bash
chmod +x build_aab.sh
./build_aab.sh
```

---

### Yöntem B: Bubblewrap CLI İle Manuel Derleme

1. **Bağımlılıkları Kontrol Edin:**
   - Node.js (v18+) ve Java JDK (17+) kurulu olmalıdır.
2. **Projeyi Derleyin:**
   ```bash
   npx @bubblewrap/cli build
   ```
   Bubblewrap, kök dizindeki `twa-manifest.json` dosyasını okuyarak imzalı `.aab` çıktısını oluşturur.

---

### Yöntem C: Gradle Wrapper İle Doğrudan Derleme

```bash
cd android-twa

# AAB (Google Play için)
./gradlew bundleRelease       # Windows: gradlew.bat bundleRelease

# APK (Doğrudan telefonda test için)
./gradlew assembleRelease     # Windows: gradlew.bat assembleRelease
```

Derlenen dosyalar:
- **Play Store AAB:** `android-release/GeziAtlasi-release.aab`
- **Doğrudan Kurulabilir APK:** `android-release/GeziAtlasi-release.apk`

---

## 4. Google Play Console Yükleme Adımları

1. **Google Play Console'a Giriş Yapın:**
   - [Google Play Console](https://play.google.com/console/) paneline gidin.
   - **"Uygulama oluştur"** (Create App) düğmesine tıklayın:
     - **Uygulama Adı:** `Gezi Atlası`
     - **Varsayılan Dil:** `Türkçe - tr-TR`
     - **Uygulama veya Oyun:** `Uygulama`
     - **Ücretsiz / Ücretli:** `Ücretsiz`

2. **Paket Yükleme (Sürüm Oluşturma):**
   - Sol menüden **Üretim (Production)** veya **Dahili Test (Internal Testing)** bölümüne gidin.
   - **"Yeni sürüm oluştur"** seçeneğini seçin.
   - **Uygulama Paketleri (App Bundles)** alanına `android-release/GeziAtlasi-release.aab` dosyasını sürükleyip bırakın.
   - Paket adı otomatik olarak `tr.com.geziatlasi.app` olarak tanınacaktır.

3. **Digital Asset Links Doğrulaması:**
   - Sitenizin `https://geziatlasi.com.tr/.well-known/assetlinks.json` adresinde SHA-256 parmak izi tanımlanmıştır.
   - Google Play Console **"Uygulama Bütünlüğü"** (App Integrity) veya TWA ayarlarında otomatik olarak doğrulanacaktır.
   - Bu sayede uygulama açıldığında Chrome adres çubuğu görünmez, tam ekran yerel bir uygulama deneyimi sunulur.

4. **Mağaza Girişi & Yayınlama:**
   - Kısa açıklama, tam açıklama, ekran görüntüleri ve `assets/icon-512.png` simgesini yükleyin.
   - İnceleme için gönderin!
