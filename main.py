from flask_talisman import Talisman
import os
import json
import logging
import atexit
import traceback
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from flask_session import Session  # ✅ NEW: Flask-Session
from flask_cors import CORS  # ✅ NEW: CORS support
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler
from functools import wraps  # ✅ NEW: For decorators

from analytics_api import setup_analytics_routes
from sync_feed import sync_products_from_feed
from chatbot import bot
from database import db

load_dotenv()

# ==================== LOGGING (define FIRST) ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ==================== APP SETUP ====================
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# ✅ CORS Configuration - Allow requests from ejolie.ro domain
CORS(app,
     origins=[
         'https://ejolie.ro',
         'https://www.ejolie.ro',
         'https://app.fabrex.org',  # ✅ Allow widget domain
         'http://localhost:3000',  # For local development
         'http://localhost:5000',  # For local development
     ],
     supports_credentials=True,  # Allow cookies/sessions
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'OPTIONS']
     )

# Talisman(app,
#        force_https=True,
#         strict_transport_security_max_age=31536000,
#         frame_options='SAMEORIGIN',  # ✅ Allow same origin embedding
#         content_security_policy={
#             'default-src': "'self'",
#             'script-src': ["'self'", "'unsafe-inline'"],
#             'style-src': ["'self'", "'unsafe-inline'"],
#             # ✅ Allow product images!
#             'img-src': ["'self'", 'data:', 'https://ejolie.ro', 'https://www.ejolie.ro', 'https://via.placeholder.com'],
#            # ✅ Allow iframe embedding from ejolie.ro
#           'frame-ancestors': ["'self'", 'https://ejolie.ro', 'https://www.ejolie.ro', 'https://*.ejolie.ro'],
#          # ✅ Allow API calls
#         'connect-src': ["'self'", 'https://ejolie.ro', 'https://www.ejolie.ro', 'https://app.fabrex.org'],
#    },
#
#        )

# ✅ Flask-Session Configuration (Railway-compatible)
app.config['SESSION_TYPE'] = None  # Use signed cookies (no filesystem)
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_DOMAIN'] = os.environ.get(
    'SESSION_COOKIE_DOMAIN', None)  # Set to 'app.fabrex.org' in production
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-production')

# ==================== RATE LIMITING ====================
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)
logger.info("🔒 Rate limiting: ENABLED")
logger.info("🍪 Session management: ENABLED (secure cookies)")

# ==================== CONFIG ====================
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
if ADMIN_PASSWORD == "admin123":
    logger.warning("⚠️ SECURITY WARNING: Using default admin password!")

# ==================== AUTH DECORATORS ====================


def require_login(f):
    """Decorator to require valid session login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))

        # Refresh session timeout on each request
        session.permanent = True
        app.permanent_session_lifetime = timedelta(days=7)

        return f(*args, **kwargs)
    return decorated_function


def require_admin(f):
    """Decorator to require admin session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check password from session
        if 'admin_authenticated' not in session:
            return jsonify({"error": "Unauthorized - please provide admin password"}), 401

        return f(*args, **kwargs)
    return decorated_function

# ==================== AUTO SYNC ====================


def do_sync():
    try:
        logger.info("🔄 Starting product sync...")
        result = sync_products_from_feed()
        if result.get("status") == "success":
            bot.load_products()
            logger.info(
                f"✅ Sync complete: {result.get('products_count')} products")
            return True
        logger.warning(f"⚠️ Sync returned non-success: {result}")
    except Exception:
        logger.error("❌ Sync failed:")
        logger.error(traceback.format_exc())
    return False


logger.info("🚀 Starting Ejolie ChatBot Server...")

if not os.path.exists("products.csv"):
    logger.info("📥 No products.csv found - auto-syncing from feed...")
    do_sync()
else:
    try:
        bot.load_products()
    except Exception:
        logger.warning("⚠️ Could not load products at startup:")
        logger.warning(traceback.format_exc())

scheduler = BackgroundScheduler()
scheduler.add_job(do_sync, "interval", hours=6, id="product_sync")
scheduler.start()

setup_analytics_routes(app)

# ==================== AUTH ROUTES ====================


@app.route("/login")
def login_page():
    """Login page - request magic link"""
    return render_template("login.html")


@app.route("/logout", methods=["POST", "GET"])
def logout():
    """Logout - clear session"""
    email = session.get('email', 'Unknown')
    session.clear()
    logger.info(f"👋 User logged out: {email}")
    return redirect(url_for('login_page'))


@app.route("/api/session/info")
def session_info():
    """Get current session info (for frontend)"""
    if 'user_id' not in session:
        return jsonify({"authenticated": False}), 401

    return jsonify({
        "authenticated": True,
        "user_id": session.get('user_id'),
        "email": session.get('email'),
        "role": session.get('role'),
        "is_admin": session.get('admin_authenticated', False)
    }), 200


# ==================== ADMIN AUTHENTICATION (OPTIONAL) ====================

# DUPĂ:
@app.route("/api/admin/authenticate", methods=["POST"])
@limiter.limit("5 per minute")
def authenticate_admin():
    try:
        from werkzeug.security import check_password_hash

        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "Email și parolă sunt obligatorii"}), 400

        # Get user from database
        user = db.get_user_by_email(email)

        if not user:
            logger.warning(f"⚠️ Login attempt for non-existent user: {email}")
            return jsonify({"error": "Email sau parolă incorectă"}), 401

        # Check password
        password_hash = user.get('password_hash')

        if not password_hash:
            logger.warning(f"⚠️ User {email} has no password set")
            return jsonify({"error": "Cont fără parolă configurată"}), 401

        # Verify password
        if not check_password_hash(password_hash, password):
            logger.warning(f"⚠️ Incorrect password for user: {email}")
            return jsonify({"error": "Email sau parolă incorectă"}), 401

        # ✅ SET USER SESSION
        session.permanent = True
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['role'] = user['role']
        session['admin_authenticated'] = True
        logger.info(
            f"✅ User authenticated: {user['email']} from {request.remote_addr}")

        return jsonify({
            "status": "success",
            "message": "Autentificare reușită"
        }), 200

    except Exception as e:
        logger.error(f"❌ Admin auth error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ==================== ROUTES ====================

@app.route("/")
@require_login  # ✅ REQUIRE LOGIN
def home():
    return render_template("index.html")


@app.route("/widget")
def widget():
    """Widget route - NO LOGIN REQUIRED - for iframe embedding"""
    logger.info(
        f"Widget accessed from {request.remote_addr} - User-Agent: {request.headers.get('User-Agent', 'Unknown')}")
    logger.info(
        f"Widget session check - user_id in session: {'user_id' in session}")
    return render_template("widget.html")


@app.route("/admin")
@require_login  # ✅ REQUIRE LOGIN
def admin():
    return render_template("admin.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "products_loaded": len(getattr(bot, "products", [])),
        "timestamp": datetime.now().isoformat(),
        "scheduler_running": bool(scheduler.running)
    }), 200

# ==================== CHAT API ====================


@app.route("/api/chat", methods=["POST"])
@limiter.limit("30 per minute")
def chat():
    """Chat API - NO LOGIN REQUIRED - public access for widget"""
    try:
        logger.info(
            f"Chat request from {request.remote_addr} - Origin: {request.headers.get('Origin', 'N/A')}")

        data = request.get_json(silent=True) or {}
        user_message = (data.get("message") or "").strip()
        session_id = data.get("session_id")
        api_key = (data.get("api_key") or "").strip()

        if not user_message:
            return jsonify({"response": "Te rog scrie un mesaj.", "status": "error"}), 400

        # =========================
        # SAAS: VALIDARE TENANT (optional)
        # =========================
        tenant = None
        if api_key != "":
            tenant = db.get_tenant_by_api_key(api_key)
            if not tenant:
                return jsonify({"response": "API key invalid.", "status": "error"}), 403

        tenant_id = tenant["id"] if tenant else "default"

        # =========================
        # BOT RESPONSE
        # =========================
        response = bot.get_response(
            user_message,
            session_id=session_id,
            user_ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")
        )

        if isinstance(response, str):
            try:
                response = json.loads(response)
            except Exception:
                response = {"response": response, "status": "success"}

        if not isinstance(response, dict):
            response = {
                "response": "Eroare internă (format răspuns).", "status": "error"}

        # =========================
        # SAVE CONVERSATION (tenant-aware)
        # ===========================
        try:
            db.save_conversation(
                session_id=session_id or f"session_{int(datetime.now().timestamp())}",
                user_message=user_message,
                bot_response=response.get("response", ""),
                user_ip=request.remote_addr,
                user_agent=request.headers.get("User-Agent", ""),
                tenant_id=tenant_id
            )
        except Exception:
            logger.warning("⚠️ Failed to save conversation:")
            logger.warning(traceback.format_exc())

        if response.get("status") == "rate_limited":
            return jsonify(response), 429

        return jsonify(response), 200

    except Exception:
        logger.error("❌ Chat error:")
        logger.error(traceback.format_exc())
        return jsonify({
            "response": "A apărut o eroare. Te rog încearcă din nou.",
            "status": "error"
        }), 500

# ==================== CONFIG API ====================


@app.route("/api/config")
def get_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        return jsonify(config), 200
    except FileNotFoundError:
        return jsonify({
            "logistics": {},
            "occasions": [],
            "faq": [],
            "custom_rules": []
        }), 200
    except Exception:
        logger.error("❌ Config error:")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Config error"}), 500


@app.route("/api/admin/save-config", methods=["POST"])
@require_admin  # ✅ REQUIRE ADMIN SESSION
@limiter.limit("10 per minute")
def save_config():
    try:
        data = request.get_json(silent=True) or {}
        config = data.get("config", data)

        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        bot.load_config()
        logger.info("✅ Config saved successfully")
        return jsonify({"status": "success", "message": "Config salvat!"}), 200

    except Exception:
        logger.error("❌ Save config error:")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Save config error"}), 500

# ==================== PRODUCTS API ====================


@app.route("/api/admin/upload-products", methods=["POST"])
@require_admin  # ✅ REQUIRE ADMIN SESSION
@limiter.limit("5 per minute")
def upload_products():
    try:
        if "file" not in request.files:
            return jsonify({"error": "Niciun fișier selectat"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "Niciun fișier selectat"}), 400

        if not file.filename.endswith(".csv"):
            return jsonify({"error": "Doar fișiere CSV sunt acceptate"}), 400

        file.save("products.csv")
        bot.load_products()

        logger.info(f"✅ Products uploaded: {len(bot.products)} products")
        return jsonify({
            "status": "success",
            "message": "Produse încărcate cu succes!",
            "products_count": len(bot.products)
        }), 200

    except Exception:
        logger.error("❌ Upload error:")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Upload error"}), 500


@app.route("/api/admin/check-products")
@require_admin  # ✅ REQUIRE ADMIN SESSION
def check_products():
    try:
        file_exists = os.path.exists("products.csv")
        file_size = os.path.getsize("products.csv") if file_exists else 0

        sample = []
        for p in bot.products[:5]:
            sample.append({
                "name": p[0] if len(p) > 0 else "",
                "price": p[1] if len(p) > 1 else 0,
                "stock": p[3] if len(p) > 3 else 0,
                "link": p[4] if len(p) > 4 else ""
            })

        return jsonify({
            "file_exists": file_exists,
            "file_size": file_size,
            "bot_products_count": len(bot.products),
            "bot_products_sample": sample
        }), 200

    except Exception:
        logger.error("❌ Check products error:")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Check products error"}), 500


@app.route("/api/admin/sync-feed", methods=["POST"])
@require_admin  # ✅ REQUIRE ADMIN SESSION
@limiter.limit("2 per minute")
def sync_feed():
    try:
        logger.info("🔄 Manual feed sync triggered...")
        result = sync_products_from_feed()

        if result.get("status") == "success":
            bot.load_products()
            result["bot_products_loaded"] = len(bot.products)
            logger.info(
                f"✅ Manual feed sync complete - {result.get('products_count')} products")

        return jsonify(result), 200 if result.get("status") == "success" else 500

    except Exception:
        logger.error("❌ Feed sync error:")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Feed sync error"}), 500


# ==================== SYNC HISTORY ====================

@app.route('/api/admin/sync-history', methods=['GET'])
@require_admin  # ✅ REQUIRE ADMIN SESSION
def sync_history():
    """Get sync history from database"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, last_sync, products_count, status, error_message 
            FROM sync_log
            WHERE tenant_id = 'default'
            ORDER BY last_sync DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()

        return jsonify([dict(row) for row in rows]), 200

    except Exception as e:
        logger.error(f"❌ Sync history error: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== ANALYTICS ROUTES ====================
# (Keep existing setup_analytics_routes but update to use session auth)


# ==================== ERROR HANDLERS ====================


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "response": "⚠️ Prea multe cereri. Te rog așteaptă un minut și încearcă din nou.",
        "status": "rate_limited"
    }), 429


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Pagină negăsită"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Eroare internă de server"}), 500

# ==================== SHUTDOWN ====================


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()


atexit.register(shutdown_scheduler)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
