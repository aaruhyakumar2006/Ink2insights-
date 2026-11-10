# Quick Reference Card - Intro Integration

## 🎯 5-Minute Integration

### 1. Copy Files
```bash
cp intro/* your-project/frontend/intro/
```

### 2. Update HTML
```html
<!-- In frontend/index.html <head> -->
<link rel="stylesheet" href="intro/intro.css">
<script src="intro/intro.js"></script>
```

### 3. Update App Boot
```javascript
// In frontend/js/app.js
Intro.play({ base: 'intro/', once: 'session' }).then(startApp);
```

### 4. Add Backend Route
```python
# In your Flask app
@app.route('/intro/<path:filename>')
def serve_intro(filename):
    allowed = ['intro-portrait.mp4', 'intro-landscape.mp4',
               'poster-portrait.jpg', 'poster-landscape.jpg',
               'intro.js', 'intro.css']
    if filename not in allowed:
        abort(404)
    response = send_from_directory('frontend/intro', filename, conditional=True)
    response.cache_control.max_age = 31536000
    if filename.endswith('.mp4'):
        response.headers['Content-Type'] = 'video/mp4'
    return response
```

### 5. Test
```bash
# Start server and visit app
# Intro should play once
# Reload - should not replay
# Try ?nointro - should skip
```

## 📱 Mobile Testing

### Quick Local Test
```bash
cd intro/
python -m http.server 8000
# On phone: http://YOUR_IP:8000/index.html
```

### iOS (HTTPS Required)
```bash
ngrok http 8000
# Use the HTTPS URL on iPhone
```

## 🧪 Test Commands

```bash
# Run automated tests
pytest tests/test_v1_intro.py -v

# Test Range support
curl -I -H "Range: bytes=0-1023" http://localhost:5000/intro/intro-portrait.mp4
# Should return: HTTP/1.1 206 Partial Content
```

## 🔧 Common Customizations

### Skip on Demo Mode
```javascript
// Add to intro.js condition check
new URLSearchParams(location.search).has('demo')
```

### Play Every Time (No Cache)
```javascript
Intro.play({ base: 'intro/', once: false }).then(startApp);
```

### Different Timeout
```javascript
// In intro.js
var LOAD_TIMEOUT_MS = 6000; // 6 seconds
```

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Video doesn't play on iPhone | Check Range support: backend must use `conditional=True` |
| App hangs | Check console for errors, verify `then(startApp)` syntax |
| Intro replays every time | Check sessionStorage not blocked, verify `once: 'session'` |
| Buttons hidden by notch | Add `viewport-fit=cover` to meta tag |
| No audio | Expected - starts muted, user clicks Sound on |
| Videos don't cache | Use `Promise.allSettled()` in service worker |

## 📖 File Reference

| File | Purpose |
|------|---------|
| `README.md` | Complete documentation |
| `IMPLEMENTATION_GUIDE.md` | Step-by-step integration guide |
| `IMPLEMENTATION_REPORT.md` | Status and next steps |
| `backend_example.py` | Flask server examples |
| `mobile_app_example.js` | Expo WebView config |
| `service-worker-example.js` | Offline caching |
| `test_v1_intro.py` | Automated tests |
| `index.html` | Working demo |

## ✅ Verification Checklist

**Desktop:**
- [ ] Intro plays in browser
- [ ] Skip works
- [ ] Sound on works
- [ ] ?nointro skips

**Mobile:**
- [ ] Edge-to-edge display
- [ ] Portrait/landscape detection
- [ ] Safe areas respected
- [ ] Audio works

**Backend:**
- [ ] GET /intro/intro-portrait.mp4 returns 200
- [ ] Range request returns 206
- [ ] No auth required

**Tests:**
- [ ] pytest passes
- [ ] Manual tests complete

## 🚀 Deploy Checklist

- [ ] Assets copied to frontend/intro/
- [ ] HTML updated (CSS + JS links)
- [ ] App.js calls Intro.play()
- [ ] Backend route added
- [ ] Tests pass
- [ ] Tested on Android device
- [ ] Tested on iPhone device
- [ ] Service worker updated (if applicable)
- [ ] README updated

## 💡 Tips

- **Never blocks:** 4-second timeout ensures app always starts
- **iOS needs Range:** Use `conditional=True` in Flask
- **Cache aggressively:** 1-year cache headers for performance
- **Test offline:** Should work after one online visit
- **Safe areas:** CSS already handles notches/home bars
- **Accessibility:** Respects prefers-reduced-motion

## 📞 Need Help?

1. Check `README.md` for detailed explanations
2. Check `IMPLEMENTATION_GUIDE.md` for step-by-step instructions
3. Review example files for your use case
4. Test with `index.html` standalone first
5. Check browser console for errors
6. Verify backend logs for Range requests (206 status)

---

**Files location:** `intro/`  
**Documentation:** `README.md`, `IMPLEMENTATION_GUIDE.md`, `IMPLEMENTATION_REPORT.md`  
**Examples:** `backend_example.py`, `mobile_app_example.js`, `service-worker-example.js`  
**Tests:** `test_v1_intro.py`  
**Demo:** `index.html`, `demo.html`
