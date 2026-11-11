# =============================================================================
# GEZİ ATLASI - ANDROID APP BUNDLE (.AAB) BUILD SCRIPT (POWERSHELL)
# Google Play Console İçin Bubblewrap / TWA .aab Derleyici
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "🌍 Gezi Atlası (geziatlasi.com.tr) - Android AAB Derleyici" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Ortam Kontrolleri
Write-Host "`n[1/4] Ortam kontrolleri yapılıyor..." -ForegroundColor Green

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js kurulu değil. Lütfen https://nodejs.org adresinden yükleyin."
    exit 1
}
$nodeVer = node -v
Write-Host "  ✓ Node.js: $nodeVer" -ForegroundColor White

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    Write-Error "Java (JDK 17+) kurulu değil. Lütfen OpenJDK 17 veya Android Studio kurun."
    exit 1
}
$javaVer = (java -version 2>&1 | Select-Object -First 1)
Write-Host "  ✓ Java JDK: $javaVer" -ForegroundColor White

# 2. Bubblewrap CLI Kontrolü
Write-Host "`n[2/4] Bubblewrap CLI hazırlanıyor..." -ForegroundColor Green

# 3. TWA Yapılandırması
Write-Host "`n[3/4] TWA yapılandırması kontrol ediliyor..." -ForegroundColor Green
if (-not (Test-Path "twa-manifest.json")) {
    Write-Host "  -> twa-manifest.json bulunamadı. Web Manifest üzerinden ilklendiriliyor..."
    npx --yes @bubblewrap/cli init --manifest=https://geziatlasi.com.tr/manifest.json
} else {
    Write-Host "  ✓ twa-manifest.json hazır (Paket: tr.com.geziatlasi.app)" -ForegroundColor White
}

# 4. Derleme Adımı (.aab Üretimi)
Write-Host "`n[4/4] Android App Bundle (.aab) derleniyor..." -ForegroundColor Green

if (Test-Path "android-twa") {
    Push-Location "android-twa"
    try {
        cmd.exe /c "gradlew.bat bundleRelease"
    } finally {
        Pop-Location
    }

    if (-not (Test-Path "android-release")) {
        New-Item -ItemType Directory -Path "android-release" | Out-Null
    }

    $builtAab = "android-twa\app\build\outputs\bundle\release\app-release.aab"
    $targetAab = "android-release\GeziAtlasi-release.aab"
    Copy-Item $builtAab $targetAab -Force

    Write-Host "`n==========================================================" -ForegroundColor Cyan
    Write-Host "✅ BAŞARILI! .aab paketi Google Play Console için hazırlandı!" -ForegroundColor Green
    Write-Host "📦 Dosya Yolu: $targetAab" -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Cyan
} else {
    npx --yes @bubblewrap/cli build
}
