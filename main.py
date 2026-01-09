from analytics_api import setup_analytics_routes
import uuid
from datetime import datetime
import logging
import os
import json
from sync_feed import sync_products_from_feed
from apscheduler.schedulers.background import BackgroundScheduler
from chatbot import bot
from flask_limiter.util import get_remote_address
from flask_limiter import Limiter
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
import atexit
from dotenv import load_dotenv

load_dotenv()

# ==================== APP SETUP ====================
app = Flask(__name__)

# ✅ FIX 1: ProxyFix (Railway, fără Cloudflare)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Setup analytics routes
setup_analytics_routes(app)

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== RATE LIMITING ====================
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

logger.info("🔒 Rate limiting: ENABLED")

# ==================== CONFIG ====================
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

if ADMIN_PASSWORD == 'admin123':
    logger.warning("⚠️ SECURITY WARNING: Using default admin password!")

# ==================== AUTO SYNC ====================


def do_sync():
    try:
        logger.info("🔄 Starting product sync...")
        result = sync_products_from_feed()
        if result.get("status") == "success":
            bot.load_products()
            logger.info(
                f"✅ Sync complete: {result['products_count']} products")
            return True
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
    return False


logger.info("🚀 Starting Ejolie ChatBot Server...")
do_sync()

scheduler = BackgroundScheduler()
scheduler.add_job(do_sync, 'interval', hours=6, id='product_sync')
scheduler.start()

# ==================== ROUTES ====================


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/admin')
def admin():
    return render_template('admin.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "products_loaded": len(bot.products),
        "timestamp": datetime.now().isoformat(),
        "scheduler_running": scheduler.running
    })

# ==================== CHAT API ====================


@app.route('/api/chat', methods=['POST'])
@limiter.limit("30 per minute")  # ⬅️ puțin mai realist
def chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"response": "Date invalide.", "status": "error"}), 400

        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')

        if not user_message:
            return jsonify({"response": "Te rog scrie un mesaj.", "status": "error"}), 400

        response = bot.get_response(
            user_message,
            session_id=session_id,
            user_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )

        # ✅ FIX 2: Safety net — bot nu are voie să întoarcă string
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except Exception:
                response = {"response": response, "status": "success"}

        # ✅ FIX 3: rate_limited = HTTP 429 REAL
        if response.get("status") == "rate_limited":
            return jsonify(response), 429

        return jsonify(response)

    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        return jsonify({
            "response": "A apărut o eroare. Te rog încearcă din nou.",
            "status": "error"
        }), 500

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
