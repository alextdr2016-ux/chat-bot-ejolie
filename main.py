import os
import json
import logging
import atexit
import traceback
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler

from analytics_api import setup_analytics_routes
from sync_feed import sync_products_from_feed
from chatbot import bot
from database import db  # ✅ IMPORTANT: db is used in /api/chat

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

# ==================== RATE LIMITING ====================
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)
logger.info("🔒 Rate limiting: ENABLED")

# ==================== CONFIG ====================
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
if ADMIN_PASSWORD == "admin123":
    logger.warning("⚠️ SECURITY WARNING: Using default admin password!")

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

# Auto-sync products on startup if missing
if not os.path.exists("products.csv"):
    logger.info("📥 No products.csv found - auto-syncing from feed...")
    do_sync()
else:
    # Still load products into memory
    try:
        bot.load_products()
    except Exception:
        logger.warning("⚠️ Could not load products at startup:")
        logger.warning(traceback.format_exc())

# Start scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(do_sync, "interval", hours=6, id="product_sync")
scheduler.start()

# Setup analytics routes
setup_analytics_routes(app)

# ==================== ROUTES ====================


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/admin")
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
    try:
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

        # Safety net: response must be dict
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
        # =========================
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

        # rate_limited = HTTP 429 real
        if response.get("status") == "rate_limited":
            return jsonify(response), 429

        return jsonify(response), 200

    except Exception:
        # ✅ Full traceback in Railway logs
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
@limiter.limit("10 per minute")
def save_config():
    password = request.headers.get("X-Admin-Password")
    if not password:
        data = request.get_json(silent=True) or {}
        password = data.get("password")

    if password != ADMIN_PASSWORD:
        logger.warning("⚠️ Unauthorized config save attempt")
        return jsonify({"error": "Parolă greșită!"}), 401

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
@limiter.limit("5 per minute")
def upload_products():
    password = request.headers.get("X-Admin-Password")
    if password != ADMIN_PASSWORD:
        logger.warning("⚠️ Unauthorized upload attempt")
        return jsonify({"error": "Parolă greșită!"}), 401

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
def check_products():
    password = request.args.get("password")
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Parolă greșită!"}), 401

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
@limiter.limit("2 per minute")
def sync_feed():
    password = request.headers.get("X-Admin-Password")
    if password != ADMIN_PASSWORD:
        logger.warning("⚠️ Unauthorized sync attempt")
        return jsonify({"error": "Parolă greșită!"}), 401

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
