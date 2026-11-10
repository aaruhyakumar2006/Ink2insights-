# 🚀 Build Your Mobile Apps NOW - 3 Steps

## ✅ Step 1: Install EAS CLI (1 minute)
```bash
npm install --global eas-cli
```

## ✅ Step 2: Login (1 minute)
```bash
eas login
```
Don't have an account? Sign up free: https://expo.dev/signup

## ✅ Step 3: Build! (automated)

**Option A: Use PowerShell Script (EASIEST)**
```powershell
cd mobile
.\build-apps.ps1
```

**Option B: Use npm Commands**
```bash
cd mobile

# Build both Android APK + iOS IPA
npm run build:preview

# Or build just Android APK
npm run build:android

# Or build just iOS IPA (requires Apple Developer Program)
npm run build:ios
```

---

## 📥 What Happens Next?

1. **Build starts** (you'll see a progress URL)
2. **Wait 10-20 minutes** (you can close terminal)
3. **Get notification** via email when ready
4. **Download APK/IPA** from the URL

---

## 📱 Installing Your Apps

### Android APK
1. Open build URL on your Android phone
2. Tap "Install"
3. Allow install from unknown sources
4. ✅ Done!

### iOS IPA
1. Build completes → Run: `eas submit --platform ios`
2. Add testers in App Store Connect
3. They install via TestFlight app
4. ✅ Done!

---

## 💡 Quick Tips

- **First build?** Choose Android - it's simpler (no paid account needed)
- **iOS requires:** Apple Developer Program ($99/year)
- **Monitor build:** Open the URL shown in terminal
- **Failed build?** Run: `eas build:list` to see what happened

---

## 🆘 Troubleshooting

**"eas: command not found"**
```bash
npm install --global eas-cli
```

**"Not logged in"**
```bash
eas login
```

**"Build failed"**
```bash
# Check status
eas build:list

# View detailed logs
eas build:view BUILD_ID
```

---

## 📚 Need More Help?

- **Detailed Guide:** See `BUILD_GUIDE.md`
- **Expo Docs:** https://docs.expo.dev/build/setup/
- **Discord Help:** https://chat.expo.dev/

---

**Ready? Run this now:**

```bash
cd mobile
npm install --global eas-cli
eas login
npm run build:preview
```

Your mobile apps will be ready in 10-20 minutes! 🎉
