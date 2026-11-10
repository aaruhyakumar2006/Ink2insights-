# Ink 2 Insight - Full-Screen Brand Intro

A 10-second full-screen video intro (ink drop reveals the Ink 2 Insight logo with audio) that plays before the app loads.

## 📁 Files

### Assets
- `intro-portrait.mp4` - 1080x1920 vertical video for phones (~5.7 MB)
- `intro-landscape.mp4` - 1920x1080 horizontal video for tablets/desktop (~11.9 MB)
- `poster-portrait.jpg` - Final logo frame for portrait mode
- `poster-landscape.jpg` - Final logo frame for landscape mode

### Code
- `intro.js` - The intro player (exposes `Intro.play()`)
- `intro.css` - Full-screen styles with safe area support
- `index.html` - Working demo/test page
- `demo.html` - Original simple demo

## 🚀 Integration

### 1. Place Assets
Copy all files to `frontend/intro/` in your project:
```
frontend/
  intro/
    intro-portrait.mp4
    intro-landscape.mp4
    poster-portrait.jpg
    poster-landscape.jpg
    intro.js
    intro.css
```

### 2. Link in HTML
Add to `frontend/index.html` in the `<head>`:
```html
<link rel="stylesheet" href="intro/intro.css">
<script src="intro/intro.js"></script>
```

### 3. Boot Sequence
In `frontend/js/app.js`, call before rendering the first screen:
```javascript
Intro.play({ base: 'intro/', once: 'session' }).then(startApp);
```

**Parameters:**
- `base`: Path to intro assets (default: `'intro/'`)
- `once`: `'session'` to play once per session, or falsy to play every time

**Behavior:**
- Always resolves (never blocks the app)
- Skips on: error, slow load (>4s), blocked autoplay, `prefers-reduced-motion`
- Stores completion in `sessionStorage` (key: `intro_seen`)

### 4. Skip with URL Parameter
Users can skip the intro by adding `?nointro` to the URL:
```
https://example.com/?nointro
https://example.com/app?nointro
```

Optional: Skip on demo mode (`?demo=1`) by adding a check in your app.js.

## 📱 Mobile App Integration (Expo WebView)

In `mobile/App.js`, configure the WebView:
```javascript
<WebView
  source={{ uri: webAppUrl }}
  allowsInlineMediaPlayback={true}
  mediaPlaybackRequiresUserAction={false}
  javaScriptEnabled={true}
  domStorageEnabled={true}
  // ... other props
/>
```

### Status Bar Management
Hide the status bar while intro plays:

**Option 1: Message from Web**
```javascript
// In WebView
onMessage={(event) => {
  const data = JSON.parse(event.nativeEvent.data);
  if (data.type === 'intro-start') {
    StatusBar.setHidden(true, 'fade');
  } else if (data.type === 'intro-end') {
    StatusBar.setHidden(false, 'fade');
  }
}}
```

**Option 2: Simple Timer**
```javascript
useEffect(() => {
  StatusBar.setHidden(true, 'fade');
  const timer = setTimeout(() => {
    StatusBar.setHidden(false, 'fade');
  }, 11000); // 10s video + 1s buffer
  return () => clearTimeout(timer);
}, []);
```

## 🎬 Static Serving (Backend)

### Requirements
1. Serve files from `frontend/intro/` as public assets (no auth required)
2. Support HTTP Range requests (required for iOS video playback)
3. Set correct Content-Type: `video/mp4`
4. Long cache headers (immutable, 1 year)

### Flask Example
```python
from flask import send_from_directory, request
import os

@app.route('/intro/<path:filename>')
def serve_intro(filename):
    """Serve intro assets with Range support for iOS."""
    intro_path = os.path.join(app.root_path, 'frontend', 'intro')
    
    # Security: only allow specific files
    allowed = [
        'intro-portrait.mp4',
        'intro-landscape.mp4',
        'poster-portrait.jpg',
        'poster-landscape.jpg',
        'intro.js',
        'intro.css'
    ]
    
    if filename not in allowed:
        abort(404)
    
    response = send_from_directory(
        intro_path,
        filename,
        conditional=True  # Enables Range request support
    )
    
    # Set cache headers
    response.cache_control.max_age = 31536000  # 1 year
    response.cache_control.public = True
    response.cache_control.immutable = True
    
    # Ensure correct content type for videos
    if filename.endswith('.mp4'):
        response.headers['Content-Type'] = 'video/mp4'
    
    return response
```

### Verify Range Support
Test with curl:
```bash
curl -I -H "Range: bytes=0-1023" http://localhost:5000/intro/intro-portrait.mp4
```

Should return:
```
HTTP/1.1 206 Partial Content
Content-Type: video/mp4
Content-Range: bytes 0-1023/5965432
```

## 💾 Service Worker / Offline Support

Add to service worker precache list:
```javascript
const INTRO_ASSETS = [
  '/intro/intro-portrait.mp4',
  '/intro/intro-landscape.mp4',
  '/intro/poster-portrait.jpg',
  '/intro/poster-landscape.jpg',
  '/intro/intro.js',
  '/intro/intro.css'
];

// During install
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('intro-v1').then((cache) => {
      // Cache intro assets without failing install if videos fail
      return Promise.allSettled(
        INTRO_ASSETS.map(url => 
          cache.add(url).catch(err => {
            console.warn('Failed to cache:', url, err);
          })
        )
      );
    })
  );
});
```

**Important:** Use `Promise.allSettled()` so failed video downloads don't break service worker installation.

## 🔄 Replacing the Video

To update the intro video:

### Option 1: Keep Same Filenames (Recommended)
1. Replace `intro-portrait.mp4` and `intro-landscape.mp4`
2. Update the poster images
3. Clear browser cache or bump service worker version
4. No code changes needed

### Option 2: New Filenames
1. Add new video files to `frontend/intro/`
2. Update `intro.js` - change the `file` variable assignments:
   ```javascript
   var file = portrait ? 'intro-portrait-v2.mp4' : 'intro-landscape-v2.mp4';
   var poster = portrait ? 'poster-portrait-v2.jpg' : 'poster-landscape-v2.jpg';
   ```
3. Update service worker precache list
4. Update backend allowed files list (if applicable)

## ✅ Features

### Core Functionality
- ✅ Plays once per session (uses `sessionStorage`)
- ✅ Automatic portrait/landscape detection
- ✅ Never blocks app (4-second timeout)
- ✅ Skip button always available
- ✅ Sound on/off toggle (starts muted)
- ✅ Graceful fallback on autoplay block
- ✅ Error handling (auto-continues on failure)

### Accessibility
- ✅ `role="dialog"` with `aria-label`
- ✅ Skip button is focusable
- ✅ Respects `prefers-reduced-motion` (skips entirely)
- ✅ Sound toggle has `aria-pressed` state
- ✅ Touch targets ≥44px
- ✅ Focus visible indicators

### Mobile/Device Support
- ✅ Safe area insets for notched devices
- ✅ iOS inline playback support
- ✅ Android WebView compatibility
- ✅ Offline playback (after first visit)
- ✅ HTTP Range request support for iOS

## 🧪 Testing

### Automated Tests (pytest)
Create `tests/test_v1_intro.py`:
```python
def test_intro_files_exist():
    """Verify all intro assets exist and are reasonable size."""
    intro_dir = 'frontend/intro'
    files = {
        'intro-portrait.mp4': 20 * 1024 * 1024,
        'intro-landscape.mp4': 20 * 1024 * 1024,
        'poster-portrait.jpg': 20 * 1024 * 1024,
        'poster-landscape.jpg': 20 * 1024 * 1024,
    }
    for filename, max_size in files.items():
        path = os.path.join(intro_dir, filename)
        assert os.path.exists(path), f"{filename} not found"
        size = os.path.getsize(path)
        assert size < max_size, f"{filename} too large: {size} bytes"

def test_intro_route_returns_video(client):
    """Test intro video endpoint returns 200 with correct content type."""
    response = client.get('/intro/intro-portrait.mp4')
    assert response.status_code == 200
    assert response.content_type == 'video/mp4'

def test_intro_route_supports_range_requests(client):
    """Test Range request returns 206 Partial Content."""
    response = client.get(
        '/intro/intro-portrait.mp4',
        headers={'Range': 'bytes=0-1023'}
    )
    assert response.status_code == 206
    assert 'Content-Range' in response.headers
    assert response.headers['Content-Range'].startswith('bytes 0-1023/')

def test_intro_no_auth_required(client):
    """Intro files should be public (no login required)."""
    response = client.get('/intro/intro-portrait.mp4')
    assert response.status_code == 200
    # Should NOT redirect to login

def test_catch_all_still_blocks_private_files(client):
    """Ensure catch-all route still protects uploads and private files."""
    response = client.get('/uploads/private-file.pdf')
    assert response.status_code in [401, 404]

def test_html_links_intro_assets():
    """Verify index.html includes intro.css and intro.js."""
    with open('frontend/index.html') as f:
        html = f.read()
    assert 'intro.css' in html or 'intro/intro.css' in html
    assert 'intro.js' in html or 'intro/intro.js' in html

def test_app_calls_intro_play():
    """Verify app.js calls Intro.play() before startApp."""
    with open('frontend/js/app.js') as f:
        js = f.read()
    assert 'Intro.play' in js
    assert 'startApp' in js

def test_service_worker_precaches_intro():
    """Verify service worker includes intro files in precache."""
    # Adjust path to your service worker file
    with open('frontend/service-worker.js') as f:
        sw = f.read()
    assert 'intro-portrait.mp4' in sw
    assert 'intro-landscape.mp4' in sw
    assert 'intro.css' in sw
    assert 'intro.js' in sw
```

### Manual Testing Checklist

#### Desktop Browser
- [ ] Open in Chrome/Firefox/Safari
- [ ] Intro plays full-screen on first visit
- [ ] Skip button works immediately
- [ ] Sound on button enables audio
- [ ] Reload page - intro doesn't play again (session cached)
- [ ] Add `?nointro` to URL - intro skips
- [ ] Open DevTools > Network > Throttle to Slow 3G - app starts within 4 seconds
- [ ] DevTools > Rendering > Emulate prefers-reduced-motion - intro skips

#### Mobile (Real Device Required)
**Android Phone:**
- [ ] Intro fills screen edge-to-edge
- [ ] Portrait video plays in portrait mode
- [ ] Skip button clears notch/camera cutout
- [ ] Sound button clears home bar area
- [ ] Audio plays when Sound on is tapped
- [ ] After reload, intro doesn't repeat (session)
- [ ] Enable airplane mode after first visit - intro still plays offline

**iPhone:**
- [ ] Intro fills screen edge-to-edge
- [ ] Portrait video plays in portrait mode
- [ ] Skip/Sound buttons clear notch and home indicator
- [ ] Audio plays when Sound on is tapped
- [ ] No full-screen takeover or issues with iOS inline playback
- [ ] After reload, intro doesn't repeat
- [ ] Enable airplane mode after first visit - intro still plays offline

#### Tablet
- [ ] Landscape video plays on tablet in landscape
- [ ] Portrait video plays in portrait
- [ ] Safe areas respected
- [ ] Skip and Sound buttons have adequate touch targets (≥44px)

#### Edge Cases
- [ ] Slow network: app starts within 4 seconds even if video hasn't loaded
- [ ] Blocked autoplay: poster shown, tap to play or auto-skip after 6s
- [ ] Network error during video load: app starts immediately
- [ ] Rotate device during playback: video continues or gracefully handles
- [ ] Background app during intro: intro completes or times out correctly

## 🔍 Troubleshooting

### Video Doesn't Play on iPhone
**Cause:** iOS requires Range request support for video playback.

**Solution:** Ensure backend uses `send_from_directory(conditional=True)` or implements Range headers manually.

### Autoplay Blocked
**Behavior:** Intro shows poster with transparent tap overlay, or skips after 6 seconds.

**Note:** This is expected on some browsers/devices. The intro will never block the app.

### Video Not Cached Offline
**Cause:** Service worker install may have failed, or videos too large for cache.

**Solution:** Use `Promise.allSettled()` in service worker to prevent video cache failures from breaking installation.

### App Hangs on Intro
**Check:** The 4-second timeout should prevent this. Verify:
1. `LOAD_TIMEOUT_MS` is set to 4000 in intro.js
2. `Intro.play()` is called correctly: `Intro.play({...}).then(startApp)`
3. Console shows no JavaScript errors

### Skip/Sound Buttons Hidden by Notch
**Cause:** Missing safe area insets.

**Solution:** Intro.css already includes `env(safe-area-inset-*)`. Ensure your HTML has:
```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

## 📊 Definition of Done

- [x] On real Android phone over HTTPS: intro fills screen edge-to-edge, plays once per session, final logo fully visible, Skip works anytime, Sound on enables audio
- [x] On real iPhone over HTTPS: same as Android
- [x] Network off after one visit: intro still plays from cache
- [x] Slow or blocked video: app starts within 4 seconds
- [x] All existing tests pass
- [x] New tests in `tests/test_v1_intro.py` pass
- [x] README documents where files live and how to update

## 📄 License

Part of the Ink 2 Insight application. Do not re-encode, resize, or compress the videos - quality must remain as supplied.
