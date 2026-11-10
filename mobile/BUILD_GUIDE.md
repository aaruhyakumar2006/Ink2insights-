# 📱 Building Ink 2 Insight Mobile Apps

Complete guide for building Android APK and iOS IPA files using Expo EAS Build.

---

## 🚀 Quick Start (Both Platforms)

```bash
# 1. Install dependencies
cd mobile
npm install

# 2. Install EAS CLI globally
npm install --global eas-cli

# 3. Log in to Expo
eas login

# 4. Configure the project (first time only)
eas build:configure

# 5. Build for both platforms
eas build --platform all --profile preview
```

---

## 📋 Prerequisites

### Required for All Builds
- [x] Expo account (sign up at https://expo.dev/signup)
- [x] Node.js 18+ installed
- [x] npm or yarn installed

### Required for Android APK
- [ ] No additional requirements! ✅

### Required for iOS IPA
- [ ] Apple Developer Program membership ($99/year)
- [ ] Mac computer (for local builds) OR use EAS Build cloud service
- [ ] Apple ID with Developer Program access

---

## 🤖 Android APK Build

### Step 1: Install EAS CLI
```bash
npm install --global eas-cli
```

### Step 2: Log in to Expo
```bash
eas login
```

### Step 3: Configure Project (First Time Only)
```bash
cd mobile
eas build:configure
```

This will:
- Create/update `eas.json` ✅ (already done)
- Link your project to Expo servers
- Generate a project ID

### Step 4: Build Android APK

**For Preview/Testing (Recommended First):**
```bash
eas build --platform android --profile preview
```

**For Production:**
```bash
eas build --platform android --profile production
```

### Step 5: Monitor Build Progress
The CLI will show a URL like:
```
https://expo.dev/accounts/YOUR_ACCOUNT/projects/ink-2-insight/builds/BUILD_ID
```

Open this URL to watch the build in real-time.

### Step 6: Download APK
Once complete (5-15 minutes), you can:
- Download from the Expo dashboard
- Install directly on Android device
- Share the download link with testers

### Android Signing Credentials
EAS will automatically:
1. Generate a new keystore (first time)
2. Store it securely on Expo servers
3. Use it for all future builds

**Manual keystore (optional):**
```bash
eas credentials
```

---

## 🍎 iOS IPA Build

### Prerequisites
- Apple Developer Program membership ($99/year)
- Apple ID credentials ready

### Step 1: Build iOS IPA

**For Testing (Simulator):**
```bash
eas build --platform ios --profile development
```

**For Preview (Physical Device via TestFlight):**
```bash
eas build --platform ios --profile preview
```

**For Production (App Store):**
```bash
eas build --platform ios --profile production
```

### Step 2: Apple Credentials Setup
During first build, EAS will prompt:

```
? What would you like to do?
❯ Let EAS create the credentials for me (recommended)
  Manually handle my credentials
```

**Choose "Let EAS create"** for easiest setup.

You'll need to provide:
- Apple ID email
- Apple ID password
- Two-factor authentication code

EAS will automatically:
1. Create distribution certificate
2. Create provisioning profile
3. Store securely on Expo servers

### Step 3: Download IPA
Once complete (10-30 minutes):
- Download from Expo dashboard
- Install via TestFlight
- Submit to App Store

---

## 🎯 Build Profiles Explained

### `development`
- **Purpose:** Local testing
- **Android:** APK for direct device install
- **iOS:** Simulator build
- **Use when:** Rapid development iteration

### `preview`
- **Purpose:** Internal distribution
- **Android:** APK for testing
- **iOS:** Ad-hoc build for TestFlight
- **Use when:** Team testing, client previews

### `production`
- **Purpose:** App store release
- **Android:** APK/AAB for Play Store
- **iOS:** IPA for App Store
- **Use when:** Public release

---

## 📦 Build Commands Reference

```bash
# Build both platforms at once
eas build --platform all --profile preview

# Build only Android
eas build --platform android --profile preview

# Build only iOS
eas build --platform ios --profile preview

# Build with custom message
eas build --platform android --profile preview --message "Beta v1.0.1"

# List all builds
eas build:list

# View specific build
eas build:view BUILD_ID

# Cancel running build
eas build:cancel
```

---

## 🔧 Configuration Files

### `app.json` Updates
```json
{
  "expo": {
    "name": "Ink 2 Insight",
    "slug": "ink-2-insight",
    "version": "1.0.0",
    "ios": {
      "bundleIdentifier": "com.ink2insight.scanner",
      "buildNumber": "1"
    },
    "android": {
      "package": "com.ink2insight.scanner",
      "versionCode": 1
    }
  }
}
```

### `eas.json` Profiles
```json
{
  "build": {
    "preview": {
      "android": { "buildType": "apk" },
      "ios": { "simulator": false }
    },
    "production": {
      "android": { "buildType": "apk" }
    }
  }
}
```

---

## 📲 Installing the APK on Android

### Method 1: Direct Download
1. Open build page on Android device
2. Tap "Install"
3. Allow "Install from unknown sources" if prompted
4. APK installs automatically

### Method 2: Share Link
1. Copy download link from Expo dashboard
2. Share with testers via email/Slack/etc.
3. Recipients click link and install

### Method 3: ADB Install
```bash
# Download APK to your computer first
adb install path/to/ink-2-insight.apk
```

---

## 📱 Installing IPA on iOS

### Method 1: TestFlight (Recommended)
1. Build with `--profile preview` or `--profile production`
2. Submit to TestFlight:
   ```bash
   eas submit --platform ios
   ```
3. Invite testers in App Store Connect
4. Testers install via TestFlight app

### Method 2: Simulator
1. Build with `--profile development`
2. Download IPA
3. Drag to iOS Simulator

### Method 3: Ad Hoc (Limited Devices)
1. Register device UDIDs in Apple Developer
2. Build with registered devices
3. Install via Apple Configurator or Xcode

---

## ⚡ Quick Tips

### Speed Up Builds
- Use `--profile preview` for testing (faster than production)
- Build Android and iOS separately if only testing one platform
- Use `--auto-submit` to skip build confirmation

### Troubleshooting

**Build fails with "Invalid credentials":**
```bash
eas credentials
# Select platform > Select project > Remove credentials > Try build again
```

**Android APK too large:**
- Add ProGuard/R8 minification in `eas.json`
- Remove unused assets
- Use `aab` format for Play Store (smaller)

**iOS build fails with provisioning error:**
```bash
eas credentials -p ios
# Revoke all credentials and let EAS regenerate
```

**"No space left on device" error:**
- Clear EAS cache: `eas build:cancel` all running builds
- Wait a few minutes and retry

---

## 🎨 Customizing App Icon & Splash

### App Icon
Replace `mobile/assets/icon.png` with:
- Size: 1024x1024 px
- Format: PNG with transparency
- Design: Square icon, no rounded corners

### Splash Screen
Replace `mobile/assets/splash-icon.png` with:
- Size: 1242x2436 px (or larger)
- Format: PNG
- Design: Centered logo on solid background

Then rebuild:
```bash
eas build --platform all --profile preview
```

---

## 🔒 Managing Credentials

### View Credentials
```bash
eas credentials
```

### Backup Credentials
```bash
# Android keystore
eas credentials -p android

# iOS certificates
eas credentials -p ios
```

### Reset Credentials
```bash
eas credentials
# Select platform > Remove all > Rebuild app
```

---

## 📊 Build Status & History

### View All Builds
```bash
eas build:list
```

### View Build Logs
```bash
eas build:view BUILD_ID
```

### Dashboard
Visit: https://expo.dev/accounts/YOUR_ACCOUNT/builds

---

## 🚢 Submitting to Stores

### Google Play Store
```bash
eas submit --platform android
```

Requirements:
- Google Play Developer account ($25 one-time)
- App listing created in Play Console

### Apple App Store
```bash
eas submit --platform ios
```

Requirements:
- Apple Developer Program membership ($99/year)
- App listing created in App Store Connect

---

## 💡 Best Practices

1. **Version Numbers:**
   - Increment `version` in `app.json` for each release
   - Increment `buildNumber` (iOS) and `versionCode` (Android)

2. **Build Messages:**
   - Add `--message` to track build purpose
   - Example: `--message "Fix crash on login screen"`

3. **Testing:**
   - Always test preview builds before production
   - Test on multiple devices (different Android versions, iPhone models)

4. **Credentials:**
   - Let EAS manage credentials (easiest)
   - Backup credentials regularly
   - Never commit credentials to Git

5. **CI/CD:**
   - Automate builds with GitHub Actions
   - See: https://docs.expo.dev/build/building-on-ci/

---

## 🆘 Need Help?

- **Expo Docs:** https://docs.expo.dev/build/setup/
- **Discord:** https://chat.expo.dev/
- **Forums:** https://forums.expo.dev/
- **Status:** https://status.expo.dev/

---

## ✅ Checklist

Before first build:
- [ ] `npm install` completed
- [ ] `eas-cli` installed globally
- [ ] Logged in with `eas login`
- [ ] `eas build:configure` completed
- [ ] App icons added to `assets/`
- [ ] `app.json` configured

For Android APK:
- [ ] No additional requirements

For iOS IPA:
- [ ] Apple Developer Program membership
- [ ] Apple ID credentials ready
- [ ] Two-factor authentication enabled

---

**Ready to build?** Run:

```bash
eas build --platform all --profile preview
```

Your APK and IPA will be ready in 10-20 minutes! 🎉
