import atexit
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from chatbot import bot
from apscheduler.schedulers.background import BackgroundScheduler
from sync_feed import sync_products_from_feed
import json
import os
import logging
from datetime import datetime
import uuid
from analytics_api import setup_analytics_routes

# ==================== APP SETUP ====================
app = Flask(__name__)

# Setup analytics routes
setup_analytics_routes(app)

# Configure logging
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

if ADMIN_PASSWORD == 'Sack3351*':
    logger.warning(
        "⚠️ SECURITY WARNING: Using default admin password! Set ADMIN_PASSWORD environment variable.")

# ==================== AUTO SYNC FUNCTIONS ====================


def do_sync():
    """Execută sync-ul din feed"""
    try:
        logger.info("🔄 Starting product sync from feed...")
        result = sync_products_from_feed()
        if result.get("status") == "success":
            bot.load_products()
            logger.info(
                f"✅ Sync complete: {result['products_count']} products loaded")
            return True
        else:
            logger.warning(f"⚠️ Sync returned: {result}")
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
    return False


# ==================== STARTUP SYNC ====================
logger.info("=" * 60)
logger.info("🚀 Starting Ejolie ChatBot Server...")
logger.info("=" * 60)

# Sync la pornire
logger.info("🔄 Initial sync on startup...")
do_sync()

# ==================== SCHEDULED SYNC ====================
scheduler = BackgroundScheduler()
scheduler.add_job(do_sync, 'interval', hours=6, id='product_sync')
scheduler.start()
logger.info("⏰ Scheduler active - auto-sync every 6 hours")

# ==================== STATIC FILES ====================


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/admin')
def admin():
    return render_template('admin.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# ==================== HEALTH CHECK ====================


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
@limiter.limit("10 per minute")
def chat():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"response": "Date invalide.", "status": "error"}), 400

        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')  # ← NEW

        if not user_message:
            return jsonify({"response": "Te rog să scrii un mesaj.", "status": "error"}), 400

        # Validare lungime mesaj
        if len(user_message) > 1000:
            return jsonify({
                "response": "Mesajul este prea lung. Maximum 1000 caractere.",
                "status": "error"
            }), 400

        logger.info(f"📩 Chat request: {user_message[:50]}...")

        # ← NEW: Get user info for database
        user_ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')

        # ← NEW: Pass session info to bot
        response = bot.get_response(
            user_message,
            session_id=session_id,
            user_ip=user_ip,
            user_agent=user_agent
        )

        # Bot now automatically saves to database!

        return jsonify(response)

    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        return jsonify({
            "response": "A apărut o eroare. Te rog încearcă din nou.",
            "status": "error"
        }), 500


# ==================== ANALYTICS DASHBOARD ====================


@app.route('/analytics')
def analytics_dashboard():
    """Serve analytics dashboard"""
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        return "Unauthorized", 401

    return render_template('analytics.html')


# ==================== CONFIG API ====================


@app.route('/api/config')
def get_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        return jsonify(config)
    except FileNotFoundError:
        return jsonify({
            "logistics": {},
            "occasions": [],
            "faq": [],
            "custom_rules": []
        })
    except Exception as e:
        logger.error(f"❌ Config error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/save-config', methods=['POST'])
@limiter.limit("10 per minute")
def save_config():
    # Accept password from header or body
    password = request.headers.get('X-Admin-Password')
    if not password:
        data = request.get_json()
        password = data.get('password') if data else None

    if password != ADMIN_PASSWORD:
        logger.warning("⚠️ Unauthorized config save attempt")
        return jsonify({"error": "Parolă greșită!"}), 401

    try:
        data = request.get_json()
        config = data.get('config', data)

        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        # Reload bot config
        bot.load_config()

        logger.info("✅ Config saved successfully")
        return jsonify({"status": "success", "message": "Config salvat!"})

    except Exception as e:
        logger.error(f"❌ Save config error: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== PRODUCTS API ====================


@app.route('/api/admin/upload-products', methods=['POST'])
@limiter.limit("5 per minute")
def upload_products():
    password = request.headers.get('X-Admin-Password')
    if password != ADMIN_PASSWORD:
        logger.warning("⚠️ Unauthorized upload attempt")
        return jsonify({"error": "Parolă greșită!"}), 401

    try:
        if 'file' not in request.files:
            return jsonify({"error": "Niciun fișier selectat"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"error": "Niciun fișier selectat"}), 400

        if not file.filename.endswith('.csv'):
            return jsonify({"error": "Doar fișiere CSV sunt acceptate"}), 400

        # Save file
        file.save('products.csv')

        # Reload bot products
        bot.load_products()

        logger.info(f"✅ Products uploaded: {len(bot.products)} products")

        return jsonify({
            "status": "success",
            "message": f"Produse încărcate cu succes!",
            "products_count": len(bot.products)
        })

    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/check-products')
def check_products():
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Parolă greșită!"}), 401

    try:
        file_exists = os.path.exists('products.csv')
        file_size = os.path.getsize('products.csv') if file_exists else 0

        # Get sample products
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
        })

    except Exception as e:
        logger.error(f"❌ Check products error: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== AUTO SYNC FROM FEED ====================


@app.route('/api/admin/sync-feed', methods=['POST'])
@limiter.limit("2 per minute")
def sync_feed():
    """Sync products from ejolie.ro feed"""
    password = request.headers.get('X-Admin-Password')
    if password != ADMIN_PASSWORD:
        logger.warning("⚠️ Unauthorized sync attempt")
        return jsonify({"error": "Parolă greșită!"}), 401

    try:
        logger.info("🔄 Manual feed sync triggered from admin...")
        result = sync_products_from_feed()

        if result.get("status") == "success":
            # Reload bot products
            bot.load_products()
            result["bot_products_loaded"] = len(bot.products)
            logger.info(
                f"✅ Manual feed sync complete - {result['products_count']} products")

        return jsonify(result), 200 if result.get("status") == "success" else 500

    except Exception as e:
        logger.error(f"❌ Feed sync error: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== ERROR HANDLERS ====================


@app.errorhandler(429)
def ratelimit_handler(e):
    logger.warning(f"⚠️ Rate limit exceeded: {request.remote_addr}")
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


# ==================== SHUTDOWN HANDLER ====================


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("⏰ Scheduler stopped")


atexit.register(shutdown_scheduler)

# ==================== RUN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
