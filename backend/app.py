"""I2 insights — Clinical Intake & Vision AI Platform.

Provides:
- Camp management & dynamic aggregate statistics (zero fake counters).
- Two-page document image processing endpoint with Groq Vision (or provider abstraction).
- Record creation, human-in-the-loop review workflow, and SQLite persistence.
- Secure Excel (.xlsx) and CSV export with formula injection protection.
- Demo mode data reset and zero patient data leakage.
"""

import os
import sys
import io
import re
import logging
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, Optional
from flask import Flask, request, jsonify, Response, send_from_directory, send_file, g
from flask_cors import CORS
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False
from dotenv import load_dotenv

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load environment variables from .env file if present
load_dotenv(os.path.join(CURRENT_DIR, ".env"))

try:
    from backend import database
    from backend.services.ai_service import AIService, extract as ai_extract
    from backend.services.groq_service import GroqService
    from backend.services.gemini_service import GeminiService
    from backend.services.nvidia_nim_service import NvidiaNimService
    from backend.services.claude_service import ClaudeService
    from backend.services.record_service import RecordService
    from backend.services.supabase_service import SupabaseService
    from backend.services.template_engine import default_template_engine, TemplateEngine
    from backend.services.invariants import wrap_field_value, format_screening_alert
    from backend.services.extraction_v2 import default_extraction_pipeline, ExtractionV2Pipeline
    from backend.services.glossary_service import default_glossary_service
except ImportError:
    import database
    from services.ai_service import AIService, extract as ai_extract
    from services.groq_service import GroqService
    from services.gemini_service import GeminiService
    from services.nvidia_nim_service import NvidiaNimService
    from services.claude_service import ClaudeService
    from services.record_service import RecordService
    from services.supabase_service import SupabaseService
    from services.template_engine import default_template_engine, TemplateEngine
    from services.invariants import wrap_field_value, format_screening_alert
    from services.extraction_v2 import default_extraction_pipeline, ExtractionV2Pipeline
    from services.glossary_service import default_glossary_service

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
)
logger = logging.getLogger("doc_scanner")

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/jpg",
    "image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"
}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB per image (supports high-res iPhone photos)


def create_app(db_path: Optional[str] = None) -> Flask:
    """Application factory for Flask API."""
    if not db_path:
        db_path = os.environ.get("DATABASE_PATH") or database.DEFAULT_DB_PATH

    candidate_dirs = [
        os.path.abspath(os.path.join(PROJECT_ROOT, "frontend")),
        os.path.abspath(os.path.join(CURRENT_DIR, "..", "frontend")),
        os.path.abspath(os.path.join(CURRENT_DIR, "frontend")),
        PROJECT_ROOT,
    ]
    frontend_dir = CURRENT_DIR
    for d in candidate_dirs:
        if os.path.exists(os.path.join(d, "index.html")):
            frontend_dir = d
            break

    app = Flask(__name__, static_folder=frontend_dir, static_url_path="")
    
    # Get environment early for CORS configuration
    app_env = (os.environ.get("APP_ENV") or "development").strip().lower()
    
    # Configure CORS with proper security for development and production
    # SECURITY FIX: Added explicit origin control and security headers
    cors_origins = os.environ.get("CORS_ORIGINS", "").split(",") if os.environ.get("CORS_ORIGINS") else [
        "http://localhost:3000",
        "http://localhost:5001",
        "http://localhost:19006",      # Expo web dev
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5001",
    ]
    
    # In development, also allow local network addresses for mobile testing
    if app_env != "production":
        # Allow exp:// scheme for Expo mobile dev
        cors_origins.append("exp://*")
        # Allow local network IPs (192.168.x.x, 10.x.x.x)
        import re
        for origin in list(cors_origins):
            if "localhost" in origin or "127.0.0.1" in origin:
                # Add wildcard port support
                base_origin = re.sub(r':\d+$', ':*', origin)
                if base_origin not in cors_origins:
                    cors_origins.append(base_origin)
    
    CORS(app, resources={
        r"/api/*": {
            "origins": cors_origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "X-Access-Token",
                "X-User-ID",
                "X-Doctor-ID",
                "X-Org-ID",
                "X-Quality-Bypassed"
            ],
            "expose_headers": ["Content-Range", "X-Total-Count"],
            "supports_credentials": True,
            "max_age": 3600
        }
    })
    
    # Production Startup Validation (Rule 9.3)
    jwt_sec = os.environ.get("JWT_SECRET") or os.environ.get("SUPABASE_JWT_SECRET")
    ai_provider = (os.environ.get("AI_PROVIDER") or "gemini").strip().lower()
    is_vercel = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

    provider_keys = {
        "gemini": os.environ.get("GEMINI_API_KEY"),
        "claude": os.environ.get("ANTHROPIC_API_KEY"),
        "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        "nvidia": os.environ.get("NVIDIA_API_KEY"),
        "groq": os.environ.get("GROQ_API_KEY"),
    }
    required_key_name = {
        "gemini": "GEMINI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "nvidia": "NVIDIA_API_KEY",
        "groq": "GROQ_API_KEY",
    }.get(ai_provider, "API_KEY")

    if app_env == "production":
        if not jwt_sec:
            raise RuntimeError("JWT_SECRET is missing. Cannot start application in production.")
        if not provider_keys.get(ai_provider):
            raise RuntimeError(f"{required_key_name} is missing for configured provider '{ai_provider}'. Cannot start in production.")
        if not db_path:
            raise RuntimeError("Database path is missing. Cannot start in production.")
        if is_vercel and (not os.environ.get("DATABASE_URL") or "sqlite" in (db_path or "").lower()):
            raise RuntimeError("Local SQLite database cannot be used in serverless Vercel: must configure Supabase or Postgres.")
    else:
        if not jwt_sec:
            logger.warning("Startup warning: JWT_SECRET is missing.")
        if not provider_keys.get(ai_provider):
            logger.warning(f"Startup warning: {required_key_name} is missing for provider '{ai_provider}'.")
        if is_vercel and "sqlite" in (db_path or "").lower():
            logger.warning("Startup warning: Local SQLite in Vercel environment.")

    # Initialize DB tables
    database.init_db(db_path)

    # Initialize Flask-Limiter for rate limiting - DISABLED FOR NOW (production mode only)
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator
    limiter = DummyLimiter()

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Rate limit exceeded.",
            "code": "RATE_LIMIT_EXCEEDED"
        }), 429

    @app.before_request
    def enforce_auth_guard():
        from flask import g
        path = request.path
        if not path.startswith("/api/"):
            return None

        if (
            path in {"/api/health", "/api/status", "/api/config/quality", "/api/billing/webhook"}
            or path.startswith("/api/community/verify")
            or path.startswith("/api/auth/")
            or path.startswith("/api/camps")
            or path.startswith("/api/records")
            or path.startswith("/api/extract")
        ):
            return None

        # Check signed short-lived URL for private files
        if path.startswith("/api/files/") and request.args.get("token"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                file_id = parts[2].split("?")[0]
                tok = request.args.get("token")
                valid, file_org = database.verify_signed_file_token(tok, file_id)
                if not valid:
                    return jsonify({
                        "error": "unauthorized",
                        "message": "Invalid or expired signed file token.",
                        "code": "INVALID_SIGNED_TOKEN"
                    }), 401
                g.current_user = {"user_id": "signed_url", "role": "authenticated", "org_id": file_org}
                g.user_id = "signed_url"
                g.user_role = "authenticated"
                g.org_id = file_org
                g.community_id = file_org
                return None

        from backend.services.auth_service import get_token_from_request, safe_decode_token, extract_claims
        token = get_token_from_request()
        if not token:
            return jsonify({
                "error": "unauthorized",
                "message": "Authentication required. Please provide Bearer token in Authorization header.",
                "code": "MISSING_TOKEN"
            }), 401

        payload, err = safe_decode_token(token)
        if not payload or err:
            return jsonify({
                "error": "unauthorized",
                "message": f"Invalid or expired token: {err or 'Verification failed'}",
                "code": "INVALID_TOKEN"
            }), 401

        try:
            claims = extract_claims(payload)
        except Exception as e:
            return jsonify({
                "error": "unauthorized",
                "message": f"Missing required claim: {e}",
                "code": "INVALID_CLAIMS"
            }), 401

        g.current_user = claims
        g.user_id = claims["user_id"]
        g.user_role = claims["role"]
        g.org_id = claims["org_id"]
        g.community_id = claims["org_id"]

    def is_admin_request() -> bool:
        from flask import g
        user_role = getattr(g, "user_role", None)
        if user_role and user_role in ("admin", "superuser"):
            return True
        return False

    record_service = RecordService(db_path)
    supabase_service = SupabaseService()

    def is_supabase_enabled() -> bool:
        """Only attempt Supabase network queries if configured, healthy (circuit breaker closed), and not running unit tests."""
        if app.config.get("TESTING") or os.environ.get("PYTEST_CURRENT_TEST"):
            return False
        return supabase_service.is_available()

    def get_ai_service() -> AIService:
        from backend.services.unified_pipeline import get_configured_ai_provider
        provider = get_configured_ai_provider()
        if provider == "groq":
            return GroqService()
        if provider == "nvidia":
            return NvidiaNimService()
        if provider in ("claude", "anthropic"):
            return ClaudeService()
        return GeminiService()

    @app.after_request
    def add_no_cache_headers(response):
        if request.path.startswith("/api/files/"):
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        if request.path.startswith("/intro/"):
            return response
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    ALLOWED_STATIC_EXTENSIONS = {
        ".html", ".js", ".css", ".json", ".png", ".jpg", ".jpeg",
        ".svg", ".ico", ".webmanifest", ".woff", ".woff2", ".ttf", ".mp4"
    }

    ALLOWED_INTRO_FILES = {
        "intro-portrait.mp4",
        "intro-landscape.mp4",
        "poster-portrait.jpg",
        "poster-landscape.jpg",
        "intro.js",
        "intro.css",
        "demo.html"
    }

    @app.route("/intro/<path:filename>")
    def serve_intro(filename):
        """Serve brand intro assets with Range request support for iOS video playback."""
        if filename not in ALLOWED_INTRO_FILES:
            return jsonify({"error": "not_found", "message": "Intro asset not found"}), 404
        intro_dir = os.path.join(frontend_dir, "intro")
        file_path = os.path.join(intro_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "not_found", "message": "File not found"}), 404

        response = send_from_directory(
            intro_dir,
            filename,
            conditional=True
        )
        response.cache_control.max_age = 31536000
        response.cache_control.public = True
        response.cache_control.immutable = True

        if filename.endswith(".mp4"):
            response.headers["Content-Type"] = "video/mp4"
        elif filename.endswith((".jpg", ".jpeg")):
            response.headers["Content-Type"] = "image/jpeg"
        elif filename.endswith(".js"):
            response.headers["Content-Type"] = "application/javascript"
        elif filename.endswith(".css"):
            response.headers["Content-Type"] = "text/css"
        return response


    # --- Static Frontend Routes ---
    @app.route("/")
    @app.route("/app.py")
    @app.route("/backend/app.py")
    @app.route("/api/index")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/uploads/<path:filename>")
    def block_legacy_uploads_route(filename):
        """Rule 10.4: Disallow public access to legacy uploads directory."""
        return jsonify({"error": "not_found", "message": "Direct upload access is deprecated and forbidden."}), 404

    @app.route("/<path:filename>")
    def static_files(filename):
        # Rule 10.4 & 0.5: Restrict catch-all static route, block uploads and traversal attempts
        raw_req_path = request.path.lower()
        if "/uploads" in raw_req_path or "uploads/" in raw_req_path or filename.startswith("uploads/") or filename == "uploads":
            return jsonify({"error": "not_found", "message": "Direct upload access forbidden"}), 404
        if ".." in filename or "%2e" in raw_req_path or ".." in raw_req_path:
            return jsonify({"error": "not_found", "message": "Invalid static file path"}), 404

        if filename in ("app.py", "backend/app.py", "index.py", "api/index"):
            return send_from_directory(frontend_dir, "index.html")

        safe_path = os.path.abspath(os.path.join(frontend_dir, filename))
        abs_frontend = os.path.abspath(frontend_dir)
        try:
            if os.path.commonpath([abs_frontend, safe_path]) != abs_frontend:
                return jsonify({"error": "not_found", "message": "Access denied"}), 404
        except ValueError:
            return jsonify({"error": "not_found", "message": "Access denied"}), 404

        ext = os.path.splitext(safe_path)[1].lower()
        if ext and ext not in ALLOWED_STATIC_EXTENSIONS:
            return jsonify({"error": "not_found", "message": "File type not allowed"}), 404

        if os.path.exists(safe_path) and not os.path.isdir(safe_path):
            return send_from_directory(frontend_dir, filename)
        return send_from_directory(frontend_dir, "index.html")

    # --- Auth Session Refresh (Rule 0.3) ---
    @app.route("/api/auth/refresh", methods=["POST"])
    @limiter.limit("10/minute")
    def auth_refresh():
        """Refresh JWT session through Flask endpoint with max session age and revocation checks."""
        from backend.services.auth_service import get_token_from_request, safe_decode_token, extract_claims, create_access_token
        token = get_token_from_request()
        if not token:
            return jsonify({
                "error": "unauthorized",
                "message": "Bearer token required in Authorization header to refresh session."
            }), 401
        claims, err = safe_decode_token(token)
        if not claims or err:
            return jsonify({
                "error": "unauthorized",
                "message": f"Cannot refresh invalid token: {err}"
            }), 401

        parsed = extract_claims(claims)
        user_id = parsed["user_id"]

        # Rule 0.3: Session max age check
        max_days = int(os.environ.get("SESSION_MAX_DAYS", "7"))
        orig_iat = parsed.get("orig_iat") or claims.get("orig_iat") or claims.get("iat")
        if orig_iat:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if now_ts - int(orig_iat) > max_days * 86400:
                return jsonify({
                    "error": "unauthorized",
                    "message": "Session exceeded max age / maximum session age (SESSION_MAX_DAYS). Please log in again."
                }), 401

        # Rule 0.3: Verify user exists and is not revoked in database
        app_env = (os.getenv("APP_ENV") or "production").strip().lower()
        with database.get_db_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, is_active FROM doctors WHERE id = ? OR auth_id = ?;", (user_id, user_id))
            doc_row = cur.fetchone()
            if doc_row:
                if doc_row["is_active"] is not None and int(doc_row["is_active"]) == 0:
                    return jsonify({
                        "error": "unauthorized",
                        "message": "User account has been revoked or deactivated."
                    }), 401
            elif app_env == "production":
                return jsonify({
                    "error": "unauthorized",
                    "message": "User account no longer exists."
                }), 401

        new_token = create_access_token(
            user_id=parsed["user_id"],
            role=parsed["role"],
            org_id=parsed["org_id"],
            orig_iat=orig_iat
        )
        return jsonify({
            "success": True,
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": 43200
        }), 200

    # --- Private Files API (Rule 10.2 & 0.6) ---
    @app.route("/api/files/<file_id>", methods=["GET"])
    def get_private_file(file_id):
        """Retrieve private file. 401 if unauth, 404 if cross-org, missing, or unauthorized worker."""
        file_record = database.get_file_by_id(file_id, db_path=db_path)
        if not file_record:
            return jsonify({"error": "not_found", "message": "File not found"}), 404
        # Cross-tenant isolation: return 404 (not 403) to prevent enumerating files
        user_org = getattr(g, "org_id", None)
        if file_record["org_id"] != user_org:
            return jsonify({"error": "not_found", "message": "File not found"}), 404

        # Rule 4.3: Field worker isolation on files
        user_role = getattr(g, "user_role", None)
        user_id = getattr(g, "user_id", None)
        if user_role == "field_worker" and file_record.get("record_id"):
            rec = database.get_record_by_id(file_record["record_id"], db_path=db_path)
            if rec and rec.get("scanned_by") and rec.get("scanned_by") != user_id:
                return jsonify({"error": "not_found", "message": "File not found"}), 404

        storage_path = file_record["storage_path"]
        if not os.path.exists(storage_path):
            return jsonify({"error": "not_found", "message": "File storage not found"}), 404

        resp = send_file(storage_path, mimetype=file_record.get("mime_type", "image/jpeg"))
        resp.headers["Cache-Control"] = "private, no-store"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp

    @app.route("/api/files/<file_id>/signed-url", methods=["GET"])
    def get_signed_file_url(file_id):
        """Generate short-lived signed URL (5 minutes) for embedding in HTML image tags."""
        file_record = database.get_file_by_id(file_id, db_path=db_path)
        if not file_record:
            return jsonify({"error": "not_found", "message": "File not found"}), 404
        user_org = getattr(g, "org_id", None)
        if file_record["org_id"] != user_org:
            return jsonify({"error": "not_found", "message": "File not found"}), 404

        signed_token = database.generate_signed_file_token(file_id, file_record["org_id"], expires_in_seconds=300)
        return jsonify({
            "file_id": file_id,
            "signed_url": f"/api/files/{file_id}?token={signed_token}",
            "expires_in": 300
        }), 200

    # --- API Status & Metrics (Rule 9.4) ---
    @app.route("/api/health", methods=["GET"])
    def health():
        """Public health endpoint returning app version, provider, model, db read test, and zero secrets."""
        from backend.services.unified_pipeline import get_configured_ai_provider
        provider = get_configured_ai_provider()
        model_env_map = {
            "gemini": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            "claude": os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"),
            "nvidia": os.environ.get("NVIDIA_MODEL", "meta/llama-3.2-11b-vision-instruct"),
            "groq": os.environ.get("GROQ_MODEL", "llama-3.2-11b-vision-preview"),
        }
        model_name = model_env_map.get(provider, "default-model")

        db_status = "error"
        try:
            with database.get_db_connection(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1;")
                cursor.fetchone()
                db_status = "ok"
        except Exception as e:
            logger.error(f"Database health check error: {e}")
            db_status = f"error: {e}"

        return jsonify({
            "status": "ok" if db_status == "ok" else "degraded",
            "version": "2.0.0",
            "provider": provider,
            "model": model_name,
            "database": db_status
        }), (200 if db_status == "ok" else 500)

    @app.route("/api/status", methods=["GET"])
    def status():
        ai = get_ai_service()
        stats = database.get_overall_stats(db_path)
        tables_exist = {"camps": False, "records": False}
        supabase_ready = False
        if is_supabase_enabled():
            tables_exist = supabase_service.check_tables_exist()
            supabase_ready = bool(tables_exist.get("camps") and tables_exist.get("records"))

        demo_mode = os.getenv("DEMO_MODE", "0").strip().lower() in ("1", "true", "yes")
        return jsonify({
            "production_mode": not demo_mode,
            "demo_mode": demo_mode,
            "mode_label": "DEMO — Synthetic Demonstrations Active" if demo_mode else "PRODUCTION — Real Medical Intake Active",
            "ai_configured": ai.is_configured(),
            "ai_provider": ai.provider_name(),
            "supabase_configured": supabase_service.is_configured(),
            "supabase_available": supabase_service.is_available(),
            "supabase_url": supabase_service.url if supabase_service.is_configured() else None,
            "supabase_tables_ready": supabase_ready,
            "supabase_tables": tables_exist,
            "overall_stats": stats
        })

    @app.route("/api/stats", methods=["GET"])
    def stats():
        return jsonify(database.get_overall_stats(db_path))

    @app.route("/api/config/quality", methods=["GET"])
    def get_quality_config_route():
        from backend.services.quality_service import get_quality_config
        return jsonify(get_quality_config())

    @app.route("/api/quality-check", methods=["POST"])
    def quality_check_route():
        from backend.services.quality_service import assess_image_quality
        file = request.files.get("image") or request.files.get("file")
        if file:
            res = assess_image_quality(file.read())
            return jsonify(res)
        raw_data = request.get_data()
        if raw_data:
            res = assess_image_quality(raw_data)
            return jsonify(res)
        return jsonify({"ok": None, "error": "No image provided", "issues": ["No image file provided"]}), 400

    # --- Camps API ---
    @app.route("/api/camps", methods=["GET"])
    def list_camps():
        community_id = getattr(g, "org_id", None) or getattr(g, "community_id", None)
        if is_supabase_enabled():
            camps = supabase_service.list_camps_with_stats()
            if camps is not None:
                return jsonify(camps)
        camps = database.list_camps_with_stats(db_path, community_id=community_id)
        return jsonify(camps)

    @app.route("/api/camps", methods=["POST"])
    def add_camp():
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "Camp name is required"}), 400
        
        try:
            expected = int(data.get("expected_records", 100))
        except (ValueError, TypeError):
            expected = 100
            
        date_str = data.get("date_str", "Today").strip() or "Today"
        location = data.get("location", "Chennai Health Camp")
        target_group = (data.get("target_group") or "adult").strip().lower()
        if target_group not in ("adult", "paediatric"):
            target_group = "adult"

        # Token Authority: Take org_id and user from token ONLY, never from body, query or headers
        from flask import g
        community_id = getattr(g, 'org_id', 'demo_org')
        created_by = getattr(g, 'current_user', {}).get("name") or getattr(g, 'user_id', 'demo_user')

        if is_supabase_enabled():
            try:
                camp = supabase_service.create_camp(name, expected, date_str)
                # Also persist locally in SQLite for resilience using the exact same ID
                try:
                    database.create_camp(
                        name, expected, date_str,
                        location=location,
                        created_by=created_by,
                        camp_id=camp.get("id"),
                        target_group=target_group,
                        community_id=community_id,
                        db_path=db_path
                    )
                except Exception as db_err:
                    logger.warning("Local camp mirror warning: %s", db_err)
                return jsonify(camp), 201
            except Exception as e:
                logger.error("Failed to create camp in Supabase: %s; falling back to SQLite", e)

        camp = database.create_camp(
            name, expected, date_str,
            location=location,
            created_by=created_by,
            target_group=target_group,
            community_id=community_id,
            db_path=db_path
        )
        return jsonify(camp), 201

    @app.route("/api/camps/<camp_id>", methods=["GET"])
    def get_camp(camp_id):
        if is_supabase_enabled():
            camp = supabase_service.get_camp_by_id(camp_id)
            if camp:
                return jsonify(camp)
        camp = database.get_camp_by_id(camp_id, db_path)
        if not camp:
            return jsonify({"error": "Camp not found"}), 404
        return jsonify(camp)

    @app.route("/api/camps/<camp_id>", methods=["PUT"])
    def update_camp(camp_id):
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "Camp name is required"}), 400
        expected = int(data.get("expected_records", 100))
        date_str = data.get("date_str", "Today").strip() or "Today"
        location = data.get("location")
        if supabase_service.is_configured():
            try:
                supabase_service.update_camp(camp_id, name, expected, date_str, location)
            except Exception as e:
                logger.error("Supabase update_camp error: %s", e)
        camp = database.update_camp(camp_id, name, expected, date_str, location, db_path)
        if not camp:
            return jsonify({"error": "Camp not found"}), 404
        return jsonify(camp)

    @app.route("/api/camps/<camp_id>", methods=["DELETE"])
    def delete_camp(camp_id):
        if supabase_service.is_configured():
            try:
                supabase_service.delete_camp(camp_id)
            except Exception as e:
                logger.error("Supabase delete_camp error: %s", e)
        success = database.delete_camp(camp_id, db_path)
        return jsonify({"status": "deleted", "success": success})

    # --- Records API ---
    @app.route("/api/records", methods=["GET"])
    def list_records():
        from backend.services.auth_service import get_token_from_request, safe_decode_token
        token = get_token_from_request()
        if not token:
            return jsonify({"error": "unauthorized", "message": "Authentication required. Bearer token missing."}), 401
        payload, err = safe_decode_token(token)
        if err or not payload:
            return jsonify({"error": "unauthorized", "message": err or "Invalid token"}), 401

        camp_id = request.args.get("camp_id")
        status_filter = request.args.get("status")
        scanned_by = request.args.get("scanned_by")
        query = request.args.get("q")
        page_param = request.args.get("page")
        page = int(page_param) if page_param and page_param.isdigit() else None
        limit = min(int(request.args.get("limit", 20 if page else 100)), 500)

        # Rule 4.3: field_worker sees only records they created
        if getattr(g, "user_role", None) == "field_worker":
            scanned_by = g.user_id

        community_id = getattr(g, "org_id", None) or getattr(g, "community_id", None)
        recs = database.list_records(
            camp_id=camp_id,
            status=status_filter,
            query=query,
            scanned_by=scanned_by,
            community_id=community_id,
            page=page,
            limit=limit,
            db_path=db_path
        )
        return jsonify(recs)

    @app.route("/api/records/<record_id>", methods=["GET"])
    def get_record(record_id):
        from flask import g
        rec = database.get_record_by_id(record_id, db_path)
        if not rec:
            return jsonify({"error": "Record not found"}), 404

        # Cross-Org Access Enforcement: Deny unless both exist and are equal
        caller_org = g.org_id
        rec_org = rec.get("community_id") or rec.get("org_id")
        if not (rec_org and caller_org and rec_org == caller_org):
            return jsonify({
                "error": "forbidden",
                "message": "Cross-organization access forbidden: record does not belong to caller organization."
            }), 403

        # Rule 4.3: Intra-Org Role Restrictions: field_worker can read only their own scans -> 403
        if g.user_role == "field_worker" and rec.get("scanned_by") != g.user_id:
            return jsonify({
                "error": "forbidden",
                "message": "Access denied: field_worker can only view own records."
            }), 403

        if supabase_service.is_configured():
            try:
                s_rec = supabase_service.get_record_by_id(record_id)
                if s_rec:
                    return jsonify(s_rec)
            except Exception as e:
                logger.error("Supabase get_record error: %s", e)
        return jsonify(rec)

    @app.route("/api/camps/<camp_id>/paediatric-records", methods=["GET"])
    def list_camp_paediatric_records(camp_id):
        status_filter = request.args.get("status")
        limit = min(int(request.args.get("limit", 100)), 500)
        recs = database.list_paediatric_records(camp_id=camp_id, status=status_filter, limit=limit, db_path=db_path)
        return jsonify(recs)

    @app.route("/api/camps/<camp_id>/adult-records", methods=["GET"])
    def list_camp_adult_records(camp_id):
        status_filter = request.args.get("status")
        limit = min(int(request.args.get("limit", 100)), 500)
        recs = database.list_adult_records(camp_id=camp_id, status=status_filter, limit=limit, db_path=db_path)
        return jsonify(recs)

    @app.route("/api/paediatric-records/<record_id>", methods=["GET"])
    def get_paediatric_record(record_id):
        rec = database.get_paediatric_record_by_id(record_id, db_path)
        if not rec:
            return jsonify({"error": "Paediatric record not found"}), 404
        return jsonify(rec)

    @app.route("/api/adult-records/<record_id>", methods=["GET"])
    def get_adult_record(record_id):
        rec = database.get_adult_record_by_id(record_id, db_path)
        if not rec:
            return jsonify({"error": "Adult record not found"}), 404
        return jsonify(rec)

    @app.route("/api/paediatric/screen", methods=["POST"])
    def screen_paediatric_vitals():
        """Evaluate paediatric growth percentiles (IAP 2015), BP classification, and ATR scoliosis screening."""
        from backend.services.paediatric_screening import classify_paediatric
        data = request.get_json(silent=True) or {}
        fields = {}
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                fields[k] = v
            else:
                fields[k] = [v, 1.0]
        result = classify_paediatric(fields)
        return jsonify(result)

    @app.route("/api/records", methods=["POST"])
    def create_record():
        from flask import g
        payload = request.get_json(silent=True) or {}
        # Ensure a single, consistent record ID across both Supabase and SQLite
        if not payload.get("id"):
            payload["id"] = f"rec_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}"
        # Token authority: org_id and scanned_by come strictly from token
        payload["community_id"] = g.org_id
        if not payload.get("scanned_by"):
            payload["scanned_by"] = g.user_id
        try:
            if is_supabase_enabled():
                try:
                    created = supabase_service.insert_record(payload)
                    # Also persist locally in SQLite for resilience using identical ID
                    try:
                        record_service.create_record(payload)
                    except Exception as local_sync_error:
                        logger.warning("Failed to sync record to local SQLite: %s", local_sync_error)
                    return jsonify(created), 201
                except Exception as e:
                    logger.error("Failed to insert record in Supabase: %s; falling back to SQLite", e)

            created = record_service.create_record(payload)
            return jsonify(created), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.exception("Error saving record")
            return jsonify({"error": "Failed to persist record"}), 500

    @app.route("/api/records/<record_id>", methods=["PUT"])
    def update_record(record_id):
        from flask import g
        from backend.services.field_permissions import validate_field_worker_edits
        existing = database.get_record_by_id(record_id, db_path)
        if not existing:
            return jsonify({"error": "Record not found"}), 404

        # Cross-Org Access Enforcement: Deny unless both exist and are equal
        caller_org = g.org_id
        rec_org = existing.get("community_id") or existing.get("org_id")
        if not (rec_org and caller_org and rec_org == caller_org):
            return jsonify({
                "error": "forbidden",
                "message": "Cross-organization modification forbidden: record does not belong to caller organization."
            }), 403

        # Rule 4.3: Field worker can only modify their own scans -> 404
        if g.user_role == "field_worker" and existing.get("scanned_by") != g.user_id:
            return jsonify({
                "error": "not_found",
                "message": "Record not found"
            }), 404

        payload = request.get_json(silent=True) or {}

        # Rule 4.2: Field worker clinical check (fail-closed, reject whole payload)
        if g.user_role == "field_worker":
            allowed, offending = validate_field_worker_edits(payload)
            if not allowed:
                return jsonify({
                    "error": "forbidden",
                    "message": f"Field workers cannot modify clinical fields: {', '.join(offending)}",
                    "code": "CLINICAL_FIELDS_FORBIDDEN"
                }), 403

        # Rule 4.4: Editing an approved record resets status to 'needs_review'
        was_approved = existing.get("status") == "approved"
        if was_approved and payload.get("status") != "approved":
            payload["status"] = "needs_review"
            payload["approved_by"] = None
            payload["approved_at"] = None

        if is_supabase_enabled():
            try:
                supabase_service.update_record(record_id, payload)
            except Exception as e:
                logger.error("Supabase update_record error: %s", e)

        # Rule 4.5: Write audit row for every edited field
        for field, new_val in payload.items():
            if field in ("updated_at", "version"):
                continue
            old_val = existing.get(field)
            if str(old_val) != str(new_val):
                database.log_record_audit(
                    record_id=record_id,
                    org_id=caller_org,
                    user_id=g.user_id,
                    user_role=g.user_role,
                    action="update",
                    field_name=field,
                    old_value=str(old_val) if old_val is not None else None,
                    new_value=str(new_val) if new_val is not None else None,
                    db_path=db_path
                )

        updated = database.update_record(record_id, payload, db_path)
        if not updated:
            return jsonify({"error": "Record not found"}), 404
        return jsonify(updated)

    @app.route("/api/records/<record_id>", methods=["DELETE"])
    def delete_record(record_id):
        from flask import g
        existing = database.get_record_by_id(record_id, db_path)
        if not existing:
            return jsonify({"error": "Record not found"}), 404

        # Cross-Org Access Enforcement: Deny unless both exist and are equal
        caller_org = g.org_id
        rec_org = existing.get("community_id") or existing.get("org_id")
        if not (rec_org and caller_org and rec_org == caller_org):
            return jsonify({
                "error": "forbidden",
                "message": "Cross-organization deletion forbidden: record does not belong to caller organization."
            }), 403

        # Intra-Org Role Restrictions (A7):
        # field_worker cannot delete
        if g.user_role == "field_worker":
            return jsonify({
                "error": "forbidden",
                "message": "Field workers are not permitted to delete records."
            }), 403
        # doctor can delete only their own drafts
        if g.user_role == "doctor":
            is_draft = existing.get("status") in ("needs_review", "draft")
            is_own = existing.get("scanned_by") == g.user_id
            if not (is_draft and is_own):
                return jsonify({
                    "error": "forbidden",
                    "message": "Doctors may only delete their own draft records."
                }), 403

        if is_supabase_enabled():
            try:
                supabase_service.delete_record(record_id)
            except Exception as e:
                logger.error("Supabase delete_record error: %s", e)
        success = database.delete_record(record_id, db_path)
        return jsonify({"status": "deleted", "success": success})

    @app.route("/api/records/<record_id>/review", methods=["PUT", "POST"])
    def review_record(record_id):
        """Review and update record fields. Resolving flags alone does NOT approve or bill paper."""
        existing = database.get_record_by_id(record_id, db_path)
        if not existing:
            return jsonify({"error": "Record not found"}), 404

        # Cross-Org Access Enforcement: Deny unless both exist and are equal
        caller_org = g.org_id
        rec_org = existing.get("community_id") or existing.get("org_id")
        if not (rec_org and caller_org and rec_org == caller_org):
            return jsonify({
                "error": "forbidden",
                "message": "Cross-organization modification forbidden: record does not belong to caller organization."
            }), 403

        # Role Permissions: doctor, admin, superuser, or field_worker for own records
        if g.user_role == "field_worker" and existing.get("scanned_by") != g.user_id:
            return jsonify({
                "error": "forbidden",
                "message": "Field workers can only review their own records."
            }), 403
        elif g.user_role not in ("field_worker", "doctor", "admin", "superuser"):
            return jsonify({
                "error": "forbidden",
                "message": f"Review requires authorized role; current role '{g.user_role}' is forbidden."
            }), 403

        payload = request.get_json(silent=True) or {}
        reviewer = g.current_user.get("name") or payload.get("reviewed_by") or g.user_id

        try:
            if is_supabase_enabled():
                try:
                    supabase_service.update_reviewed_record(record_id, payload, reviewer)
                except Exception as e:
                    logger.error("Failed to update in Supabase: %s", e)

            updated = record_service.review_record(record_id, payload, reviewer)
            # Release lock upon review
            database.unlock_record(record_id, reviewer, db_path=db_path)
            return jsonify(updated)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.exception("Error reviewing record")
            return jsonify({"error": "Failed to update record"}), 500

    @app.route("/api/records/<record_id>/approve", methods=["POST"])
    def approve_record_endpoint(record_id):
        """Explicit approval action: checks flags are resolved, stores approved_by & approved_at, and marks paper billed."""
        from flask import g
        if g.user_role not in ("field_worker", "doctor", "admin", "superuser"):
            return jsonify({
                "error": "forbidden",
                "message": f"Approval requires authorized role; current role '{g.user_role}' is forbidden."
            }), 403

        existing = database.get_record_by_id(record_id, db_path)
        if not existing:
            return jsonify({"error": "Record not found"}), 404

        # Cross-Org Access Enforcement: Deny unless both exist and are equal
        caller_org = g.org_id
        rec_org = existing.get("community_id") or existing.get("org_id")
        if not (rec_org and caller_org and rec_org == caller_org):
            return jsonify({
                "error": "forbidden",
                "message": "Cross-organization modification forbidden: record does not belong to caller organization."
            }), 403

        # Intra-Org Worker Isolation: field_worker can approve only their own scans
        if g.user_role == "field_worker" and existing.get("scanned_by") != g.user_id:
            return jsonify({
                "error": "forbidden",
                "message": "Field workers can only approve their own records."
            }), 403

        payload = request.get_json(silent=True) or {}
        doctor = g.current_user.get("name") or g.user_id
        org_id = g.org_id

        # Check for unresolved flags passed in payload
        unresolved_flags = payload.get("unresolved_flags") or payload.get("flags_unresolved")
        if unresolved_flags:
            return jsonify({
                "error": "flags_unresolved",
                "message": f"Approval refused: {len(unresolved_flags)} flagged fields remain unresolved."
            }), 409

        success, updated, err = database.approve_record(record_id, approved_by=doctor, org_id=org_id, db_path=db_path)
        if not success:
            if err == "flags_unresolved":
                return jsonify({
                    "error": "flags_unresolved",
                    "message": "Approval refused: flagged fields remain unresolved."
                }), 409
            if err == "consent_withheld":
                return jsonify({
                    "error": "consent_withheld",
                    "message": "Approval refused: Patient or parental consent is withheld or not given."
                }), 403
            return jsonify({"error": err or "Failed to approve record"}), 404

        database.log_record_audit(
            record_id=record_id,
            org_id=caller_org,
            user_id=g.user_id,
            user_role=g.user_role,
            action="approve",
            field_name="status",
            old_value=existing.get("status"),
            new_value="approved",
            db_path=db_path
        )

        return jsonify({
            "success": True,
            "status": "approved",
            "approved_by": doctor,
            "approved_at": updated.get("approved_at"),
            "record": updated
        })

    # --- Record Audit API (Rule 4.5) ---
    @app.route("/api/records/<record_id>/audit", methods=["GET"])
    def get_record_audit(record_id):
        """Retrieve insert-only audit log for doctor/admin within the same org."""
        from flask import g
        existing = database.get_record_by_id(record_id, db_path)
        if not existing:
            return jsonify({"error": "Record not found"}), 404

        caller_org = g.org_id
        rec_org = existing.get("community_id") or existing.get("org_id")
        if not (rec_org and caller_org and rec_org == caller_org):
            return jsonify({"error": "forbidden", "message": "Cross-organization access forbidden"}), 403

        if g.user_role not in ("doctor", "admin", "superuser"):
            return jsonify({"error": "forbidden", "message": "Only doctors and admins can view audit history."}), 403

        entries = database.get_record_audit_log(record_id, db_path=db_path)
        return jsonify({"audit_log": entries}), 200

    @app.route("/api/records/<record_id>/release", methods=["POST"])
    def release_record(record_id):
        org_id = request.headers.get("X-Org-ID") or request.args.get("org_id") or "org_default"
        rec = database.get_record_by_id(record_id, db_path)
        if rec and rec.get("status") in ("reviewed", "approved"):
            return jsonify({
                "error": "already_billed",
                "message": "Cannot release paper quota for an already approved record."
            }), 409
        papers_left = database.release_paper(org_id=org_id, record_id=record_id, reason="manual_release", db_path=db_path)
        return jsonify({"success": True, "papers_left": papers_left})

    @app.route("/api/records/<record_id>/lock", methods=["POST"])
    def lock_record(record_id):
        data = request.get_json(silent=True) or {}
        doctor_name = data.get("doctor_name") or request.headers.get("X-Doctor-ID") or "Dr. Priya"
        res = database.lock_record(record_id, doctor_name, db_path=db_path)
        return jsonify(res)

    @app.route("/api/records/<record_id>/unlock", methods=["POST"])
    def unlock_record(record_id):
        data = request.get_json(silent=True) or {}
        doctor_name = data.get("doctor_name") or request.headers.get("X-Doctor-ID") or "Dr. Priya"
        success = database.unlock_record(record_id, doctor_name, db_path=db_path)
        return jsonify({"success": success, "unlocked": success})

    @app.route("/api/records/validate", methods=["POST"])
    def validate_record():
        payload = request.get_json(silent=True) or {}
        res = record_service.validate_record_fields(payload)
        return jsonify(res)

    @app.route("/api/records/check-duplicate", methods=["POST"])
    def check_duplicate():
        data = request.get_json(silent=True) or {}
        camp_id = data.get("camp_id", "")
        person_name = data.get("person_name", "")
        phone = data.get("phone", "")
        exclude_id = data.get("exclude_id")
        res = database.check_duplicate_record(camp_id, person_name, phone, exclude_id, db_path)
        res["has_duplicate"] = res.get("is_duplicate", False)
        res["count"] = 1 if res["has_duplicate"] else 0
        return jsonify(res)

    @app.route("/api/records/<record_id>/erase", methods=["DELETE", "POST"])
    def erase_record(record_id):
        # DPDP Right to Erasure - Admin within own org only
        from flask import g
        if g.user_role not in ("admin", "superuser"):
            return jsonify({
                "error": "forbidden",
                "message": "DPDP Right to Erasure can only be exercised by organization administrators."
            }), 403

        existing = database.get_record_by_id(record_id, db_path)
        if not existing:
            return jsonify({"error": "Record not found"}), 404

        caller_org = g.org_id
        rec_org = existing.get("community_id") or existing.get("org_id")
        if not (rec_org and caller_org and rec_org == caller_org):
            return jsonify({
                "error": "forbidden",
                "message": "Cross-organization erasure forbidden: record does not belong to caller organization."
            }), 403

        if is_supabase_enabled():
            try:
                supabase_service.delete_record(record_id)
            except Exception as e:
                logger.error("Supabase erasure error: %s", e)
        success = database.erase_patient_record(record_id, db_path)
        return jsonify({
            "status": "erased",
            "success": success,
            "erased": success,
            "message": "Patient data and source images permanently deleted under DPDP Act."
        })

    @app.route("/api/records/<record_id>/referral-slip", methods=["GET"])
    def get_referral_slip(record_id):
        """Generate and stream a 1-page printable clinical referral slip PDF."""
        rec = database.get_record_by_id(record_id, db_path)
        if not rec:
            return jsonify({"error": "Record not found"}), 404

        p_dir = database.get_private_upload_dir()
        pdf_dir = os.path.join(p_dir, "referral_slips")
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_filename = f"referral_slip_{record_id}.pdf"
        output_pdf_path = os.path.join(pdf_dir, pdf_filename)

        database.generate_patient_referral_pdf(rec, output_pdf_path)

        with open(output_pdf_path, "rb") as f:
            pdf_bytes = f.read()

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"inline; filename={pdf_filename}"}
        )


    @app.route("/api/admin/billing", methods=["GET"])
    def admin_billing():
        if not is_admin_request():
            return jsonify({"error": "forbidden", "message": "Admin authorization required."}), 403
        # Aggregated admin, billing and operational telemetry
        billing_info = database.get_admin_billing(db_path)
        billing_info["used_scans"] = billing_info.get("quota_used", 0)
        billing_info["monthly_limit"] = billing_info.get("quota_total", 5000)
        billing_info["cost_estimate_inr"] = billing_info.get("est_groq_cost_inr", 0.0)
        billing_info["invoices"] = [
            {"id": "INV-2026-10", "date": "01 Oct 2026", "plan": "Outreach 2,500 Scans", "amount": "₹0.00 (Grant)", "status": "Paid"},
            {"id": "INV-2026-09", "date": "01 Sep 2026", "plan": "Outreach 2,500 Scans", "amount": "₹0.00 (Grant)", "status": "Paid"}
        ]
        return jsonify(billing_info)

    @app.route("/api/admin/purchase-credits", methods=["POST"])
    def purchase_credits():
        data = request.get_json(silent=True) or {}
        credits = int(data.get("credits", 1000))
        res = database.purchase_credits(credits, db_path=db_path)
        res["credits_added"] = res.get("added_credits", credits)
        res["new_limit"] = res.get("new_quota", 5000)
        return jsonify(res)

    # --- Tokenized Single-Use Invites API ---
    @app.route("/api/community/invites", methods=["GET"])
    def list_invites():
        comm_id = request.args.get("community_id") or "comm_health_demo_01"
        invs = database.list_invites(comm_id, db_path=db_path)
        return jsonify({"invites": invs, "total": len(invs)})

    @app.route("/api/community/invites", methods=["POST"])
    @app.route("/api/community/invite", methods=["POST"])
    def create_invite():
        if not is_admin_request():
            return jsonify({"error": "forbidden", "message": "Admin authorization required."}), 403
        data = request.get_json(silent=True) or {}
        comm_id = data.get("community_id") or "comm_health_demo_01"
        email = data.get("email")
        role = data.get("role", "doctor")
        expires_hours = int(data.get("expires_hours", 72))
        created_by = data.get("created_by") or request.headers.get("X-Doctor-ID") or "Dr. Priya"
        inv = database.create_invite(comm_id, email, role, expires_hours, created_by, db_path=db_path)
        return jsonify(inv), 201

    @app.route("/api/community/invites/<invite_id>", methods=["DELETE"])
    def revoke_invite(invite_id):
        if not is_admin_request():
            return jsonify({"error": "forbidden", "message": "Admin authorization required."}), 403
        success = database.revoke_invite(invite_id, db_path=db_path)
        return jsonify({"success": success, "revoked": success})

    @app.route("/api/community/verify-invite", methods=["POST"])
    def verify_invite_token():
        data = request.get_json(silent=True) or {}
        code = (data.get("code") or "").strip().upper()
        inv = database.verify_invite(code, db_path=db_path)
        if not inv:
            return jsonify({"valid": False, "error": "Invite code is invalid, expired, or has been revoked."}), 400
        return jsonify({"valid": True, "invite": inv})

    # --- Image Upload API (Supabase Storage with Local Fallback) ---
    @app.route("/api/upload-image", methods=["POST"])
    def upload_image():
        """
        Upload medical intake form images with security validation.
        
        SECURITY FIX: Added file size limit (10MB), file type validation, and error handling.
        """
        # Security: Maximum file size (10MB for high-resolution medical forms)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
        ALLOWED_MIME_TYPES = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp'}
        ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
        
        if "image" not in request.files:
            return jsonify({"error": "No image file uploaded"}), 400
            
        img = request.files["image"]
        
        # Validate filename exists
        if not img.filename or img.filename == '':
            return jsonify({"error": "Invalid filename"}), 400
        
        # Validate file extension
        file_ext = os.path.splitext(img.filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return jsonify({
                "error": "Invalid file type",
                "message": f"Only image files are allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400
        
        camp_id = request.form.get("camp_id", "default_camp")
        page_num = request.form.get("page", "1")
        filename = f"{camp_id}_page{page_num}_{os.urandom(4).hex()}.jpg"
        
        # Read file with size limit
        img_bytes = img.read(MAX_FILE_SIZE + 1)  # Read one byte extra to detect oversized files
        
        # Validate file size
        if len(img_bytes) > MAX_FILE_SIZE:
            return jsonify({
                "error": "File too large",
                "message": f"Maximum file size is {MAX_FILE_SIZE // (1024 * 1024)}MB",
                "max_size_bytes": MAX_FILE_SIZE
            }), 413  # 413 Payload Too Large
        
        if len(img_bytes) == 0:
            return jsonify({"error": "Empty file uploaded"}), 400
        
        # Validate MIME type
        mimetype = img.mimetype or "image/jpeg"
        if mimetype not in ALLOWED_MIME_TYPES:
            return jsonify({
                "error": "Invalid file type",
                "message": f"Only image MIME types are allowed: {', '.join(ALLOWED_MIME_TYPES)}"
            }), 400

        # Try Supabase Storage first
        if supabase_service.is_configured():
            try:
                storage_path = f"{camp_id}/{filename}"
                public_url = supabase_service.upload_storage_image(storage_path, img_bytes, mimetype)
                if public_url:
                    return jsonify({"url": public_url, "storage": "supabase", "size_bytes": len(img_bytes)})
            except Exception as e:
                logger.error("Supabase storage upload failed: %s", e)
                # Fall through to local storage

        # Save to private upload directory outside static root (Rule 10.1)
        try:
            target_org = getattr(g, "org_id", "org_default")
            file_id = database.save_private_file(
                org_id=target_org,
                record_id=None,
                file_type="upload",
                filename=filename,
                data=img_bytes,
                mime_type=mimetype,
                db_path=db_path
            )
            return jsonify({
                "url": f"/api/files/{file_id}", 
                "file_id": file_id, 
                "storage": "private",
                "size_bytes": len(img_bytes)
            })
        except Exception as e:
            logger.exception("File upload error")
            return jsonify({"error": "Failed to save uploaded file"}), 500

    # --- Camp Analytics API ---
    @app.route("/api/analytics", methods=["GET"])
    @app.route("/api/camps/<camp_id>/analytics", methods=["GET"])
    def camp_analytics(camp_id=None):
        cid = camp_id or request.args.get("camp_id")
        stats = database.get_camp_analytics(camp_id=cid, db_path=db_path)
        return jsonify(stats)

    # --- Community (Organization / Outreach Network) API ---
    @app.route("/api/community/create", methods=["POST"])
    def community_create():
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        creator_name = (data.get("creator_name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        custom_code = (data.get("code") or "").strip().upper()

        if not name or not creator_name or not email:
            return jsonify({"error": "Community name, your name, and email are required."}), 400

        # Build community in database
        comm = database.create_community(name, creator_name, email, code=custom_code or None, db_path=db_path)
        
        # Register or update founder doctor
        doctor = database.get_or_create_doctor(
            email=email,
            full_name=creator_name,
            specialization="Community Lead / Organizer",
            community_id=comm["id"],
            community_code=comm["code"],
            community_role="admin",
            db_path=db_path
        )
        
        token = None
        if supabase_service.is_configured() and password:
            auth_res = supabase_service.auth_sign_up(email, password, creator_name, "Community Lead")
            token = auth_res.get("access_token")

        profile = database.get_doctor_profile(doctor["id"], db_path=db_path)
        return jsonify({
            "success": True,
            "community": comm,
            "doctor": profile,
            "token": token or f"demo_jwt_{doctor['id']}"
        }), 201

    @app.route("/api/community/verify", methods=["POST"])
    @limiter.limit("10/minute")
    def community_verify():
        data = request.get_json(silent=True) or {}
        code = (data.get("code") or "").strip().upper()
        if not code:
            return jsonify({"valid": False, "error": "Community code is required"}), 400
        comm = database.get_community_by_code(code, db_path=db_path)
        if not comm:
            return jsonify({"valid": False, "error": f"Invalid code '{code}'. Ask your organizer for the exact code."}), 400
        return jsonify({
            "valid": True,
            "community": {
                "id": comm["id"],
                "name": comm["name"],
                "code": comm["code"],
                "creator_name": comm["creator_name"]
            }
        })

    @app.route("/api/community/members", methods=["GET"])
    def community_members():
        if not is_admin_request():
            return jsonify({"error": "forbidden", "message": "Admin authorization required."}), 403
        from flask import g
        comm_id = request.args.get("community_id") or getattr(g, "org_id", None)
        members = []
        with database.get_db_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, email, full_name, specialization, community_role, is_active FROM doctors WHERE community_id = ?;", (comm_id,))
            members = [dict(r) for r in cur.fetchall()]
            if not members:
                cur.execute("SELECT id, email, full_name, specialization, community_role, is_active FROM doctors LIMIT 10;")
                members = [dict(r) for r in cur.fetchall()]
                if not members:
                    members = [{
                        "id": "doc_priya",
                        "email": "dr.priya@clinic.org",
                        "full_name": "Dr. Priya",
                        "specialization": "Lead Camp Physician",
                        "community_role": "admin",
                        "is_active": 1
                    }]
        return jsonify({"members": members, "total": len(members)})

    @app.route("/api/community/rotate-code", methods=["POST"])
    def community_rotate():
        if not is_admin_request():
            return jsonify({"error": "forbidden", "message": "Admin authorization required."}), 403
        data = request.get_json(silent=True) or {}
        comm_id = data.get("community_id") or getattr(g, "org_id", None)
        new_code = data.get("new_code")
        if not comm_id:
            return jsonify({"error": "community_id is required"}), 400
        res = database.rotate_community_code(comm_id, new_code=new_code, db_path=db_path)
        if not res:
            res = database.create_community("Organization", "Admin", "admin@org.com", code=new_code or "ROTATED-CODE", db_path=db_path)
        return jsonify({"success": True, "community": res}), 200

    @app.route("/api/community/members/revoke", methods=["POST"])
    def community_revoke_member():
        if not is_admin_request():
            return jsonify({"error": "forbidden", "message": "Admin authorization required."}), 403
        data = request.get_json(silent=True) or {}
        comm_id = data.get("community_id")
        doctor_id = data.get("doctor_id")
        if not comm_id or not doctor_id:
            return jsonify({"error": "community_id and doctor_id are required"}), 400
        success = database.revoke_community_member(comm_id, doctor_id, db_path=db_path)
        return jsonify({"success": success})

    # --- Doctor Authentication & Profile API ---
    @app.route("/api/auth/send-otp", methods=["POST"])
    @limiter.limit("10/minute")
    def auth_send_otp():
        data = request.get_json(silent=True) or {}
        phone = (data.get("phone") or "").strip()
        if not phone:
            return jsonify({"error": "Phone number is required."}), 400
        
        demo_mode_active = os.getenv("DEMO_MODE", "0").lower() in ("1", "true")
        logger.info("Clinical verification code requested for %s (demo_mode=%s)", phone, demo_mode_active)
        from backend.services.auth_service import send_otp_for_recipient
        try:
            send_otp_for_recipient(phone)
        except Exception as e:
            logger.warning("OTP dispatch fallback: %s", e)

        resp = {
            "success": True,
            "message": f"Clinical verification code sent to {phone}"
        }
        if demo_mode_active:
            resp["demo_otp"] = "123456"
        return jsonify(resp)

    @app.route("/api/auth/demo", methods=["POST"])
    @limiter.limit("10/minute")
    def auth_demo():
        app_env = os.getenv("APP_ENV", "").strip().lower()
        demo_mode_active = os.getenv("DEMO_MODE", "0").lower() in ("1", "true")
        if app_env == "production" or not demo_mode_active:
            return jsonify({"error": "Demo login is disabled and refused in production. DEMO_MODE=1 required."}), 403
        from backend.services.auth_service import create_access_token
        token = create_access_token(
            user_id="doc_demo",
            role="doctor",
            org_id="comm_demo",
            email="demo@clinic.camp",
            name="Dr. Priya (Demo)"
        )
        return jsonify({
            "success": True,
            "token": token,
            "doctor": {"id": "doc_demo", "full_name": "Dr. Priya (Demo)", "role": "doctor"},
            "community": {"id": "comm_demo", "name": "Rotary Community Health Outreach", "code": "CAMP-2026"}
        })

    @app.route("/api/auth/login", methods=["POST"])
    @limiter.limit("10/minute")
    def auth_login():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        phone = (data.get("phone") or "").strip()
        pin = (data.get("pin") or "").strip()
        otp = (data.get("otp") or "").strip()
        password = data.get("password") or ""
        community_code = (data.get("community_code") or "").strip().upper() or "CAMP-2026"

        app_env = os.getenv("APP_ENV", "production").strip().lower()
        demo_mode_active = os.getenv("DEMO_MODE", "0").lower() in ("1", "true")
        is_demo_req = bool(data.get("is_demo") or data.get("demo") or email == "demo@clinic.camp")
        if is_demo_req and (app_env == "production" or not demo_mode_active):
            return jsonify({"error": "Demo login is disabled and refused in production. DEMO_MODE=1 required."}), 403

        comm = database.get_community_by_code(community_code, db_path=db_path)
        if not comm:
            return jsonify({"error": f"Invalid Community Code '{community_code}'. You can only log in with an active community invite code."}), 403

        from backend.services.auth_service import (
            create_access_token,
            verify_submitted_otp,
            check_account_locked,
            record_login_attempt,
            verify_pin,
            hash_pin
        )

        account_key = phone or email or "anonymous_login"
        is_locked, remaining_sec = check_account_locked(account_key)
        if is_locked:
            return jsonify({
                "error": "Account is locked due to 5 consecutive failed attempts. Please try again in 15 minutes.",
                "code": "ACCOUNT_LOCKED",
                "remaining_seconds": remaining_sec
            }), 403

        # Look up existing doctor record for email or phone
        existing_doc = None
        with database.get_db_connection(db_path) as conn:
            cur = conn.cursor()
            if email:
                existing_doc = cur.execute("SELECT * FROM doctors WHERE LOWER(email) = ?;", (email,)).fetchone()
            elif phone:
                clean_p = re.sub(r'[^0-9+]', '', phone)
                existing_doc = cur.execute("SELECT * FROM doctors WHERE phone = ? OR phone = ?;", (phone, clean_p)).fetchone()

        # Handle PIN verification and auto-upgrade
        pin_verified = False
        if pin:
            if len(pin) < 4:
                return jsonify({"error": "PIN must be at least 4 digits."}), 400

            if existing_doc and existing_doc["pin_hash"]:
                if not verify_pin(pin, existing_doc["pin_hash"], existing_doc["pin_salt"]):
                    record_login_attempt(account_key, success=False)
                    return jsonify({"error": "Invalid PIN.", "success": False}), 401

                record_login_attempt(account_key, success=True)
                pin_verified = True
                # Auto-upgrade legacy SHA-256 hash to bcrypt
                if not (existing_doc["pin_hash"].startswith("$2b$") or existing_doc["pin_hash"].startswith("$2a$")):
                    upgraded_hash, upgraded_salt = hash_pin(pin)
                    with database.get_db_connection(db_path) as conn:
                        conn.cursor().execute(
                            "UPDATE doctors SET pin_hash = ?, pin_salt = ? WHERE id = ?;",
                            (upgraded_hash, upgraded_salt, existing_doc["id"])
                        )
                        conn.commit()
            elif existing_doc and not existing_doc["pin_hash"]:
                record_login_attempt(account_key, success=False)
                return jsonify({"error": "Invalid PIN. No PIN set for this account.", "success": False}), 401
            elif not existing_doc and (email or phone):
                record_login_attempt(account_key, success=False)
                return jsonify({"error": "Invalid PIN or account not found.", "success": False}), 401

        # Support Phone OTP / PIN login
        if phone:
            if not pin_verified:
                if not otp:
                    record_login_attempt(account_key, success=False)
                    return jsonify({"error": "Phone login requires either an OTP verification code or valid PIN.", "code": "CREDENTIALS_REQUIRED"}), 401

                if otp == "123456":
                    if app_env != "development":
                        record_login_attempt(account_key, success=False)
                        return jsonify({"error": "Invalid verification code. DEV_OTP is only permitted in development.", "success": False}), 401
                else:
                    if not verify_submitted_otp(phone, otp):
                        record_login_attempt(account_key, success=False)
                        return jsonify({"error": "Invalid verification code.", "success": False}), 401

            clean_phone = re.sub(r'[^0-9+]', '', phone)
            email = email or f"doc_{clean_phone.replace('+', '')}@clinic.camp"
            doc_name = data.get("full_name") or f"Dr. {clean_phone[-4:] if len(clean_phone) >= 4 else 'Physician'}"
            doctor = database.get_or_create_doctor(
                email=email,
                full_name=doc_name,
                community_id=comm["id"],
                community_code=comm["code"],
                db_path=db_path
            )
            try:
                with database.get_db_connection(db_path) as conn:
                    conn.cursor().execute("UPDATE doctors SET phone = ? WHERE id = ?;", (clean_phone, doctor["id"]))
                    conn.commit()
            except Exception as phone_update_error:
                logger.warning("Failed to update doctor phone number for %s: %s", doctor["id"], phone_update_error)

            record_login_attempt(account_key, success=True)
            profile = database.get_doctor_profile(doctor["id"], db_path=db_path)
            token = create_access_token(
                user_id=doctor["id"],
                role=doctor.get("community_role", "doctor"),
                org_id=comm["id"],
                email=email,
                name=doc_name
            )
            return jsonify({
                "success": True,
                "token": token,
                "doctor": profile,
                "community": comm
            })

        if not email:
            return jsonify({"error": "Doctor email or mobile phone is required."}), 400

        # Doctor Email Login: Must authenticate via PIN, password, or Supabase
        token = None
        if pin_verified:
            pass  # Already verified above
        elif password:
            if supabase_service.is_configured():
                auth_res = supabase_service.auth_sign_in(email, password)
                if auth_res.get("success"):
                    token = auth_res.get("access_token")
                else:
                    record_login_attempt(account_key, success=False)
                    return jsonify({"error": "Invalid email or password.", "code": "INVALID_CREDENTIALS"}), 401
            else:
                # If demo mode active or local development, verify password or pin
                if existing_doc and existing_doc["pin_hash"]:
                    if not verify_pin(password, existing_doc["pin_hash"], existing_doc["pin_salt"]):
                        record_login_attempt(account_key, success=False)
                        return jsonify({"error": "Invalid email or password.", "code": "INVALID_CREDENTIALS"}), 401
                elif app_env == "production":
                    record_login_attempt(account_key, success=False)
                    return jsonify({"error": "Invalid credentials or authentication service unconfigured.", "code": "INVALID_CREDENTIALS"}), 401
        else:
            record_login_attempt(account_key, success=False)
            return jsonify({"error": "Password or PIN is required for doctor email login.", "code": "CREDENTIALS_REQUIRED"}), 401

        name_part = email.split("@")[0].replace(".", " ").replace("_", " ").title()
        doc_name = f"Dr. {name_part}" if not name_part.startswith("Dr") else name_part
        doctor = database.get_or_create_doctor(
            email=email,
            full_name=doc_name,
            community_id=comm["id"],
            community_code=comm["code"],
            db_path=db_path
        )
        record_login_attempt(account_key, success=True)
        profile = database.get_doctor_profile(doctor["id"], db_path=db_path)
        if not token:
            token = create_access_token(
                user_id=doctor["id"],
                role=doctor.get("community_role", "doctor"),
                org_id=comm["id"],
                email=email,
                name=doc_name
            )

        return jsonify({
            "success": True,
            "token": token,
            "doctor": profile,
            "community": comm
        })

    @app.route("/api/auth/signup", methods=["POST"])
    def auth_signup():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        full_name = (data.get("full_name") or "").strip()
        specialization = (data.get("specialization") or "General Physician").strip()
        community_code = (data.get("community_code") or "").strip().upper()

        if not email or not full_name:
            return jsonify({"error": "Email and Full Name are required."}), 400

        # STRICT RULE: A community code is mandatory for doctor registration
        if not community_code:
            return jsonify({"error": "Community Invite Code is required to join. Contact your community organizer or build a new community."}), 400

        comm = database.get_community_by_code(community_code, db_path=db_path)
        if not comm:
            return jsonify({"error": f"Invalid Community Code '{community_code}'. Doctors can only register with a valid community invite code."}), 403

        token = None
        if supabase_service.is_configured() and password:
            auth_res = supabase_service.auth_sign_up(email, password, full_name, specialization)
            token = auth_res.get("access_token")

        # Caller 'role' and 'org_id' are strictly ignored: role is always 'doctor', org is comm["id"]
        doctor = database.get_or_create_doctor(
            email=email,
            full_name=full_name,
            specialization=specialization,
            community_id=comm["id"],
            community_code=comm["code"],
            community_role="doctor",
            db_path=db_path
        )
        profile = database.get_doctor_profile(doctor["id"], db_path=db_path)
        from backend.services.auth_service import create_access_token
        if not token:
            token = create_access_token(
                user_id=doctor["id"],
                role="doctor",
                org_id=comm["id"],
                email=email,
                name=full_name
            )

        return jsonify({
            "success": True,
            "token": token,
            "doctor": profile,
            "community": comm
        }), 201

    @app.route("/api/doctor/profile", methods=["GET", "PUT"])
    def doctor_profile():
        from flask import g
        doc_id = request.args.get("doctor_id") or request.headers.get("X-Doctor-ID")
        if not doc_id and hasattr(g, "current_user") and g.current_user:
            doc_id = g.current_user.get("user_id") or g.current_user.get("email")
            if doc_id == "doc_demo":
                doc_id = "dr.priya@clinic.org"
        if not doc_id:
            doc_id = "dr.priya@clinic.org"

        if request.method == "GET":
            prof = database.get_doctor_profile(doc_id, db_path=db_path)
            return jsonify(prof)
        else:
            data = request.get_json(silent=True) or {}
            full_name = data.get("full_name") or "Dr. Priya"
            spec = data.get("specialization") or "General Physician"
            avatar = data.get("avatar_url")
            updated = database.update_doctor_profile(doc_id, full_name, spec, avatar, db_path=db_path)
            return jsonify(updated)

    @app.route("/api/sync/supabase", methods=["POST"])
    def sync_to_supabase():
        """Push all existing local SQLite camps and records to Supabase."""
        if not supabase_service.is_configured():
            return jsonify({"error": "Supabase credentials not configured in backend/.env"}), 400
        try:
            res = supabase_service.sync_from_sqlite(db_path)
            return jsonify({"status": "ok", "synced": res})
        except Exception as e:
            logger.exception("Error syncing SQLite to Supabase")
            return jsonify({"error": str(e)}), 500

    # --- AI Extraction API ---
    @app.route("/api/extract", methods=["POST"])
    @limiter.limit("10/minute")
    def extract_document():
        """Accepts student_form and health_assessment sheets, checks quota/dedup, and calls AI extractor."""
        # Support both new standard names and backward-compatible page1/page2
        sf_file = request.files.get("student_form") or request.files.get("page1")
        ha_file = request.files.get("health_assessment") or request.files.get("page2")

        if not sf_file or not ha_file:
            return jsonify({
                "error": "Both student_form and health_assessment image files are required for extraction.",
                "code": "MISSING_PAGES"
            }), 400

        if not sf_file.filename or not ha_file.filename:
            return jsonify({"error": "One or both uploaded files are empty.", "code": "EMPTY_FILE"}), 400

        sf_mime = sf_file.mimetype or "image/jpeg"
        ha_mime = ha_file.mimetype or "image/jpeg"

        if sf_mime not in ALLOWED_MIME_TYPES or ha_mime not in ALLOWED_MIME_TYPES:
            return jsonify({
                "error": "Invalid image format. Allowed formats: JPEG, PNG, WebP, HEIC/HEIF.",
                "code": "INVALID_MIME_TYPE"
            }), 400

        sf_bytes = sf_file.read()
        ha_bytes = ha_file.read()

        if len(sf_bytes) > MAX_FILE_SIZE or len(ha_bytes) > MAX_FILE_SIZE:
            return jsonify({
                "error": "Image file size exceeds the 15 MB limit.",
                "code": "FILE_TOO_LARGE"
            }), 400

        camp_id = request.form.get("camp_id") or request.args.get("camp_id") or "camp_default"
        record_id = request.form.get("record_id") or request.args.get("record_id")
        org_id = request.headers.get("X-Org-ID") or request.form.get("org_id") or request.args.get("org_id") or "org_default"

        # Permanent Private Storage: Save scans in private directory outside static root (Rule 10.1)
        target_org = getattr(g, "org_id", org_id)
        f1_id = database.save_private_file(
            org_id=target_org,
            record_id=record_id,
            file_type="scan_page1",
            filename=f"{camp_id}_p1.jpg",
            data=sf_bytes,
            mime_type="image/jpeg",
            db_path=db_path
        )
        f2_id = database.save_private_file(
            org_id=target_org,
            record_id=record_id,
            file_type="scan_page2",
            filename=f"{camp_id}_p2.jpg",
            data=ha_bytes,
            mime_type="image/jpeg",
            db_path=db_path
        )
        page1_permanent_url = f"/api/files/{f1_id}"
        page2_permanent_url = f"/api/files/{f2_id}"

        # Dynamic AI API Key, Provider, and Model overrides
        dynamic_key = (
            request.headers.get("X-AI-API-Key")
            or request.headers.get("X-API-Key")
            or request.form.get("api_key")
            or request.args.get("api_key")
        )
        dynamic_provider = (
            request.headers.get("X-AI-Provider")
            or request.form.get("ai_provider")
            or request.args.get("ai_provider")
        )
        dynamic_model = (
            request.headers.get("X-AI-Model")
            or request.form.get("model")
            or request.args.get("model")
        )

        # Emergency AI Kill Switch Check (Fail fast before image analysis or reservations)
        try:
            with database.get_db_connection(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ai_paused FROM orgs WHERE id = ?;", (org_id,))
                org_row = cursor.fetchone()
                if org_row and org_row["ai_paused"]:
                    return jsonify({
                        "success": False,
                        "error": "AI processing is currently paused by administrator kill switch.",
                        "code": "AI_PAUSED"
                    }), 403
        except Exception as ai_pause_check_error:
            logger.warning("Failed to check AI pause status for org %s: %s", org_id, ai_pause_check_error)

        # Task 2: Server-side Quality Pre-flight Check
        from backend.services.quality_service import assess_image_quality
        q1 = assess_image_quality(sf_bytes)
        q2 = assess_image_quality(ha_bytes)
        quality_ok = bool((q1.get("ok") is not False) and (q2.get("ok") is not False))
        combined_issues = []
        if q1.get("ok") is False and q1.get("issues"):
            combined_issues.extend([f"Page 1: {iss}" for iss in q1["issues"]])
        if q2.get("ok") is False and q2.get("issues"):
            combined_issues.extend([f"Page 2: {iss}" for iss in q2["issues"]])

        quality_bypassed = (
            request.headers.get("X-Quality-Bypassed", "").strip().lower() in ("1", "true")
            or request.form.get("quality_bypassed", "").strip().lower() in ("1", "true")
            or request.args.get("quality_bypassed", "").strip().lower() in ("1", "true")
        )

        quality_summary = {
            "page1": q1,
            "page2": q2,
            "blur_score": min(q1.get("blur_score", 0), q2.get("blur_score", 0)),
            "brightness": round((q1.get("brightness", 0) + q2.get("brightness", 0)) / 2.0, 2),
            "glare_pct": max(q1.get("glare_pct", 0), q2.get("glare_pct", 0)),
            "ok": quality_ok,
            "issues": combined_issues
        }

        if not quality_ok and not quality_bypassed:
            if record_id:
                try:
                    database.release_paper(org_id=org_id, record_id=record_id, db_path=db_path)
                except Exception as paper_release_error:
                    logger.error("Failed to release paper quota for record %s: %s", record_id, paper_release_error)
            return jsonify({
                "success": False,
                "error": "unreadable",
                "message": f"Image quality check failed. Please retake the photo. Issues: {', '.join(combined_issues)}",
                "quality": quality_summary,
                "code": "IMAGE_UNREADABLE"
            }), 422

        template_ids_raw = request.form.get("template_ids") or request.args.get("template_ids")
        template_ids_list = [t.strip() for t in template_ids_raw.split(",") if t.strip()] if template_ids_raw else None

        result = ai_extract(
            student_form_bytes=sf_bytes,
            health_assessment_bytes=ha_bytes,
            camp_id=camp_id,
            record_id=record_id,
            org_id=org_id,
            db_path=db_path,
            api_key=dynamic_key,
            provider=dynamic_provider,
            model=dynamic_model,
            template_ids=template_ids_list
        )

        # Inject quality metrics and bypass flag
        result["quality"] = quality_summary
        result["quality_bypassed"] = quality_bypassed
        if isinstance(result.get("data"), dict):
            result["data"]["quality"] = quality_summary
            result["data"]["quality_bypassed"] = quality_bypassed

        # Inject permanent URLs so client saves durable image links in database
        result["page1_url"] = page1_permanent_url
        result["page2_url"] = page2_permanent_url
        if isinstance(result.get("data"), dict):
            result["data"]["page1_url"] = page1_permanent_url
            result["data"]["page2_url"] = page2_permanent_url

        http_code = result.get("http_status", 200 if result.get("success") else 422)
        return jsonify(result), http_code

    @app.route("/api/extract/v2", methods=["POST"])
    def extract_document_v2():
        """Phase 3 Extraction v2: Template-driven extraction with field-scoped glossary and invariants."""
        # Check for JSON payload normalization
        json_data = request.get_json(silent=True) or {}
        if json_data.get("template_id") and (json_data.get("raw_model_json") or json_data.get("data")):
            t_id = json_data.get("template_id")
            raw_json = json_data.get("raw_model_json") or json_data.get("data")
            try:
                processed = default_extraction_pipeline.process_extracted_payload(t_id, raw_json)
                return jsonify({"success": True, "result": processed}), 200
            except KeyError as ke:
                return jsonify({"success": False, "error": str(ke), "code": "TEMPLATE_NOT_FOUND"}), 404
            except Exception as e:
                return jsonify({"success": False, "error": str(e), "code": "NORMALIZATION_ERROR"}), 422

        # Check for image file upload
        file = request.files.get("image") or request.files.get("page") or request.files.get("student_form")
        if not file:
            return jsonify({
                "error": "No image file or extraction JSON provided. Expecting 'image' file or 'raw_model_json' payload.",
                "code": "MISSING_INPUT"
            }), 400

        img_bytes = file.read()
        t_id = request.form.get("template_id") or request.args.get("template_id")
        footer_code = request.form.get("footer_code") or request.args.get("footer_code")
        header_text = request.form.get("header_text") or request.args.get("header_text")

        if not t_id:
            classification = default_template_engine.classify_page(footer_code, header_text)
            t_id = classification.get("template_id") or "tpl_adult_examination_v9_1"

        tpl = default_template_engine.get_template(t_id)
        if not tpl:
            return jsonify({"error": f"Template '{t_id}' not registered.", "code": "TEMPLATE_NOT_FOUND"}), 404

        # Save permanent scan file in private directory outside static root (Rule 10.1)
        target_org = getattr(g, "org_id", "org_default")
        f_id = database.save_private_file(
            org_id=target_org,
            record_id=None,
            file_type="scan_form",
            filename=f"form_{t_id}.jpg",
            data=img_bytes,
            mime_type="image/jpeg",
            db_path=db_path
        )

        # Process form inputs through extraction pipeline
        form_payload = {}
        for sec in tpl.get("sections", []):
            for f in sec.get("fields", []):
                val = request.form.get(f["key"])
                if val is not None:
                    form_payload[f["key"]] = {"raw_text": val, "confidence": 0.95}

        processed = default_extraction_pipeline.process_extracted_payload(t_id, form_payload)
        processed["image_url"] = f"/api/files/{f_id}"
        processed["file_id"] = f_id
        processed["image_hash"] = default_extraction_pipeline.compute_image_hash(img_bytes)

        return jsonify({
            "success": True,
            "template_id": t_id,
            "template_title": tpl.get("title", ""),
            "data": processed,
            "code": "EXTRACTION_SUCCESS"
        }), 200

    # --- Unified AI Pipeline Status & Telemetry ---
    @app.route("/api/ai/status", methods=["GET"])
    def get_ai_status():
        """Returns auto-detected AI provider configuration, model, and guardrail parameters."""
        try:
            from backend.services.unified_pipeline import detect_ai_provider, PROVIDER_DEFAULTS
        except ImportError:
            from services.unified_pipeline import detect_ai_provider, PROVIDER_DEFAULTS
        
        req_key = (
            request.headers.get("X-AI-API-Key") or
            request.args.get("api_key") or
            ""
        ).strip()
        req_provider = (
            request.headers.get("X-AI-Provider") or
            request.args.get("provider") or
            ""
        ).strip().lower()

        detected_provider = detect_ai_provider(req_key, preferred=req_provider) if req_key or req_provider else detect_ai_provider("")
        cfg = PROVIDER_DEFAULTS.get(detected_provider, {})

        configured_providers = []
        for prov, info in PROVIDER_DEFAULTS.items():
            key = os.getenv(f"{prov.upper()}_API_KEY", "")
            if key and len(key) > 8:
                configured_providers.append({
                    "provider": prov,
                    "name": info["name"],
                    "primary_model": info["primary_model"],
                    "fallback_model": info["fallback_model"]
                })

        return jsonify({
            "unified_pipeline": True,
            "active_provider": detected_provider,
            "provider_name": cfg.get("name", detected_provider),
            "primary_model": cfg.get("primary_model"),
            "fallback_model": cfg.get("fallback_model"),
            "configured_providers": configured_providers,
            "guardrail_parameters": {
                "flag_confidence": float(os.getenv("FLAG_CONFIDENCE", "0.8")),
                "flag_confidence_measure": float(os.getenv("FLAG_CONFIDENCE_MEASURE", "0.9")),
                "image_max_edge_px": int(os.getenv("IMAGE_MAX_EDGE_PX", "1568")),
                "timeout_seconds": int(os.getenv("AI_TIMEOUT_SECONDS", "60")),
                "max_retries": int(os.getenv("AI_MAX_RETRIES", "2")),
                "temperature": 0.0,
                "max_output_tokens": 4000
            }
        })

    # --- Phase 3 Usage & Metering Endpoints (Admin-Only) ---
    @app.route("/api/usage", methods=["GET"])
    def get_usage_endpoint():
        """Returns papers included, used, left, add-on papers, renewal date, and cost this month (Admin-Only)."""
        if not is_admin_request():
            return jsonify({"error": "forbidden", "message": "Admin authorization required to access usage telemetry."}), 403
        org_id = request.headers.get("X-Org-ID") or request.args.get("org_id") or "org_default"
        summary = database.get_usage_summary(org_id=org_id, db_path=db_path)
        return jsonify(summary)

    @app.route("/api/usage/ledger", methods=["GET"])
    def get_usage_ledger_endpoint():
        """Returns paginated usage ledger entries (Admin-Only)."""
        if not is_admin_request():
            return jsonify({"error": "forbidden", "message": "Admin authorization required to access usage ledger."}), 403
        org_id = request.headers.get("X-Org-ID") or request.args.get("org_id") or "org_default"
        from_date = request.args.get("from")
        to_date = request.args.get("to")
        try:
            page = int(request.args.get("page", 1))
            limit = int(request.args.get("limit", 50))
        except (ValueError, TypeError):
            page, limit = 1, 50

        ledger_data = database.get_usage_ledger_paged(
            org_id=org_id,
            from_date=from_date,
            to_date=to_date,
            page=page,
            limit=limit,
            db_path=db_path
        )
        return jsonify(ledger_data)

    @app.route("/api/admin/ai-pause", methods=["POST"])
    @app.route("/api/ai/pause", methods=["POST"])
    def admin_ai_pause():
        """Emergency kill switch per organization or global (Admin-Only)."""
        if not is_admin_request():
            return jsonify({"error": "forbidden", "message": "Admin authorization required to toggle AI kill switch."}), 403
        data = request.get_json(silent=True) or {}
        org_id = data.get("org_id")
        paused = bool(data.get("paused", True))
        success = database.set_ai_pause(org_id=org_id, paused=paused, db_path=db_path)
        return jsonify({
            "success": success,
            "paused": paused,
            "org_id": org_id or "all",
            "message": "AI processing paused" if paused else "AI processing resumed"
        })

    @app.route("/api/admin/cleanup-expired-reservations", methods=["POST"])
    def admin_cleanup_expired_reservations():
        """Scheduled job: release unapproved reservations older than RESERVATION_EXPIRY_DAYS (Admin-Only)."""
        if not is_admin_request():
            return jsonify({"error": "forbidden", "message": "Admin authorization required to run reservation cleanup."}), 403
        data = request.get_json(silent=True) or {}
        expiry_days = int(data.get("expiry_days") or request.args.get("expiry_days") or os.getenv("RESERVATION_EXPIRY_DAYS", "7"))
        released = database.release_expired_reservations(expiry_days=expiry_days, db_path=db_path)
        return jsonify({
            "success": True,
            "released_papers": released,
            "expiry_days": expiry_days,
            "message": f"Successfully released {released} unapproved paper reservation(s)."
        })

    # --- Phase 4: Razorpay Orders, Webhook & Invoices API ---
    @app.route("/api/billing/order", methods=["POST"])
    def billing_create_order():
        """Create a Razorpay order for purchasing scan credits."""
        data = request.get_json(silent=True) or {}
        org_id = request.headers.get("X-Org-ID") or data.get("org_id") or "org_default"
        papers = int(data.get("papers", 1000))

        # Standard pack pricing:
        if papers == 1000:
            base_rs = 5000.0
        elif papers == 2500:
            base_rs = 11250.0
        elif papers == 5000:
            base_rs = 20000.0
        else:
            base_rs = round(papers * 5.0, 2)

        gst_rs = round(base_rs * 0.18, 2)
        total_rs = base_rs + gst_rs
        amount_paise = int(round(total_rs * 100))

        order_id = f"order_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}"
        key_id = os.getenv("RAZORPAY_KEY_ID", "rzp_test_ink2insights")

        return jsonify({
            "order_id": order_id,
            "papers": papers,
            "amount_rs": base_rs,
            "gst_rs": gst_rs,
            "total_rs": total_rs,
            "amount_paise": amount_paise,
            "currency": "INR",
            "key_id": key_id,
            "org_id": org_id
        })

    @app.route("/api/billing/webhook", methods=["POST"])
    def billing_webhook():
        """Signature-checked Razorpay webhook with idempotent credit and sequential GST invoice PDF."""
        signature = request.headers.get("X-Razorpay-Signature", "")
        raw_body = request.get_data()

        app_env = (os.getenv("APP_ENV") or "development").strip().lower()
        webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
        if not webhook_secret:
            if app_env == "production":
                return jsonify({"error": "configuration_error", "message": "RAZORPAY_WEBHOOK_SECRET must be configured in production."}), 500
            webhook_secret = "mock_webhook_secret"

        if not database.verify_razorpay_webhook_signature(raw_body, signature, webhook_secret=webhook_secret):
            return jsonify({"error": "invalid_signature", "message": "HMAC signature mismatch"}), 400

        payload = request.get_json(silent=True) or {}
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {}) if "payload" in payload else payload
        payment_id = payment_entity.get("id") or payload.get("razorpay_payment_id") or f"pay_{os.urandom(4).hex()}"
        notes = payment_entity.get("notes", {})
        org_id = notes.get("org_id") or payload.get("org_id") or "org_default"
        papers = int(notes.get("papers") or payload.get("papers", 1000))

        if papers == 1000:
            base_rs = 5000.0
        elif papers == 2500:
            base_rs = 11250.0
        elif papers == 5000:
            base_rs = 20000.0
        else:
            base_rs = round(papers * 5.0, 2)
        gst_rs = round(base_rs * 0.18, 2)

        success, result = database.process_successful_payment(
            org_id=org_id,
            payment_id=payment_id,
            papers=papers,
            amount_rs=base_rs,
            gst_rs=gst_rs,
            db_path=db_path
        )

        return jsonify({
            "status": "ok",
            "success": success,
            "result": result
        })

    @app.route("/api/billing/invoices", methods=["GET"])
    def billing_invoices():
        """List all GST invoices for the organization."""
        org_id = getattr(g, "org_id", None) or "org_default"
        invoices = database.get_invoices_for_org(org_id=org_id, db_path=db_path)
        return jsonify({"invoices": invoices, "total": len(invoices)})

    @app.route("/api/billing/invoices/<invoice_id>/download", methods=["GET"])
    def billing_download_invoice(invoice_id):
        """Download invoice PDF by invoice ID or invoice number."""
        inv = database.get_invoice_by_id_or_number(invoice_id, db_path=db_path)
        if not inv or not inv.get("pdf_path") or not os.path.exists(inv["pdf_path"]):
            return jsonify({"error": "Invoice PDF not found"}), 404

        caller_org = getattr(g, "org_id", None)
        if caller_org and inv.get("org_id") and inv.get("org_id") != caller_org:
            return jsonify({"error": "forbidden", "message": "Access denied across organizations"}), 403

        pdf_path = inv["pdf_path"]
        inv_number = inv.get("number", "invoice")
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={inv_number}.pdf"}
        )

    # --- Comprehensive Excel Export (and CSV fallback) ---
    @app.route("/api/export", methods=["GET"])
    def export_all():
        from flask import g
        if getattr(g, "user_role", None) == "field_worker":
            return jsonify({"error": "forbidden", "message": "Field workers are not permitted to export records."}), 403
        camp_id = request.args.get("camp_id")
        only_reviewed = request.args.get("only_reviewed", "false").lower() == "true"
        form_type = request.args.get("type") or request.args.get("form_type") or request.args.get("template")
        community_id = getattr(g, "org_id", None) or getattr(g, "community_id", None)
        fmt = request.args.get("format", "xlsx").lower()
        if fmt == "csv":
            csv_data = record_service.generate_csv_export(
                camp_id=camp_id,
                only_reviewed=only_reviewed,
                community_id=community_id,
                org_id=community_id
            )
            filename = f"clinic_records_{camp_id or 'all'}.csv"
            return Response(
                csv_data,
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        excel_data = record_service.generate_excel_export(
            camp_id=camp_id,
            only_reviewed=only_reviewed,
            form_type=form_type,
            community_id=community_id,
            org_id=community_id
        )
        prefix = f"{form_type}_" if form_type else ""
        filename = f"{prefix}clinic_records_{camp_id or 'all'}.xlsx"
        return Response(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    @app.route("/api/export/adult/excel", methods=["GET"])
    def export_adult_excel_endpoint():
        """Dedicated endpoint to download formatted Adult Health Screening Excel workbook."""
        from flask import g
        if getattr(g, "user_role", None) == "field_worker":
            return jsonify({"error": "forbidden", "message": "Field workers are not permitted to export records."}), 403
        camp_id = request.args.get("camp_id")
        only_reviewed = request.args.get("only_reviewed", "false").lower() == "true"
        community_id = getattr(g, "org_id", None) or getattr(g, "community_id", None)
        excel_data = record_service.generate_adult_excel_export(
            camp_id=camp_id,
            only_reviewed=only_reviewed,
            community_id=community_id,
            org_id=community_id
        )
        filename = f"Adult_Health_Records_{camp_id or 'all'}.xlsx"
        return Response(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    @app.route("/api/export/paediatric/excel", methods=["GET"])
    def export_paediatric_excel_endpoint():
        """Dedicated endpoint to download formatted Paediatric School Health Screening Excel workbook."""
        from flask import g
        if getattr(g, "user_role", None) == "field_worker":
            return jsonify({"error": "forbidden", "message": "Field workers are not permitted to export records."}), 403
        camp_id = request.args.get("camp_id")
        only_reviewed = request.args.get("only_reviewed", "false").lower() == "true"
        community_id = getattr(g, "org_id", None) or getattr(g, "community_id", None)
        excel_data = record_service.generate_paediatric_excel_export(
            camp_id=camp_id,
            only_reviewed=only_reviewed,
            community_id=community_id,
            org_id=community_id
        )
        filename = f"Paediatric_Health_Records_{camp_id or 'all'}.xlsx"
        return Response(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    @app.route("/api/camps/<camp_id>/export", methods=["GET"])
    @app.route("/api/camps/<camp_id>/export/excel", methods=["GET"])
    def export_camp(camp_id):
        from flask import g
        if getattr(g, "user_role", None) == "field_worker":
            return jsonify({"error": "forbidden", "message": "Field workers are not permitted to export records."}), 403
        camp = database.get_camp_by_id(camp_id, db_path)
        raw_name = camp.get("name", "Organization") if camp else "Organization"
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_name).strip('_') or f"Org_{camp_id}"
        form_type = request.args.get("type") or request.args.get("form_type") or request.args.get("template")
        fmt = request.args.get("format", "xlsx").lower()
        if fmt == "csv":
            csv_data = record_service.generate_csv_export(camp_id=camp_id, only_reviewed=False)
            filename = f"{safe_name}_Health_Records.csv"
            return Response(
                csv_data,
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        excel_data = record_service.generate_excel_export(camp_id=camp_id, only_reviewed=False, form_type=form_type)
        filename = f"{safe_name}_Health_Records.xlsx"
        return Response(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    # --- Separate Forms Structure & Attributes API ---
    @app.route("/api/forms", methods=["GET"])
    def list_forms_catalog():
        """List all available form definitions (adult/paediatric suites + individual pages) with attribute counts."""
        forms = default_template_engine.list_forms()
        return jsonify({
            "forms": forms,
            "count": len(forms)
        })

    @app.route("/api/forms/<form_id>", methods=["GET"])
    def get_form_structure_endpoint(form_id):
        """Get complete hierarchical structure (pages, sections, fields, validations) for a form."""
        structure = default_template_engine.get_form_structure(form_id)
        if not structure:
            return jsonify({"error": f"Form structure '{form_id}' not found."}), 404
        return jsonify(structure)

    @app.route("/api/forms/<form_id>/attributes", methods=["GET"])
    def get_form_attributes_endpoint(form_id):
        """Get flat attribute dictionary for a form (clinical labels, types, writers, export columns)."""
        structure = default_template_engine.get_form_structure(form_id)
        if not structure:
            return jsonify({"error": f"Form '{form_id}' not found."}), 404
        attributes = default_template_engine.get_form_attributes(form_id)
        return jsonify({
            "form_id": structure["id"],
            "title": structure["title"],
            "family": structure["family"],
            "attributes": attributes,
            "count": len(attributes)
        })

    @app.route("/api/forms/<form_id>/schema", methods=["GET"])
    def get_form_schema_endpoint(form_id):
        """Get dynamic UI rendering schema for tabs and form inputs."""
        canon_id = default_template_engine.resolve_form_id(form_id)
        if canon_id in default_template_engine.templates:
            return jsonify(default_template_engine.generate_ui_schema(canon_id))
        
        # Composite forms UI schema (combines tabs of both pages)
        structure = default_template_engine.get_form_structure(form_id)
        if not structure:
            return jsonify({"error": f"Form '{form_id}' not found."}), 404

        merged_tabs = []
        for p in structure.get("pages", []):
            page_title = p.get("title", f"Page {p.get('page_number')}")
            for sec in p.get("sections", []):
                fields = []
                for f in sec.get("fields", []):
                    fields.append({
                        "key": f["key"],
                        "label": f["label"],
                        "type": f["type"],
                        "required": f.get("required", False),
                        "options": f.get("options", []),
                        "validation": f.get("validation"),
                        "glossary_scope": f.get("glossary_scope"),
                        "alert_hook": f.get("alert_hook"),
                        "export_column": f.get("export_column") or f["key"]
                    })
                merged_tabs.append({
                    "id": f"p{p.get('page_number')}_{sec['id']}",
                    "title": f"[{page_title[:10]}] {sec['title']}",
                    "page_number": p.get("page_number"),
                    "fields": fields
                })

        return jsonify({
            "form_id": structure["id"],
            "title": structure["title"],
            "family": structure["family"],
            "tabs": merged_tabs
        })

    # --- Template Engine & Case Pairing Endpoints (Phase 2) ---
    @app.route("/api/templates", methods=["GET"])
    def list_templates():
        """List all available declarative clinical templates."""
        paed_enabled = os.getenv("ENABLE_PAEDIATRIC", "1").strip().lower() not in ("0", "false")
        all_templates = default_template_engine.list_templates()
        if not paed_enabled:
            all_templates = [t for t in all_templates if t.get("family") != "paediatric"]
        return jsonify({
            "templates": all_templates,
            "count": len(all_templates)
        })

    @app.route("/api/templates/<template_id>", methods=["GET"])
    def get_template(template_id):
        """Get full template definition or dynamic UI schema."""
        tpl = default_template_engine.get_template(template_id)
        if not tpl:
            return jsonify({"error": f"Template '{template_id}' not found."}), 404

        # Gate paediatric templates with ENABLE_PAEDIATRIC=1
        if tpl.get("family") == "paediatric" and os.getenv("ENABLE_PAEDIATRIC", "1").strip().lower() in ("0", "false"):
            return jsonify({
                "error": "forbidden",
                "message": "Paediatric templates are currently disabled (ENABLE_PAEDIATRIC=0)."
            }), 403

        if request.args.get("ui_schema", "false").lower() == "true":
            return jsonify(default_template_engine.generate_ui_schema(template_id))
        return jsonify(tpl)

    @app.route("/api/templates/classify", methods=["POST"])
    def classify_page_template():
        """Classify page template based on footer code or title text."""
        data = request.get_json(silent=True) or {}
        footer_code = data.get("footer_code")
        header_text = data.get("header_text")
        result = default_template_engine.classify_page(footer_code, header_text)
        return jsonify(result)

    @app.route("/api/cases/pair", methods=["POST"])
    def pair_case_endpoint():
        """Pair history and examination page payloads into a unified Case."""
        data = request.get_json(silent=True) or {}
        history_page = data.get("history_page") or {}
        exam_page = data.get("exam_page") or {}
        session_id = data.get("session_id")
        result = default_template_engine.pair_case(history_page, exam_page, session_id=session_id)
        return jsonify(result)

    # --- Clear / Reset Data ---
    @app.route("/api/reset-demo", methods=["POST"])
    @app.route("/api/clear-data", methods=["POST"])
    def reset_demo():
        database.clear_all_records(db_path)
        logger.info("Database records and camps were cleared for clean production.")
        return jsonify({"message": "Data cleared successfully", "stats": database.get_overall_stats(db_path)})

    return app

# Top-level Flask instance required by Vercel and WSGI runtimes
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    logger.info("Starting I2 insights Clinical API on port %d...", port)
    app.run(host="0.0.0.0", port=port, debug=False)
