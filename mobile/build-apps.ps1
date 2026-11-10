# Ink 2 Insight - Mobile App Build Script
# Builds both Android APK and iOS IPA using Expo EAS Build

Write-Host "🚀 Ink 2 Insight - Mobile App Builder" -ForegroundColor Cyan
Write-Host "====================================`n" -ForegroundColor Cyan

# Check if EAS CLI is installed
Write-Host "📦 Checking EAS CLI installation..." -ForegroundColor Yellow
$easInstalled = Get-Command eas -ErrorAction SilentlyContinue
if (-not $easInstalled) {
    Write-Host "❌ EAS CLI not found. Installing..." -ForegroundColor Red
    npm install --global eas-cli
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install EAS CLI. Please run manually: npm install --global eas-cli" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ EAS CLI installed successfully" -ForegroundColor Green
} else {
    Write-Host "✅ EAS CLI already installed" -ForegroundColor Green
}

# Check if logged in
Write-Host "`n🔐 Checking Expo account login..." -ForegroundColor Yellow
eas whoami 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Not logged in to Expo account" -ForegroundColor Red
    Write-Host "Please log in first:" -ForegroundColor Yellow
    eas login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Login failed. Please try again." -ForegroundColor Red
        exit 1
    }
}
$username = eas whoami
Write-Host "✅ Logged in as: $username" -ForegroundColor Green

# Install dependencies
Write-Host "`n📦 Installing dependencies..." -ForegroundColor Yellow
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Dependencies installed" -ForegroundColor Green

# Configure project (if needed)
Write-Host "`n⚙️  Configuring project..." -ForegroundColor Yellow
if (-not (Test-Path "eas.json")) {
    eas build:configure
} else {
    Write-Host "✅ Project already configured (eas.json exists)" -ForegroundColor Green
}

# Ask user which platform to build
Write-Host "`n📱 Which platform would you like to build?" -ForegroundColor Cyan
Write-Host "1. Android APK only" -ForegroundColor White
Write-Host "2. iOS IPA only" -ForegroundColor White
Write-Host "3. Both Android APK and iOS IPA" -ForegroundColor White
Write-Host "4. Cancel" -ForegroundColor White
$choice = Read-Host "`nEnter your choice (1-4)"

switch ($choice) {
    "1" {
        Write-Host "`n🤖 Building Android APK..." -ForegroundColor Green
        Write-Host "This will take 5-15 minutes. You can close this window and check progress at:" -ForegroundColor Yellow
        Write-Host "https://expo.dev/accounts/$username/builds`n" -ForegroundColor Cyan
        eas build --platform android --profile preview
    }
    "2" {
        Write-Host "`n🍎 Building iOS IPA..." -ForegroundColor Green
        Write-Host "This will take 10-30 minutes. You can close this window and check progress at:" -ForegroundColor Yellow
        Write-Host "https://expo.dev/accounts/$username/builds`n" -ForegroundColor Cyan
        Write-Host "⚠️  You'll need Apple Developer Program credentials during the build process." -ForegroundColor Yellow
        eas build --platform ios --profile preview
    }
    "3" {
        Write-Host "`n📱 Building both Android APK and iOS IPA..." -ForegroundColor Green
        Write-Host "This will take 15-40 minutes total. You can close this window and check progress at:" -ForegroundColor Yellow
        Write-Host "https://expo.dev/accounts/$username/builds`n" -ForegroundColor Cyan
        Write-Host "⚠️  You'll need Apple Developer Program credentials for iOS build." -ForegroundColor Yellow
        eas build --platform all --profile preview
    }
    "4" {
        Write-Host "`n❌ Build cancelled" -ForegroundColor Red
        exit 0
    }
    default {
        Write-Host "`n❌ Invalid choice. Please run the script again." -ForegroundColor Red
        exit 1
    }
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Build submitted successfully!" -ForegroundColor Green
    Write-Host "`n📊 To check build status, run: eas build:list" -ForegroundColor Cyan
    Write-Host "📥 To download when complete, visit: https://expo.dev/accounts/$username/builds" -ForegroundColor Cyan
} else {
    Write-Host "`n❌ Build failed. Check the error messages above." -ForegroundColor Red
    Write-Host "💡 Common fixes:" -ForegroundColor Yellow
    Write-Host "  - Make sure you're logged in: eas login" -ForegroundColor White
    Write-Host "  - Check your internet connection" -ForegroundColor White
    Write-Host "  - See BUILD_GUIDE.md for troubleshooting" -ForegroundColor White
}

Write-Host "`n🎉 Script complete!" -ForegroundColor Cyan
