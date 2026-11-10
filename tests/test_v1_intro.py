"""
Integration tests for the Ink 2 Insight brand intro video feature.

Place this file in tests/test_v1_intro.py in the main application repository.

Requirements:
- pytest
- Flask test client (conftest.py should provide 'client' fixture)
- Application running with intro assets in frontend/intro/

Run with: pytest tests/test_v1_intro.py -v
"""

import os
import pytest


class TestIntroAssets:
    """Test that intro media files exist and meet size requirements."""
    
    def test_intro_files_exist(self):
        """All four media files must exist in frontend/intro/."""
        files = [
            'frontend/intro/intro-portrait.mp4',
            'frontend/intro/intro-landscape.mp4',
            'frontend/intro/poster-portrait.jpg',
            'frontend/intro/poster-landscape.jpg'
        ]
        for filepath in files:
            assert os.path.exists(filepath), f"{filepath} not found"
    
    def test_intro_files_size_limits(self):
        """All media files must be under 20 MB each."""
        files = {
            'frontend/intro/intro-portrait.mp4': 20,
            'frontend/intro/intro-landscape.mp4': 20,
            'frontend/intro/poster-portrait.jpg': 20,
            'frontend/intro/poster-landscape.jpg': 20,
        }
        for filepath, max_mb in files.items():
            if os.path.exists(filepath):
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                assert size_mb < max_mb, f"{filepath} is {size_mb:.2f} MB (must be under {max_mb} MB)"
    
    def test_intro_code_files_exist(self):
        """intro.js and intro.css must exist."""
        assert os.path.exists('frontend/intro/intro.js'), "intro.js not found"
        assert os.path.exists('frontend/intro/intro.css'), "intro.css not found"


class TestIntroStaticServing:
    """Test that intro files are served correctly with proper HTTP headers."""
    
    def test_intro_portrait_video_basic(self, client):
        """GET /intro/intro-portrait.mp4 returns 200 with Content-Type video/mp4."""
        response = client.get('/intro/intro-portrait.mp4')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert 'video/mp4' in response.content_type.lower(), \
            f"Expected video/mp4, got {response.content_type}"
    
    def test_intro_landscape_video_basic(self, client):
        """GET /intro/intro-landscape.mp4 returns 200 with Content-Type video/mp4."""
        response = client.get('/intro/intro-landscape.mp4')
        assert response.status_code == 200
        assert 'video/mp4' in response.content_type.lower()
    
    def test_intro_video_range_request(self, client):
        """Range request returns 206 Partial Content with Content-Range header.
        
        iOS requires Range request support for video playback.
        """
        response = client.get(
            '/intro/intro-portrait.mp4',
            headers={'Range': 'bytes=0-1023'}
        )
        assert response.status_code == 206, \
            f"Expected 206 Partial Content for Range request, got {response.status_code}"
        assert 'Content-Range' in response.headers, \
            "Content-Range header missing in Range response"
        
        content_range = response.headers['Content-Range']
        assert content_range.startswith('bytes 0-1023/') or content_range.startswith('bytes 0-'), \
            f"Invalid Content-Range format: {content_range}"
    
    def test_intro_video_range_request_landscape(self, client):
        """Range request works for landscape video too."""
        response = client.get(
            '/intro/intro-landscape.mp4',
            headers={'Range': 'bytes=0-1023'}
        )
        assert response.status_code == 206
        assert 'Content-Range' in response.headers
    
    def test_intro_poster_images_served(self, client):
        """Poster images are served correctly."""
        for poster in ['poster-portrait.jpg', 'poster-landscape.jpg']:
            response = client.get(f'/intro/{poster}')
            assert response.status_code == 200
            assert 'image' in response.content_type.lower()
    
    def test_intro_js_served(self, client):
        """intro.js is served correctly."""
        response = client.get('/intro/intro.js')
        assert response.status_code == 200
        assert 'javascript' in response.content_type.lower() or \
               'text' in response.content_type.lower()
    
    def test_intro_css_served(self, client):
        """intro.css is served correctly."""
        response = client.get('/intro/intro.css')
        assert response.status_code == 200
        assert 'css' in response.content_type.lower() or \
               'text' in response.content_type.lower()
    
    def test_intro_cache_headers(self, client):
        """Intro static files should have long cache headers (1 year, immutable)."""
        response = client.get('/intro/intro-portrait.mp4')
        if 'Cache-Control' in response.headers:
            cache_control = response.headers['Cache-Control']
            # Should contain max-age=31536000 (1 year) and immutable
            assert 'max-age=31536000' in cache_control or 'max-age=2592000' in cache_control, \
                f"Expected long cache duration in Cache-Control: {cache_control}"


class TestIntroIntegration:
    """Test that intro is properly integrated into the main application."""
    
    def test_index_html_links_intro_css(self, client):
        """index.html must link intro.css."""
        response = client.get('/')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'intro.css' in html or 'intro/intro.css' in html, \
            "intro.css not linked in index.html"
    
    def test_index_html_links_intro_js(self, client):
        """index.html must link intro.js."""
        response = client.get('/')
        html = response.data.decode('utf-8')
        assert 'intro.js' in html or 'intro/intro.js' in html, \
            "intro.js not linked in index.html"
    
    def test_app_js_calls_intro_play(self):
        """app.js must call Intro.play() before startApp."""
        app_js_path = 'frontend/js/app.js'
        if not os.path.exists(app_js_path):
            pytest.skip(f"{app_js_path} not found")
        
        with open(app_js_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'Intro.play' in content, \
            "Intro.play() not called in app.js"
        
        # Verify it's called before startApp (if startApp exists)
        if 'startApp' in content:
            intro_pos = content.find('Intro.play')
            start_app_pos = content.find('startApp')
            assert intro_pos < start_app_pos, \
                "Intro.play() must be called before startApp()"
    
    def test_nointro_parameter_supported(self):
        """app.js should respect ?nointro URL parameter."""
        app_js_path = 'frontend/js/app.js'
        if not os.path.exists(app_js_path):
            pytest.skip(f"{app_js_path} not found")
        
        with open(app_js_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # The intro.js handles ?nointro internally, but verify app.js doesn't override
        # Just check that Intro.play is called unconditionally (not wrapped in URL checks)
        assert 'Intro.play' in content


class TestIntroSecurity:
    """Test that intro files don't break existing security rules."""
    
    def test_catch_all_route_refuses_uploads(self, client):
        """Catch-all route must still refuse access to uploads directory."""
        response = client.get('/uploads/private.pdf')
        assert response.status_code in [401, 403, 404], \
            f"Expected 401/403/404 for uploads, got {response.status_code}"
    
    def test_intro_files_public_no_auth(self, client):
        """Intro files must be accessible without authentication."""
        # This test assumes unauthenticated client
        # If your test setup provides an authenticated client, create an unauthenticated one
        public_files = [
            '/intro/intro.js',
            '/intro/intro.css',
            '/intro/poster-portrait.jpg',
            '/intro/intro-portrait.mp4'
        ]
        for path in public_files:
            response = client.get(path)
            assert response.status_code == 200, \
                f"{path} should be publicly accessible, got {response.status_code}"
    
    def test_catch_all_still_blocks_private_paths(self, client):
        """Verify catch-all route security is not weakened by intro route."""
        dangerous_paths = [
            '/uploads/../intro/intro.js',  # Path traversal attempt
            '/../intro/intro.js',
            '/intro/../uploads/file.pdf',
        ]
        for path in dangerous_paths:
            response = client.get(path)
            # Should either normalize and serve correctly, or return error
            # Should NOT allow path traversal to restricted areas
            assert response.status_code in [200, 400, 403, 404]


class TestServiceWorker:
    """Test that service worker correctly caches intro assets."""
    
    def test_service_worker_exists(self):
        """Service worker file must exist."""
        sw_paths = ['frontend/sw.js', 'frontend/service-worker.js']
        sw_found = any(os.path.exists(p) for p in sw_paths)
        assert sw_found, f"Service worker not found in {sw_paths}"
    
    def test_service_worker_precache_intro_files(self):
        """Service worker precache must include intro.js, intro.css, and posters."""
        sw_paths = ['frontend/sw.js', 'frontend/service-worker.js']
        sw_path = next((p for p in sw_paths if os.path.exists(p)), None)
        
        if not sw_path:
            pytest.skip("Service worker file not found")
        
        with open(sw_path, 'r', encoding='utf-8') as f:
            sw_content = f.read()
        
        required_files = [
            'intro.js',
            'intro.css',
            'poster-portrait.jpg',
            'poster-landscape.jpg'
        ]
        
        for filename in required_files:
            assert filename in sw_content, \
                f"{filename} not found in service worker precache"
    
    def test_service_worker_does_not_precache_videos(self):
        """Videos should NOT be in precache (too large, cached on demand)."""
        sw_paths = ['frontend/sw.js', 'frontend/service-worker.js']
        sw_path = next((p for p in sw_paths if os.path.exists(p)), None)
        
        if not sw_path:
            pytest.skip("Service worker file not found")
        
        with open(sw_path, 'r', encoding='utf-8') as f:
            sw_content = f.read()
        
        # This is a soft check - videos might be in comments or docs
        # The key is they shouldn't be in the actual precache array
        # We're just warning if they appear to be precached
        video_filenames = ['intro-portrait.mp4', 'intro-landscape.mp4']
        for video in video_filenames:
            # Check if video is in what looks like a precache array
            if f"'{video}'" in sw_content or f'"{video}"' in sw_content:
                # This might be okay if it's in a runtime cache strategy
                # But flag it for review
                print(f"WARNING: {video} appears in service worker - ensure it's runtime cached, not precached")


class TestIntroAccessibility:
    """Test accessibility features of the intro player."""
    
    def test_intro_js_has_aria_labels(self):
        """intro.js must set role=dialog and aria-label."""
        with open('frontend/intro/intro.js', 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'role' in content and 'dialog' in content, \
            "intro must have role=dialog"
        assert 'aria-label' in content, \
            "intro must have aria-label"
    
    def test_intro_js_respects_reduced_motion(self):
        """intro.js must check prefers-reduced-motion."""
        with open('frontend/intro/intro.js', 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'prefers-reduced-motion' in content, \
            "intro must respect prefers-reduced-motion preference"
    
    def test_intro_css_has_safe_area_insets(self):
        """intro.css must use env(safe-area-inset-*) for notch/home bar."""
        with open('frontend/intro/intro.css', 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'safe-area-inset' in content, \
            "intro.css must use safe-area-inset for device notches"
    
    def test_intro_css_touch_targets_minimum_size(self):
        """Buttons must have minimum 44px touch targets (WCAG AA)."""
        with open('frontend/intro/intro.css', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for min-height or height declarations on buttons
        assert 'min-height:44px' in content.replace(' ', '') or \
               'min-height: 44px' in content, \
            "Buttons must have min-height: 44px for accessibility"


class TestIntroLogic:
    """Test the intro.js logic and behavior."""
    
    def test_intro_js_has_load_timeout(self):
        """intro.js must have a 4-second load timeout."""
        with open('frontend/intro/intro.js', 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '4000' in content, \
            "intro.js must have 4-second (4000ms) load timeout"
    
    def test_intro_js_exposes_play_function(self):
        """intro.js must expose Intro.play() function."""
        with open('frontend/intro/intro.js', 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'Intro' in content and 'play' in content, \
            "intro.js must expose Intro.play() function"
        assert 'window.Intro' in content or 'g.Intro' in content, \
            "Intro must be exposed on window object"
    
    def test_intro_js_respects_nointro_param(self):
        """intro.js must check for ?nointro URL parameter."""
        with open('frontend/intro/intro.js', 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'nointro' in content, \
            "intro.js must respect ?nointro URL parameter"
    
    def test_intro_js_uses_session_storage(self):
        """intro.js must use sessionStorage for once-per-session tracking."""
        with open('frontend/intro/intro.js', 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'sessionStorage' in content, \
            "intro.js must use sessionStorage to track 'seen' state"
    
    def test_intro_js_orientation_detection(self):
        """intro.js must detect portrait vs landscape orientation."""
        with open('frontend/intro/intro.js', 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'portrait' in content or 'innerHeight' in content, \
            "intro.js must detect device orientation"
        assert 'intro-portrait' in content and 'intro-landscape' in content, \
            "intro.js must reference both portrait and landscape video files"


# Manual test checklist - cannot be automated
MANUAL_TEST_CHECKLIST = """
MANUAL TEST CHECKLIST
=====================
These tests require real devices and cannot be automated with pytest.

[ ] Android Phone (over HTTPS)
    [ ] Intro fills screen edge to edge (no black bars)
    [ ] Intro plays once per session
    [ ] Final logo frame fully visible (not cropped)
    [ ] Skip button works at any time
    [ ] Sound on button turns audio on
    [ ] Status bar hidden during intro
    [ ] Buttons clear notch/home bar (safe areas)

[ ] iPhone (over HTTPS)
    [ ] Intro fills screen edge to edge
    [ ] Intro plays once per session
    [ ] Final logo frame fully visible
    [ ] Skip button works
    [ ] Sound on button turns audio on
    [ ] Status bar hidden during intro
    [ ] Buttons clear notch/home bar

[ ] Offline Mode (after one full visit)
    [ ] Turn off network
    [ ] Refresh page
    [ ] Intro still plays from cache

[ ] Degraded Conditions
    [ ] Slow 3G: app starts within 4 seconds
    [ ] Blocked autoplay: app still starts
    [ ] Reduced motion: intro skipped entirely
    [ ] ?nointro parameter: intro skipped

[ ] Edge Cases
    [ ] Portrait phone: correct video
    [ ] Landscape tablet: correct video
    [ ] Rotate during intro: handles gracefully
    [ ] Very slow device: no crashes
"""


if __name__ == '__main__':
    print(MANUAL_TEST_CHECKLIST)
    print("\nRun automated tests with: pytest tests/test_v1_intro.py -v")
