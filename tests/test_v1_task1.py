"""Tests for V1 Task 1: Remove fake scan and fix phone camera path.

Validates:
1. Server /api/status reports demo_mode accurately based on DEMO_MODE env var.
2. In production (demo off), synthetic sheet generation and demo login are blocked.
3. In demo mode (demo on), demo status is activated.
4. Client markup and code invariants:
   - camera-file-input has accept="image/*" and capture="environment"
   - insecure context banner exists
   - login-demo-btn is identifiable for conditional display
   - captureCurrentPage does not synthesize fake canvas outside demo mode
"""

import os
import re
import pytest
from backend.app import create_app
from backend import database


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_task1.db")
    monkeypatch.delenv("DEMO_MODE", raising=False)
    app = create_app(db_path=db_file)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client, db_file


def test_api_status_default_production_mode(app_client):
    """Test /api/status defaults to demo_mode=False and production_mode=True."""
    client, _ = app_client
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["demo_mode"] is False
    assert data["production_mode"] is True
    assert "PRODUCTION" in data["mode_label"]


def test_api_status_demo_mode_enabled(tmp_path, monkeypatch):
    """Test /api/status reflects demo_mode=True when DEMO_MODE=1."""
    monkeypatch.setenv("DEMO_MODE", "1")
    db_file = str(tmp_path / "test_task1_demo.db")
    app = create_app(db_path=db_file)
    app.config["TESTING"] = True
    with app.test_client() as client:
        res = client.get("/api/status")
        assert res.status_code == 200
        data = res.get_json()
        assert data["demo_mode"] is True
        assert data["production_mode"] is False
        assert "DEMO" in data["mode_label"]


def test_frontend_markup_camera_file_input_and_banners():
    """Verify frontend HTML has environment capture file input and insecure context banner."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(root_dir, "frontend", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Verify camera-file-input with capture=environment
    assert 'id="camera-file-input"' in html
    assert 'capture="environment"' in html
    assert 'accept="image/*"' in html

    # Verify insecure context HTTPS banner exists
    assert 'id="insecure-context-banner"' in html
    assert "HTTPS" in html

    # Verify login-demo-btn ID exists
    assert 'id="login-demo-btn"' in html


def test_frontend_app_js_guards_against_fake_scan():
    """Verify app.js guards generatePageCanvasBlob, loginDemo, and captureCurrentPage."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app_js_path = os.path.join(root_dir, "frontend", "js", "app.js")
    with open(app_js_path, "r", encoding="utf-8") as f:
        app_js = f.read()

    # isDemoMode utility exists and checks demo=1 or SERVER_DEMO_MODE
    assert "export function isDemoMode" in app_js
    assert "urlParams.get('demo') === '1'" in app_js
    assert "SERVER_DEMO_MODE" in app_js

    # loginDemo is guarded by isDemoMode()
    assert re.search(r'function loginDemo\(\)\s*\{\s*if\s*\(!isDemoMode\(\)\)', app_js)

    # generatePageCanvasBlob is guarded by isDemoMode()
    assert re.search(r'function generatePageCanvasBlob\([^)]*\)\s*\{\s*if\s*\(!isDemoMode\(\)\)', app_js)

    # captureCurrentPage branches on isDemoMode() and clicks camera-file-input when demo is off
    assert "camera-file-input" in app_js
    assert "fileInput.click()" in app_js
    assert "Camera inactive" in app_js

    # checkSecureContext checks window.isSecureContext
    assert "export function checkSecureContext" in app_js
    assert "isSecureContext" in app_js
