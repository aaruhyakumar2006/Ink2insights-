# Integration Guide – Ink 2 Insight Intro Video

Step-by-step code examples for integrating the intro into your application.

## Prerequisites

Copy all files from this directory to `frontend/intro/` in your main repository.

## 1. HTML Integration

### Add to `frontend/index.html` `<head>` section:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Ink 2 Insight</title>
  
  <!-- Existing stylesheets -->
  <link rel="stylesheet" href="css/main.css">
  
  <!-- ADD THESE LINES -->
  <link rel="stylesheet" href="intro/intro.css">
  <script src="intro/intro.js"></script>
  
</head>
<body>
  <!-- Your app markup -->
</body>
</html>
```

**Note:** The `viewport-fit=cover` meta tag is important for safe area insets to work properly on notched devices.

## 2. App Boot Sequence

### Modify `frontend/js/app.js`:

**Before (typical app.js):**
```javascript
document.addEventListener('DOMContentLoaded', function() {
  startApp();
});

function startApp() {
  // Initialize app
  showSplashScreen();
  checkAuth();
  // ... rest of app logic
}
```

**After (with intro):**
```javascript
document.addEventListener('DOMContentLoaded', function() {
  // Play intro BEFORE starting app
  Intro.play({ base: 'intro/', once: 'session' }).then(startApp);
});

function startApp() {
  // Initialize app
  showSplashScreen();
  checkAuth();
  // ... rest of app logic
}
```

### For NEW_UI mode:

```javascript
document.addEventListener('DOMContentLoaded', function() {
  if (window.NEW_UI) {
    // NEW_UI: intro before new splash
    Intro.play({ base: 'intro/', once: 'session' }).then(function() {
      showNewSplash();
      startApp();
    });
  } else {
    // Legacy: intro before old splash
    Intro.play({ base: 'intro/', once: 'session' }).then(startApp);
  }
});
```

### Keep `?nointro` skip functionality:

The intro.js already handles `?nointro` internally, so no code changes needed. Users can add `?nointro` to any URL to skip the intro.

## 3. Backend – Static File Serving (Flask)

### Add route to serve intro files in `app.py` or `routes.py`:

```python
from flask import Flask, send_from_directory

app = Flask(__name__)

# ... existing routes ...

@app.route('/intro/<path:filename>')
def serve_intro(filename):
    """
    Serve intro assets as public static files.
    - No authentication required
    - Supports HTTP Range requests (required for iOS video)
    - Long cache headers for immutable assets
    """
    response = send_from_directory('frontend/intro', filename, conditional=True)
    
    # Set Content-Type for video files
    if filename.endswith('.mp4'):
        response.headers['Content-Type'] = 'video/mp4'
    
    # Long cache headers (1 year, immutable)
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    
    return response
```

### Verify Range request support:

```bash
# Test with curl (should return 206 Partial Content)
curl -I -H "Range: bytes=0-1023" http://localhost:5000/intro/intro-portrait.mp4

# Expected response headers:
# HTTP/1.1 206 Partial Content
# Content-Range: bytes 0-1023/5693440
# Content-Type: video/mp4
```

### Alternative: Nginx serving

If using Nginx to serve static files:

```nginx
# In your nginx.conf or site config
location /intro/ {
    alias /path/to/frontend/intro/;
    
    # Enable Range requests
    add_header Accept-Ranges bytes;
    
    # Long cache for immutable assets
    add_header Cache-Control "public, max-age=31536000, immutable";
    
    # Correct MIME types
    types {
        video/mp4 mp4;
        text/css css;
        application/javascript js;
        image/jpeg jpg;
    }
}
```

## 4. Service Worker – Offline Caching

### Modify `frontend/sw.js`:

**Add to precache list (only small files):**

```javascript
const CACHE_VERSION = 'v1.2.0';
const PRECACHE_URLS = [
  '/',
  'css/main.css',
  'js/app.js',
  // ... existing assets ...
  
  // ADD THESE INTRO FILES
  'intro/intro.js',
  'intro/intro.css',
  'intro/poster-portrait.jpg',
  'intro/poster-landscape.jpg',
  // NOTE: Do NOT precache .mp4 files (too large)
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => {
      return cache.addAll(PRECACHE_URLS);
    })
  );
});
```

**Add runtime caching for video files with Range support:**

```javascript
// Runtime caching for intro videos (NOT precached)
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // Handle intro video requests with Range support
  if (url.pathname.includes('/intro/intro-') && url.pathname.endsWith('.mp4')) {
    event.respondWith(
      caches.open('intro-videos-v1').then((cache) => {
        return cache.match(event.request).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          
          // Fetch from network and cache
          return fetch(event.request).then((networkResponse) => {
            // Only cache successful full responses (200 OK)
            // Don't cache partial responses (206) or errors
            if (networkResponse.ok && networkResponse.status === 200) {
              cache.put(event.request, networkResponse.clone());
            }
            return networkResponse;
          }).catch(() => {
            // Network failed - return nothing (intro will timeout gracefully)
            return new Response('', { status: 408 });
          });
        });
      })
    );
    return;
  }
  
  // ... handle other requests ...
});
```

**Important notes:**
- Only cache status 200 responses (full video)
- Don't cache 206 Partial Content responses
- Failed video downloads should not break the service worker
- The intro.js timeout (4s) ensures the app still starts if video fails

## 5. Mobile App Shell (Expo WebView)

### Modify `mobile/App.js` (React Native Expo):

```javascript
import React, { useState } from 'react';
import { View, StatusBar } from 'react-native';
import { WebView } from 'react-native-webview';

export default function App() {
  const [hideStatusBar, setHideStatusBar] = useState(false);

  const handleMessage = (event) => {
    const message = JSON.parse(event.nativeEvent.data);
    
    // Handle intro start/end messages from web page
    if (message.type === 'intro:start') {
      setHideStatusBar(true);
    } else if (message.type === 'intro:end') {
      setHideStatusBar(false);
    }
  };

  return (
    <View style={{ flex: 1 }}>
      <StatusBar hidden={hideStatusBar} />
      <WebView
        source={{ uri: 'https://your-app-url.com' }}
        
        // REQUIRED FOR INTRO VIDEO
        allowsInlineMediaPlayback={true}
        mediaPlaybackRequiresUserAction={false}
        
        // Standard settings
        javaScriptEnabled={true}
        domStorageEnabled={true}
        
        // Handle messages from web page
        onMessage={handleMessage}
      />
    </View>
  );
}
```

### Add messaging to `intro.js` (optional enhancement):

To send messages to the native shell, add this to intro.js after line 20:

```javascript
// After: document.body.appendChild(root);
if (window.ReactNativeWebView) {
  window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'intro:start' }));
}

// In finish() function, before resolve():
if (window.ReactNativeWebView) {
  window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'intro:end' }));
}
```

### Simple timer fallback (if messages not working):

```javascript
export default function App() {
  const [hideStatusBar, setHideStatusBar] = useState(false);

  // Simple timer: hide status bar for 12 seconds on app start
  React.useEffect(() => {
    setHideStatusBar(true);
    const timer = setTimeout(() => setHideStatusBar(false), 12000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <View style={{ flex: 1 }}>
      <StatusBar hidden={hideStatusBar} />
      <WebView
        source={{ uri: 'https://your-app-url.com' }}
        allowsInlineMediaPlayback={true}
        mediaPlaybackRequiresUserAction={false}
        javaScriptEnabled={true}
        domStorageEnabled={true}
      />
    </View>
  );
}
```

## 6. Testing the Integration

### Quick manual test:

1. **Start your development server:**
   ```bash
   python app.py
   # or: flask run
   # or: npm start
   ```

2. **Open in browser:**
   ```
   http://localhost:5000
   ```

3. **Expected behavior:**
   - Intro plays automatically
   - Skip button visible in top-right
   - Sound on button in bottom-right
   - After ~10 seconds or click Skip, app starts

4. **Test ?nointro:**
   ```
   http://localhost:5000?nointro
   ```
   Should skip intro entirely.

5. **Test once-per-session:**
   - Refresh page → intro plays again
   - Navigate away and back → no intro
   - Close browser and reopen → intro plays

### Test on real devices:

**Android (via Chrome DevTools remote debugging):**
```bash
# Connect phone via USB, enable USB debugging
# Chrome -> chrome://inspect -> select device
# Open your app URL with https://
```

**iPhone (via Safari Web Inspector):**
```bash
# Connect phone via USB
# iPhone: Settings -> Safari -> Advanced -> Web Inspector (on)
# Mac Safari -> Develop -> [Your iPhone] -> select page
```

### Test offline mode:

1. Visit site once with network on
2. Open DevTools -> Network tab
3. Check "Offline" checkbox
4. Refresh page
5. Intro should still play

### Run automated tests:

```bash
# Copy test_v1_intro.py to tests/ in your main repo
pytest tests/test_v1_intro.py -v
```

## 7. Common Issues & Solutions

### Issue: Video won't play on iPhone

**Solution:**
- Verify Range request support is working: `curl -I -H "Range: bytes=0-1023" https://your-url/intro/intro-portrait.mp4`
- Ensure HTTPS is used (autoplay requires secure context)
- Check WebView has `allowsInlineMediaPlayback={true}`

### Issue: App blocks for 4+ seconds

**Solution:**
- Check network speed - videos should load within 4s
- Verify timeout logic is working in intro.js
- After first visit, video should be cached

### Issue: Sound button doesn't work on mobile

**Solution:**
- Ensure `mediaPlaybackRequiresUserAction={false}` in WebView
- Check browser autoplay policies
- User must interact with page first (tap anywhere)

### Issue: Intro replays every page load

**Solution:**
- Verify `once: 'session'` is set in `Intro.play()` call
- Check sessionStorage is available (private browsing blocks it)
- Clear storage: `sessionStorage.removeItem('intro_seen')`

### Issue: Intro doesn't respect reduced motion

**Solution:**
- Should work automatically
- Test: macOS System Preferences -> Accessibility -> Display -> Reduce motion
- Or: Chrome DevTools -> Cmd+Shift+P -> "Emulate CSS prefers-reduced-motion"

### Issue: Service worker fails to install

**Solution:**
- Check browser console for errors
- Ensure all precache files exist and are accessible
- Don't include .mp4 files in precache (use runtime caching)
- HTTPS required for service workers

## 8. Deployment Checklist

Before deploying to production:

- [ ] All 7 files copied to `frontend/intro/`
- [ ] `index.html` links intro.css and intro.js
- [ ] `app.js` calls `Intro.play()` before `startApp()`
- [ ] Backend serves `/intro/` with Range request support
- [ ] Service worker precaches intro.js, intro.css, and posters (NOT videos)
- [ ] Service worker runtime-caches videos
- [ ] Mobile WebView configured with correct props
- [ ] Tested on real Android phone (HTTPS)
- [ ] Tested on real iPhone (HTTPS)
- [ ] Tested offline mode
- [ ] Tested `?nointro` parameter
- [ ] Tested reduced motion preference
- [ ] All existing tests still pass
- [ ] New tests in `tests/test_v1_intro.py` pass

## 9. Updating the Video

To replace the intro video later:

### Option 1: Keep same file names (recommended)
1. Replace files with new versions:
   - `intro-portrait.mp4`
   - `intro-landscape.mp4`
   - `poster-portrait.jpg`
   - `poster-landscape.jpg`

2. Bump service worker version to force cache refresh:
   ```javascript
   const CACHE_VERSION = 'v1.3.0'; // increment version
   ```

3. Deploy - no code changes needed

### Option 2: New file names
1. Replace video files
2. Update intro.js lines 15-16 with new file names
3. Update service worker precache list
4. Deploy

## 10. Performance Optimization

The intro is already optimized, but here are the key strategies:

**Load time:**
- Videos are NOT precached (too large)
- Only essential files precached: JS, CSS, posters (~170 KB total)
- Videos cached on-demand after first play
- 4-second timeout ensures app never blocks

**Network usage:**
- Portrait devices only download portrait video
- Landscape devices only download landscape video
- Once per session = minimal repeated downloads
- Cache-Control headers prevent re-downloads

**Device compatibility:**
- Orientation detection picks correct video
- Graceful degradation on errors
- Always resolves (never blocks app)
- Reduced motion support

## Support

For issues or questions:
1. Check browser console for errors
2. Review TROUBLESHOOTING section in README.md
3. Run `pytest tests/test_v1_intro.py -v` to identify integration issues
4. Test on real devices (emulators may behave differently)
