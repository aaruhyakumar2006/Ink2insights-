# Ink 2 Insight – Brand Intro Video

Full-screen intro video player with sound toggle and skip button. Ready for integration into the Ink 2 Insight application.

## Files

### Media Assets
- **`intro-portrait.mp4`** (5.43 MB, 1080×1920) – For phones in portrait orientation
- **`intro-landscape.mp4`** (11.36 MB, 1920×1080) – For tablets and desktop
- **`poster-portrait.jpg`** (80 KB) – Final logo frame for portrait, shown while loading or if playback fails
- **`poster-landscape.jpg`** (90 KB) – Final logo frame for landscape

### Code
- **`intro.js`** – Player logic (exposes `Intro.play()`)
- **`intro.css`** – Styling with safe area insets for notches/home bars
- **`demo.html`** – Stand-alone test page

## Integration Steps

### 1. Place Assets
Copy all files to `frontend/intro/` in your repository:
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

### 2. Link CSS and JS in `frontend/index.html`
Add these lines in the `<head>`:
```html
<link rel="stylesheet" href="intro/intro.css">
<script src="intro/intro.js"></script>
```

### 3. Modify Boot Sequence in `frontend/js/app.js`

**Before the first screen renders**, call:
```javascript
Intro.play({ base: 'intro/', once: 'session' }).then(startApp);
```

This plays the intro once per session before splash/login.

**For NEW_UI mode**, apply the same logic before the new splash screen.

**Keep `?nointro` parameter** as a way to skip the intro entirely.

### 4. Static File Serving

The backend must:
- Serve files from `frontend/intro/` as public static assets (no authentication required)
- **Support HTTP Range requests** for video files (iOS requires this)
- Use `send_from_directory(..., conditional=True)` in Flask/Python
- Set `Content-Type: video/mp4` for `.mp4` files
- Add cache headers for `frontend/intro/`: `Cache-Control: public, max-age=31536000, immutable`

Example Flask route:
```python
@app.route('/intro/<path:filename>')
def serve_intro(filename):
    return send_from_directory('frontend/intro', filename, conditional=True)
```

Verify Range support:
```bash
curl -H "Range: bytes=0-1023" http://localhost:5000/intro/intro-portrait.mp4
# Should return 206 Partial Content with Content-Range header
```

### 5. Service Worker Precache

Add to service worker precache list:
- `intro/intro.js`
- `intro/intro.css`
- `intro/poster-portrait.jpg`
- `intro/poster-landscape.jpg`

**Video caching strategy**: Cache the video file the device actually plays (portrait OR landscape) on first request using the Cache API with Range support. Do not precache videos - they're too large and only one is needed per device.

Example service worker code:
```javascript
// In sw.js precache list
const PRECACHE_URLS = [
  'intro/intro.js',
  'intro/intro.css',
  'intro/poster-portrait.jpg',
  'intro/poster-landscape.jpg',
  // ... other assets
];

// Runtime caching for videos with Range support
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.includes('/intro/intro-') && url.pathname.endsWith('.mp4')) {
    event.respondWith(
      caches.open('intro-videos-v1').then((cache) => {
        return cache.match(event.request).then((response) => {
          if (response) return response;
          return fetch(event.request).then((networkResponse) => {
            // Only cache successful full responses, not partial/failed
            if (networkResponse.ok && networkResponse.status === 200) {
              cache.put(event.request, networkResponse.clone());
            }
            return networkResponse;
          });
        });
      })
    );
  }
});
```

**Important**: Never let a failed or partial video download fail the service worker install.

### 6. Mobile App Shell (Expo WebView in `mobile/App.js`)

Configure the WebView:
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

**Status bar hiding**: The status bar should be hidden while the intro is showing. Implement this via:
- Message from web page to shell when intro starts/ends, OR
- Simple timer fallback (10 seconds)

Audio works with the "Sound on" button on both Android and iOS.

### 7. Accessibility Features

The intro implementation includes:
- `role="dialog"` and `aria-label` on the overlay
- Focusable Skip button with proper focus indicators
- **`prefers-reduced-motion`** detection – skips video entirely when user has reduced motion preference
- Touch targets 44px minimum (WCAG AA compliant)
- Safe area insets for notches and home bars using `env(safe-area-inset-*)`

### 8. Testing

#### Automated Tests (`tests/test_v1_intro.py`)
```python
import os
import pytest
from flask import Flask

def test_intro_files_exist():
    """All four media files must exist and be under 20 MB each."""
    files = [
        'frontend/intro/intro-portrait.mp4',
        'frontend/intro/intro-landscape.mp4',
        'frontend/intro/poster-portrait.jpg',
        'frontend/intro/poster-landscape.jpg'
    ]
    for file in files:
        assert os.path.exists(file), f"{file} not found"
        size_mb = os.path.getsize(file) / (1024 * 1024)
        assert size_mb < 20, f"{file} is {size_mb:.2f} MB (must be under 20 MB)"

def test_intro_video_route_basic(client):
    """GET /intro/intro-portrait.mp4 returns 200 with video/mp4."""
    response = client.get('/intro/intro-portrait.mp4')
    assert response.status_code == 200
    assert response.content_type == 'video/mp4'

def test_intro_video_range_request(client):
    """Range request returns 206 with Content-Range header."""
    response = client.get('/intro/intro-portrait.mp4', 
                         headers={'Range': 'bytes=0-1023'})
    assert response.status_code == 206
    assert 'Content-Range' in response.headers
    assert response.headers['Content-Range'].startswith('bytes 0-1023/')

def test_index_html_links_intro(client):
    """index.html must link intro.css and intro.js."""
    response = client.get('/')
    html = response.data.decode('utf-8')
    assert 'intro.css' in html, "intro.css not linked in index.html"
    assert 'intro.js' in html, "intro.js not linked in index.html"

def test_app_js_calls_intro_play():
    """app.js must call Intro.play() before startApp."""
    with open('frontend/js/app.js', 'r') as f:
        content = f.read()
    assert 'Intro.play' in content, "Intro.play not called in app.js"
    # Verify it's called before startApp
    intro_pos = content.find('Intro.play')
    start_app_pos = content.find('startApp')
    assert intro_pos < start_app_pos, "Intro.play must be called before startApp"

def test_catch_all_route_still_secure(client):
    """Catch-all route must refuse uploads and private files."""
    # Should return 404 or 401 for uploads directory
    response = client.get('/uploads/private.pdf')
    assert response.status_code in [401, 404]
    
    # Should serve /intro/ files without login (public)
    response = client.get('/intro/intro.js')
    assert response.status_code == 200

def test_service_worker_precache_intro():
    """Service worker precache must contain intro files."""
    with open('frontend/sw.js', 'r') as f:
        sw_content = f.read()
    
    required_files = [
        'intro/intro.js',
        'intro/intro.css',
        'intro/poster-portrait.jpg',
        'intro/poster-landscape.jpg'
    ]
    
    for file in required_files:
        assert file in sw_content, f"{file} not in service worker precache"
```

#### Manual Test Checklist

**Cannot be automated - requires real device testing:**

##### On Real Android Phone (over HTTPS)
- [ ] Intro fills screen edge to edge (no black bars)
- [ ] Intro plays once per session (refresh page = plays again; use without closing browser = doesn't replay)
- [ ] Final logo frame is fully visible (not cropped)
- [ ] Skip button works at any time during playback
- [ ] Sound on button turns audio on
- [ ] Status bar is hidden during intro
- [ ] Safe areas respected (buttons clear notch/home bar)

##### On Real iPhone (over HTTPS)
- [ ] Intro fills screen edge to edge
- [ ] Intro plays once per session
- [ ] Final logo frame fully visible
- [ ] Skip button works
- [ ] Sound on button turns audio on
- [ ] Status bar hidden during intro
- [ ] Safe areas respected

##### Offline Mode (After One Full Visit)
- [ ] Turn off network/enable airplane mode
- [ ] Refresh the page
- [ ] Intro still plays from cache
- [ ] All assets load successfully

##### Degraded Conditions
- [ ] **Slow network**: Throttle to Slow 3G - app must start within 4 seconds even if video doesn't load
- [ ] **Blocked autoplay**: Disable autoplay in browser settings - app should still start
- [ ] **Reduced motion**: Enable `prefers-reduced-motion` in OS settings - intro is skipped entirely
- [ ] **`?nointro` parameter**: Add to URL - intro is skipped

##### Edge Cases
- [ ] Portrait phone (9:16 aspect): uses portrait video correctly
- [ ] Landscape tablet: uses landscape video correctly
- [ ] Rotate device during intro: handles gracefully (may need to restart intro)
- [ ] Very slow device: no crashes, app always starts

## API Usage

### `Intro.play(options)`

Returns a `Promise` that always resolves (never rejects) - the app will never be blocked.

**Options:**
- `base` (string, default `'intro/'`) – Path prefix for assets
- `once` (string, optional) – Set to `'session'` to play only once per browser session

**Auto-skip conditions:**
- URL contains `?nointro`
- User has `prefers-reduced-motion` enabled
- Already seen this session (when `once: 'session'`)
- Video fails to load after 4 seconds
- Autoplay is blocked by browser and user doesn't tap within 6 seconds

**Example:**
```javascript
Intro.play({ base: 'intro/', once: 'session' })
  .then(() => {
    console.log('Intro finished');
    startApp();
  });
```

## Replacing the Video

To update the intro video:

### Option 1: Keep File Names (Recommended)
Replace the files with new versions using the **same names**:
- `intro-portrait.mp4` (1080×1920, portrait)
- `intro-landscape.mp4` (1920×1080, landscape)
- `poster-portrait.jpg`
- `poster-landscape.jpg`

No code changes needed.

### Option 2: New File Names
1. Replace the video files with new names
2. Update `intro.js` lines 15-16:
```javascript
var file = portrait ? 'your-new-portrait-name.mp4' : 'your-new-landscape-name.mp4';
var poster = portrait ? 'your-new-poster-portrait.jpg' : 'your-new-poster-landscape.jpg';
```

**Important:** Keep both portrait and landscape versions. Don't resize or compress - quality must stay as supplied.

## Video Specifications

- **Portrait**: 1080×1920 (9:16), suitable for phones
- **Landscape**: 1920×1080 (16:9), suitable for tablets/desktop
- **Format**: H.264 MP4
- **Audio**: Included (muted by default, user can enable)
- **Duration**: ~10 seconds
- **File sizes**: Portrait ~5.7 MB, Landscape ~11.9 MB

## Technical Details

### Orientation Detection
The player selects portrait/landscape based on:
```javascript
var portrait = window.innerHeight > window.innerWidth * 1.1;
```

This means portrait mode needs >10% taller than wide to avoid edge cases on square-ish tablets.

### Timeout Behavior
- **4 seconds**: Maximum wait for video to start playing before giving up
- **6 seconds**: Maximum wait for user tap when autoplay is blocked
- App **always starts** even if intro fails

### Browser Compatibility
- Modern browsers (Chrome 90+, Safari 14+, Firefox 88+)
- iOS Safari (requires Range request support)
- Android WebView
- Expo WebView with proper configuration

### Safe Area Insets
Uses CSS `env(safe-area-inset-*)` for:
- Top: Status bar and notch
- Bottom: Home indicator bar
- Left/Right: Screen edges on notched devices

Works on iPhone X+ and Android devices with system gesture bars.

## Troubleshooting

### Video Won't Play on iPhone
- Ensure Range request support is enabled on the server
- Check `allowsInlineMediaPlayback={true}` in WebView
- Verify HTTPS (required for autoplay)

### App Blocks for 4+ Seconds
- Check network - videos should load within 4s on reasonable connections
- Ensure timeout logic is working (`LOAD_TIMEOUT_MS = 4000`)
- Video cache should prevent this after first visit

### Sound Button Doesn't Work
- Verify `mediaPlaybackRequiresUserAction={false}` in mobile WebView
- Check browser autoplay policies
- Ensure user interacted with page first (mobile requirement)

### Intro Replays Every Time
- Verify `once: 'session'` is set in `Intro.play()` options
- Check sessionStorage is enabled (private browsing may block it)
- Clear sessionStorage manually: `sessionStorage.clear()`

### Service Worker Not Caching
- Check HTTPS (service workers require secure context)
- Verify precache list includes all four assets
- Check browser console for service worker errors
- Ensure video caching logic handles Range requests properly

## Definition of Done

✅ On real Android phone and iPhone over HTTPS:
- Intro fills screen edge to edge
- Plays once per session
- Final logo fully visible
- Skip works anytime
- Sound on turns audio on

✅ Network off after one visit: intro still plays

✅ Slow/blocked video: app starts within 4 seconds

✅ All tests pass: existing tests + `tests/test_v1_intro.py`

## License & Assets

The intro video, posters, and logo are proprietary assets of Ink 2 Insight. Do not redistribute or reuse outside this project.

Code (intro.js, intro.css) may be modified as needed for integration.
