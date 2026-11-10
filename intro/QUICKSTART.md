# Quick Start – Test the Intro

Fast instructions to test the intro video locally.

## 1. Test the Demo (Stand-Alone)

The easiest way to see the intro in action:

```bash
# Start a local server in this directory
python -m http.server 8000
```

Then open in your browser:
```
http://localhost:8000/demo.html
```

**What you'll see:**
- Intro plays automatically (portrait or landscape based on window size)
- Skip button in top-right
- Sound on button in bottom-right
- After ~10 seconds, shows "App starts here"
- Click "Replay" to test again

## 2. Test Different Scenarios

### Test Portrait vs Landscape
- **Portrait:** Resize browser window to tall/narrow (phone-like)
- **Landscape:** Resize to wide (tablet/desktop)
- Refresh to see different video

### Test Skip Functionality
- Refresh page
- Click "Skip" button immediately
- Should jump to end screen

### Test Sound Toggle
- Refresh page
- Click "Sound on" button
- Audio should play (check volume is up!)

### Test URL Parameters
```bash
# Skip intro entirely
http://localhost:8000/demo.html?nointro
```

### Test Reduced Motion
**Chrome DevTools:**
1. Open DevTools (F12)
2. Cmd/Ctrl + Shift + P
3. Type "emulate reduced motion"
4. Select "Emulate CSS prefers-reduced-motion: reduce"
5. Refresh page
6. Intro should skip automatically

**macOS System-Wide:**
1. System Preferences → Accessibility → Display
2. Check "Reduce motion"
3. Refresh page
4. Intro skips

### Test Session Storage (Once Per Session)
1. Open `demo.html` - intro plays
2. Navigate away: `window.location = 'about:blank'`
3. Go back to `demo.html` - intro DOES NOT play
4. Close browser completely
5. Reopen `demo.html` - intro plays again

To reset: Open console and run:
```javascript
sessionStorage.clear()
```

## 3. Test on Mobile Device (Same Network)

### Find Your Computer's IP:
```bash
# Windows
ipconfig
# Look for "IPv4 Address" (usually 192.168.x.x)

# Mac/Linux
ifconfig | grep inet
```

### Connect Mobile Device:
1. Connect phone to **same WiFi** as computer
2. Open browser on phone
3. Navigate to: `http://YOUR_IP:8000/demo.html`
   - Example: `http://192.168.1.100:8000/demo.html`

**Test on phone:**
- Rotate device (portrait/landscape)
- Test Skip button (touch)
- Test Sound button (touch)
- Check safe areas on notched phones

## 4. Test Offline Mode

### In Chrome/Edge:
1. Open demo.html
2. Open DevTools (F12)
3. Go to "Network" tab
4. Check "Offline" box
5. Refresh page
6. **Expected:** Intro plays from cache

### Service Worker Test:
For full offline testing, you need a real service worker. Use this test page:

**Create `sw-test.html`:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Intro SW Test</title>
  <link rel="stylesheet" href="intro.css">
</head>
<body>
  <h1>Service Worker Test</h1>
  <p id="status">Checking SW...</p>
  <button onclick="testIntro()">Play Intro</button>
  <script src="intro.js"></script>
  <script>
    // Register minimal service worker
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw-test.js').then(() => {
        document.getElementById('status').textContent = 'SW registered!';
      }).catch(err => {
        document.getElementById('status').textContent = 'SW failed: ' + err;
      });
    }
    
    function testIntro() {
      Intro.play({ base: './', once: false }).then(() => {
        console.log('Intro done');
      });
    }
  </script>
</body>
</html>
```

**Create `sw-test.js`:**
```javascript
const CACHE_NAME = 'intro-test-v1';
const PRECACHE = [
  'intro.js',
  'intro.css',
  'poster-portrait.jpg',
  'poster-landscape.jpg'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE))
  );
});

self.addEventListener('fetch', (e) => {
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
```

Then:
1. Visit `http://localhost:8000/sw-test.html`
2. Wait for SW registration
3. Go offline
4. Refresh
5. Videos should cache on first play, posters work offline immediately

## 5. Performance Testing

### Measure Load Time:
Open DevTools Console and run:
```javascript
performance.mark('intro-start');
Intro.play({ base: './', once: false }).then(() => {
  performance.mark('intro-end');
  performance.measure('intro-duration', 'intro-start', 'intro-end');
  const measure = performance.getEntriesByName('intro-duration')[0];
  console.log(`Intro took ${measure.duration}ms`);
});
```

### Test Timeout (Slow Network):
1. DevTools → Network tab
2. Set throttling to "Slow 3G"
3. Refresh page
4. **Expected:** App starts within 4 seconds even if video hasn't loaded

### Check File Sizes:
```javascript
// In DevTools Console after page load
performance.getEntriesByType('resource')
  .filter(r => r.name.includes('intro'))
  .forEach(r => console.log(r.name, (r.transferSize / 1024).toFixed(2) + ' KB'));
```

## 6. Browser Compatibility Testing

Test in multiple browsers:

- [ ] **Chrome** (desktop & mobile)
- [ ] **Safari** (desktop & mobile)
- [ ] **Firefox**
- [ ] **Edge**
- [ ] **Samsung Internet** (Android)

### Known Issues:
- **Firefox:** May need interaction before audio plays (click Sound button)
- **Safari:** Requires Range request support from server
- **Old iOS (<14):** May not support some features

## 7. Debugging

### Check if intro.js loaded:
```javascript
console.log(typeof Intro); // Should be "object"
console.log(Intro.play);   // Should be function
```

### Force intro to play (ignore session storage):
```javascript
sessionStorage.removeItem('intro_seen');
Intro.play({ base: './', once: 'session' }).then(() => {
  console.log('Done');
});
```

### Check video selection:
```javascript
const portrait = window.innerHeight > window.innerWidth * 1.1;
console.log('Orientation:', portrait ? 'portrait' : 'landscape');
console.log('Video:', portrait ? 'intro-portrait.mp4' : 'intro-landscape.mp4');
```

### Monitor events:
```javascript
const video = document.querySelector('.intro video');
if (video) {
  video.addEventListener('loadstart', () => console.log('Load started'));
  video.addEventListener('canplay', () => console.log('Can play'));
  video.addEventListener('playing', () => console.log('Playing'));
  video.addEventListener('ended', () => console.log('Ended'));
  video.addEventListener('error', (e) => console.log('Error:', e));
}
```

## 8. Common Problems

### Problem: "Failed to load resource"
**Solution:** Check server is running and files exist
```bash
ls -lh intro-*.mp4
```

### Problem: Video doesn't autoplay
**Solution:** 
- Check browser autoplay policy (needs muted video)
- Ensure HTTPS in production
- User may need to interact with page first

### Problem: Wrong video plays (portrait on desktop)
**Solution:**
- Check window dimensions
- Threshold is `height > width * 1.1`
- May need to refresh after resizing

### Problem: Skip button not visible
**Solution:**
- Check CSS is loaded
- Use DevTools Elements inspector
- Verify z-index and positioning

### Problem: Sound button doesn't work
**Solution:**
- Check browser audio policy
- Try clicking elsewhere first (activate page)
- Check system volume

## 9. Integration Test

Once you integrate into your app:

```bash
# In your main app directory
pytest tests/test_v1_intro.py -v

# Run all tests
pytest -v

# Run specific test
pytest tests/test_v1_intro.py::TestIntroAssets::test_intro_files_exist -v
```

## 10. Production Checklist

Before going live:

- [ ] Tested on real Android phone (HTTPS)
- [ ] Tested on real iPhone (HTTPS)
- [ ] Tested offline mode
- [ ] Tested `?nointro` parameter
- [ ] Tested reduced motion
- [ ] Tested slow network (3G)
- [ ] Verified Range requests work
- [ ] Verified cache headers set
- [ ] All automated tests pass
- [ ] Service worker caching works
- [ ] Mobile app shell configured

## Quick Commands Reference

```bash
# Start local server
python -m http.server 8000

# Get computer's IP (Windows)
ipconfig

# Get computer's IP (Mac/Linux)
ifconfig | grep inet

# Test Range request (bash/linux/mac)
curl -I -H "Range: bytes=0-1023" http://localhost:8000/intro-portrait.mp4

# Test Range request (PowerShell)
Invoke-WebRequest -Uri "http://localhost:8000/intro-portrait.mp4" -Headers @{"Range"="bytes=0-1023"} -Method Head

# Clear service worker (DevTools Console)
navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister()))

# Clear all caches (DevTools Console)
caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k))))

# Reset session storage (DevTools Console)
sessionStorage.clear()
```

---

**Need help?** See `README.md` for full documentation and `INTEGRATION_GUIDE.md` for integration instructions.
