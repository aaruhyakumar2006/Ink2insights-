# Full-Screen Brand Intro - Complete Implementation Guide

This guide walks you through implementing the Ink 2 Insight brand intro video in your application, step by step.

## 📋 Prerequisites

- Existing web application with frontend directory
- Flask backend (or similar Python web framework)
- Optional: Expo mobile app with WebView
- Optional: Service worker for offline support

## 🚀 Quick Start (5 Steps)

### Step 1: Copy Assets

Copy all intro files to `frontend/intro/`:

```bash
mkdir -p frontend/intro
cp intro-portrait.mp4 frontend/intro/
cp intro-landscape.mp4 frontend/intro/
cp poster-portrait.jpg frontend/intro/
cp poster-landscape.jpg frontend/intro/
cp intro.js frontend/intro/
cp intro.css frontend/intro/
```

### Step 2: Update HTML

In `frontend/index.html`, add to the `<head>`:

```html
<link rel="stylesheet" href="intro/intro.css">
<script src="intro/intro.js"></script>
```

Ensure your viewport meta tag includes `viewport-fit=cover`:

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

### Step 3: Update App Boot Sequence

In `frontend/js/app.js`, modify the startup code:

**Before:**
```javascript
function init() {
  startApp();
}
```

**After:**
```javascript
function init() {
  // Play intro before starting app
  Intro.play({ 
    base: 'intro/', 
    once: 'session' 
  }).then(startApp);
}
```

### Step 4: Add Backend Route

In your Flask app (e.g., `app.py`), add:

```python
from flask import send_from_directory
import os

@app.route('/intro/<path:filename>')
def serve_intro(filename):
    """Serve intro assets with Range support for iOS."""
    allowed = [
        'intro-portrait.mp4', 'intro-landscape.mp4',
        'poster-portrait.jpg', 'poster-landscape.jpg',
        'intro.js', 'intro.css'
    ]
    
    if filename not in allowed:
        abort(404)
    
    intro_path = os.path.join(app.root_path, 'frontend', 'intro')
    response = send_from_directory(intro_path, filename, conditional=True)
    
    # Long cache headers
    response.cache_control.max_age = 31536000
    response.cache_control.public = True
    response.cache_control.immutable = True
    
    # Correct Content-Type for videos
    if filename.endswith('.mp4'):
        response.headers['Content-Type'] = 'video/mp4'
    
    return response
```

### Step 5: Test

1. Start your development server
2. Open the app in a browser
3. Intro should play full-screen on first load
4. Click Skip to test skipping
5. Reload - intro should not play again (session cached)
6. Add `?nointro` to URL - intro should skip

## 📱 Mobile App Integration (Optional)

If you have an Expo mobile app with WebView, update `mobile/App.js`:

```javascript
<WebView
  source={{ uri: 'https://your-app.com' }}
  allowsInlineMediaPlayback={true}
  mediaPlaybackRequiresUserAction={false}
  javaScriptEnabled={true}
  domStorageEnabled={true}
/>
```

Add status bar management:

```javascript
import { StatusBar } from 'react-native';
import { useEffect, useState } from 'react';

export default function App() {
  const [statusBarHidden, setStatusBarHidden] = useState(false);
  
  useEffect(() => {
    // Hide status bar for intro duration (10s + 1s buffer)
    setStatusBarHidden(true);
    const timer = setTimeout(() => {
      setStatusBarHidden(false);
    }, 11000);
    
    return () => clearTimeout(timer);
  }, []);
  
  return (
    <>
      <StatusBar hidden={statusBarHidden} animated={true} />
      <WebView {...props} />
    </>
  );
}
```

## 💾 Service Worker / Offline Support (Optional)

Add intro assets to your service worker:

```javascript
const INTRO_ASSETS = [
  '/intro/intro-portrait.mp4',
  '/intro/intro-landscape.mp4',
  '/intro/poster-portrait.jpg',
  '/intro/poster-landscape.jpg',
  '/intro/intro.js',
  '/intro/intro.css'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('intro-cache').then(cache => 
      // Use allSettled so video failures don't break install
      Promise.allSettled(
        INTRO_ASSETS.map(url => 
          cache.add(url).catch(err => 
            console.warn(`Failed to cache ${url}:`, err)
          )
        )
      )
    )
  );
});
```

## 🧪 Testing Checklist

### Automated Tests

Copy `test_v1_intro.py` to `tests/` and run:

```bash
pytest tests/test_v1_intro.py -v
```

All tests should pass.

### Manual Tests - Desktop

- [ ] Open app in Chrome - intro plays
- [ ] Skip button works
- [ ] Sound on button enables audio
- [ ] Reload - intro doesn't replay (cached)
- [ ] Add `?nointro` - intro skips
- [ ] Slow network (DevTools throttle) - app starts within 4s
- [ ] DevTools: prefers-reduced-motion - intro skips

### Manual Tests - Mobile

**Android Phone (Real Device):**
- [ ] Intro fills screen edge-to-edge
- [ ] Portrait video plays in portrait
- [ ] Skip/Sound buttons clear safe areas
- [ ] Audio works
- [ ] Reload - no replay
- [ ] Airplane mode after first visit - plays offline

**iPhone (Real Device):**
- [ ] Same as Android
- [ ] No full-screen video takeover
- [ ] Range requests work (check server logs for 206 responses)

## 🔧 Advanced Configuration

### Skip on Demo Mode

To skip intro when `?demo=1` is in the URL, modify intro.js:

```javascript
if (seen(opts.once) || 
    new URLSearchParams(location.search).has('nointro') ||
    new URLSearchParams(location.search).has('demo') ||  // Add this
    (g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches)) {
  return resolve();
}
```

### Custom Session Storage Key

To use a different storage key:

```javascript
// In intro.js, change 'intro_seen' to your preferred key
sessionStorage.getItem('my_custom_intro_key')
sessionStorage.setItem('my_custom_intro_key', '1')
```

### Play Every Time (No Session Cache)

Change the boot call to:

```javascript
Intro.play({ base: 'intro/', once: false }).then(startApp);
```

### Custom Timeout

To change the 4-second timeout, edit intro.js:

```javascript
var LOAD_TIMEOUT_MS = 6000; // 6 seconds instead of 4
```

## 🐛 Troubleshooting

### Video Doesn't Play on iPhone

**Problem:** Video loads but doesn't play, or shows "play" icon.

**Solution:** iOS requires HTTP Range request support.

**Check:**
```bash
curl -I -H "Range: bytes=0-1023" https://your-app.com/intro/intro-portrait.mp4
```

Should return:
```
HTTP/1.1 206 Partial Content
Content-Range: bytes 0-1023/5965432
```

If you get `200` instead of `206`, Range support is missing. Ensure backend uses `send_from_directory(conditional=True)`.

### Autoplay Blocked

**Problem:** Browser blocks autoplay, video doesn't start.

**Expected behavior:** Intro.js handles this automatically:
1. Shows poster image
2. Displays transparent tap overlay
3. Taps start playback
4. Or auto-skips after 6 seconds

**This is not a bug** - it's the intended fallback behavior.

### App Hangs on Intro

**Problem:** App doesn't start after intro.

**Check:**
1. Console for JavaScript errors
2. Verify `Intro.play().then(startApp)` syntax
3. Confirm `startApp` function exists
4. Check if 4-second timeout is triggering (should auto-continue)

**Debug:**
```javascript
Intro.play({ base: 'intro/', once: 'session' })
  .then(() => {
    console.log('Intro finished');
    startApp();
  })
  .catch(err => {
    console.error('Intro error:', err);
    startApp(); // Start anyway
  });
```

### Videos Not Caching

**Problem:** Videos don't work offline.

**Check:**
1. Service worker registered successfully
2. Browser cache storage quota (Settings > Storage)
3. File sizes (should be < 20 MB each)
4. Network tab shows videos loading
5. Application > Cache Storage in DevTools

**Fix:** Use `Promise.allSettled()` in service worker so video cache failures don't break installation.

### Skip/Sound Buttons Hidden by Notch

**Problem:** Buttons covered by iPhone notch or home indicator.

**Check viewport meta tag:**
```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

intro.css already includes `env(safe-area-inset-*)` for proper spacing.

## 📊 Performance Considerations

### File Sizes

Current files:
- `intro-portrait.mp4`: ~5.7 MB
- `intro-landscape.mp4`: ~11.9 MB
- Posters: ~200-500 KB each

**Do not re-encode or compress.** Quality must remain as supplied per client requirements.

### Network Impact

- First load: Downloads 5.7-11.9 MB (based on orientation)
- Subsequent visits: Served from cache
- 4-second timeout ensures app never hangs

### Cache Strategy

- Browser cache: 1 year (`max-age=31536000`)
- Service worker: Precached for offline
- Session storage: Tracks "seen" status

## ✅ Definition of Done

All must be true:

- [ ] Assets in `frontend/intro/`
- [ ] HTML links intro.css and intro.js
- [ ] App.js calls `Intro.play()` before `startApp()`
- [ ] Backend serves intro files with Range support
- [ ] GET /intro/intro-portrait.mp4 returns 200, Content-Type video/mp4
- [ ] Range request returns 206 with Content-Range
- [ ] Service worker precaches intro files (if applicable)
- [ ] Intro plays once per session on real Android phone over HTTPS
- [ ] Intro plays once per session on real iPhone over HTTPS
- [ ] Skip and Sound buttons work
- [ ] Final logo fully visible
- [ ] Offline playback works after first visit
- [ ] Slow network: app starts within 4 seconds
- [ ] All existing tests pass
- [ ] New tests in tests/test_v1_intro.py pass

## 📞 Support

For implementation questions or issues:

1. Check this guide and README.md
2. Review example files:
   - `backend_example.py` - Flask server implementation
   - `mobile_app_example.js` - Expo WebView config
   - `service-worker-example.js` - Offline caching
3. Test with `demo.html` or `index.html` standalone
4. Check browser console for errors
5. Verify backend logs for Range requests (206 status)

## 🎉 Success Criteria

When complete, users will experience:

1. **First Visit:**
   - App loads
   - Full-screen intro plays with ink drop animation
   - Logo reveal with audio (if Sound on clicked)
   - Skip available anytime
   - App starts after 10 seconds or when skipped

2. **Subsequent Visits (Same Session):**
   - App starts immediately
   - No intro replay

3. **Offline:**
   - After one online visit, intro plays from cache
   - No network required

4. **Edge Cases:**
   - Slow network: App starts within 4 seconds
   - Blocked autoplay: Tap to play or auto-skip
   - Reduced motion preference: Intro skips entirely
   - Mobile devices: Proper safe area handling

Ready to implement? Follow the Quick Start section and test each step!
