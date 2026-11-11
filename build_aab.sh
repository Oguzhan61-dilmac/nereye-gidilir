#!/usr/bin/env bash
# =============================================================================
# GEZİ ATLASI - ANDROID APP BUNDLE (.AAB) BUILD SCRIPT
# Google Play Console İçin Bubblewrap / TWA .aab Derleyici
# =============================================================================

set -e

echo "=========================================================="
echo "🌍 Gezi Atlası (geziatlasi.com.tr) - Android AAB Derleyici"
echo "=========================================================="

# 1. Node.js & Java Ortam Kontrolleri
echo ""
echo "[1/4] Ortam kontrolleri yapılıyor..."

if ! command -v node &> /dev/null; then
    echo "❌ HATA: Node.js kurulu değil. Lütfen https://nodejs.org adresinden yükleyin."
    exit 1
fi
echo "  ✓ Node.js: $(node -v)"

if ! command -v java &> /dev/null; then
    echo "❌ HATA: Java (JDK 17+) kurulu değil. Lütfen OpenJDK 17 veya Android Studio kurun."
    exit 1
fi
echo "  ✓ Java JDK: $(java -version 2>&1 | head -n 1)"

# 2. Bubblewrap CLI Kontrolü
echo ""
echo "[2/4] Bubblewrap CLI hazırlanıyor..."
BUBBLEWRAP="npx --yes @bubblewrap/cli"

# 3. Manifest ve TWA Kontrolü
echo ""
echo "[3/4] TWA yapılandırması kontrol ediliyor..."
if [ ! -f "twa-manifest.json" ]; then
    echo "  -> twa-manifest.json bulunamadı. Web Manifest üzerinden ilklendiriliyor..."
    $BUBBLEWRAP init --manifest=https://geziatlasi.com.tr/manifest.json
else
    echo "  ✓ twa-manifest.json bulundu (Paket: tr.com.geziatlasi.app)"
fi

# 4. Derleme Adımı (.aab Üretimi)
echo ""
echo "[4/4] Android App Bundle (.aab) derleniyor..."

if [ -d "android-twa" ]; then
    cd android-twa
    if [ -f "./gradlew" ]; then
        chmod +x ./gradlew
        ./gradlew bundleRelease
    else
        gradlew.bat bundleRelease
    fi
    cd ..

    mkdir -p android-release
    cp android-twa/app/build/outputs/bundle/release/app-release.aab android-release/GeziAtlasi-release.aab

    echo ""
    echo "=========================================================="
    echo "✅ BAŞARILI! .aab paketi Google Play Console için hazırlandı!"
    echo "📦 Dosya Yolu: android-release/GeziAtlasi-release.aab"
    echo "=========================================================="
else
    $BUBBLEWRAP build
fi
