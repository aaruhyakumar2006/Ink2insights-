# 📱 Ink 2 Insight - Mobile App

React Native mobile application for clinical health camp documentation and form scanning.

## 🚀 Quick Start

### Build APK & IPA (Production Apps)

**Fastest Way:**
```bash
cd mobile
.\build-apps.ps1
```

**Manual Way:**
```bash
npm install --global eas-cli
eas login
npm run build:preview
```

📖 **Full Instructions:** See [QUICK_START.md](QUICK_START.md)

---

## 📦 What's Included

- ✅ WebView wrapper for Ink 2 Insight web app
- ✅ iOS safe area handling (notches, home indicator)
- ✅ Android edge-to-edge display
- ✅ Configurable backend server URL
- ✅ Full-screen brand intro support
- ✅ Camera and photo library permissions
- ✅ Connection status monitoring

---

## 🔨 Development

### Run on Simulator/Emulator
```bash
npm start          # Start Expo Dev Server
npm run android    # Launch Android Emulator
npm run ios        # Launch iOS Simulator
```

### Build for Production
```bash
npm run build:preview       # Both platforms (testing)
npm run build:android       # Android APK only
npm run build:ios          # iOS IPA only
npm run build:production   # Both platforms (stores)
```

### Submit to Stores
```bash
npm run submit:android     # Google Play Store
npm run submit:ios        # Apple App Store
```

### Check Build Status
```bash
npm run build:list        # List all builds
```

---

## 📋 Configuration

### App Configuration
Edit `app.json`:
- `version`: App version number
- `ios.buildNumber`: iOS build number
- `android.versionCode`: Android version code
- `ios.bundleIdentifier`: iOS bundle ID
- `android.package`: Android package name

### Build Configuration
Edit `eas.json`:
- `development`: Local testing builds
- `preview`: Internal distribution builds
- `production`: App store builds

### Backend Server
Edit `App.js`:
```javascript
const DEFAULT_SERVER_URL = 'http://192.168.1.8:5001';
```

---

## 🎨 Customization

### App Icon
Replace: `assets/icon.png` (1024x1024 px)

### Splash Screen
Replace: `assets/splash-icon.png` (1242x2436 px)

### Android Adaptive Icon
Replace: 
- `assets/android-icon-foreground.png`
- `assets/android-icon-background.png`

---

## 📱 Platform Requirements

### Android
- **Minimum SDK:** 21 (Android 5.0)
- **Target SDK:** 34 (Android 14)
- **Permissions:** Camera, Photo Library, Internet

### iOS
- **Minimum Version:** iOS 13.0
- **Supports:** iPhone, iPad
- **Permissions:** Camera, Photo Library

---

## 🔐 Signing & Credentials

### Android
EAS Build automatically:
- Generates keystore (first build)
- Signs APK with keystore
- Stores keystore securely

### iOS
Requires:
- Apple Developer Program ($99/year)
- Apple ID with Two-Factor Authentication

EAS Build automatically:
- Creates distribution certificate
- Creates provisioning profile
- Signs IPA

---

## 📂 Project Structure

```
mobile/
├── App.js                  # Main app component
├── app.json                # Expo configuration
├── eas.json                # EAS Build configuration
├── package.json            # Dependencies & scripts
├── assets/                 # App icons & images
├── build-apps.ps1          # Build automation script
├── BUILD_GUIDE.md          # Detailed build instructions
├── QUICK_START.md          # 3-step quick start guide
└── README.md               # This file
```

---

## 🔧 Common Tasks

### Change Server URL
1. Edit `App.js`
2. Update `DEFAULT_SERVER_URL`
3. Rebuild app

### Update App Version
1. Edit `app.json`
2. Increment `version`
3. Increment `buildNumber` (iOS) / `versionCode` (Android)
4. Rebuild app

### Add Permissions
1. Edit `app.json`
2. Add to `android.permissions` array
3. Add to `ios.infoPlist` with description
4. Rebuild app

### View Build Logs
```bash
eas build:view BUILD_ID
```

### Cancel Build
```bash
eas build:cancel
```

---

## 🆘 Troubleshooting

### Build Fails
1. Check build logs: `eas build:view BUILD_ID`
2. Verify credentials: `eas credentials`
3. Check eas.json configuration
4. See BUILD_GUIDE.md troubleshooting section

### iOS Provisioning Error
```bash
eas credentials -p ios
# Remove all → Regenerate
```

### Android Keystore Error
```bash
eas credentials -p android
# Remove all → Regenerate
```

### App Won't Connect
1. Check backend server is running
2. Verify firewall allows connections
3. Ensure phone and PC on same network
4. Update server URL in app settings (⚙️ IP button)

---

## 📚 Documentation

- **Quick Start:** [QUICK_START.md](QUICK_START.md) - Build apps in 3 steps
- **Build Guide:** [BUILD_GUIDE.md](BUILD_GUIDE.md) - Complete build documentation
- **Expo Docs:** https://docs.expo.dev/
- **EAS Build:** https://docs.expo.dev/build/setup/
- **React Native:** https://reactnative.dev/

---

## 🚢 Deployment

### Internal Testing
1. Build: `npm run build:preview`
2. Share APK download link
3. iOS: Submit to TestFlight

### App Stores
1. Build: `npm run build:production`
2. Submit: `npm run submit:android` / `npm run submit:ios`
3. Wait for store review (1-7 days)

---

## 🎯 Release Checklist

Before production release:
- [ ] Update version numbers in app.json
- [ ] Test on real Android device
- [ ] Test on real iPhone
- [ ] Verify backend connection
- [ ] Test camera permissions
- [ ] Test form scanning
- [ ] Update app store listings
- [ ] Prepare marketing materials
- [ ] Submit for review

---

## 📄 License

See main project LICENSE file.

---

## 💬 Support

- **Issues:** Report in main project repository
- **Questions:** See BUILD_GUIDE.md
- **Expo Help:** https://chat.expo.dev/

---

**Built with:**
- React Native 0.86
- Expo SDK 57
- React 19
- WebView 13

**Package:** `com.ink2insight.scanner`  
**Version:** 1.0.0  
**Build System:** EAS Build
