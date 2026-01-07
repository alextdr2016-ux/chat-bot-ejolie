from flask import Flask, render_template, request, jsonify
import json
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from chatbot import bot
import pandas as pd

load_dotenv()

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
config_data = {}


def load_config():
    """Încarcă config.json"""
    global config_data
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        logger.info("✅ Config loaded")
    except Exception as e:
        logger.error(f"❌ Config load error: {e}")
        config_data = {}


def count_conversations():
    """Numără total conversații"""
    try:
        with open('conversations.json', 'r', encoding='utf-8') as f:
            conversations = json.load(f)
        return len(conversations)
    except:
        return 0


load_config()


# ==================== ROUTES ====================

@app.route('/', methods=['GET'])
def index():
    """Serve chatbot frontend"""
    return render_template('index.html')


@app.route('/admin', methods=['GET'])
def admin():
    """Serve admin panel"""
    return render_template('admin.html')


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "products_loaded": len(bot.products),
        "total_conversations": count_conversations(),
        "version": "1.0.0"
    }), 200


@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint - process user message"""
    data = request.json
    user_message = data.get('message', '').strip()

    if not user_message:
        logger.warning("⚠️ Empty message received")
        return jsonify({"response": "Please write a message", "status": "error"}), 400

    logger.info(f"📨 Message: {user_message[:50]}...")

    try:
        bot_response = bot.get_response(user_message)
        logger.info(f"✅ Response sent - Status: {bot_response['status']}")

        return jsonify({
            "response": bot_response['response'],
            "status": bot_response['status']
        }), 200

    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        return jsonify({
            "response": "An error occurred. Please try again.",
            "status": "error"
        }), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get configuration"""
    load_config()
    logger.info("ℹ️ Config requested")
    return jsonify(config_data), 200


@app.route('/api/admin/save-config', methods=['POST'])
def save_config():
    """Save configuration - requires admin password"""
    password = request.headers.get('X-Admin-Password')
    if password != ADMIN_PASSWORD:
        logger.warning("⚠️ Unauthorized save-config attempt")
        return jsonify({"error": "Wrong password"}), 401

    data = request.json
    new_config = data.get('config', {})

    try:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=2, ensure_ascii=False)

        load_config()
        bot.load_config()

        logger.info("✅ Config saved successfully")
        return jsonify({"status": "success", "message": "Salvat cu succes!"}), 200

    except Exception as e:
        logger.error(f"❌ Config save error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get conversations - requires admin password"""
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        logger.warning("⚠️ Unauthorized conversations access")
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with open('conversations.json', 'r', encoding='utf-8') as f:
            conversations = json.load(f)
        logger.info(f"✅ Fetched {len(conversations)} conversations")
        return jsonify(conversations), 200
    except FileNotFoundError:
        logger.info("ℹ️ No conversations file found")
        return jsonify([]), 200
    except Exception as e:
        logger.error(f"❌ Conversations fetch error: {e}")
        return jsonify([]), 200


@app.route('/api/admin/upload-products', methods=['POST'])
def upload_products():
    """Upload and SYNC products CSV file - replaces old products"""
    password = request.headers.get('X-Admin-Password')
    if password != ADMIN_PASSWORD:
        logger.warning("⚠️ Unauthorized upload attempt")
        return jsonify({"error": "Wrong password"}), 401

    try:
        # Check file exists
        if 'file' not in request.files:
            logger.warning("⚠️ No file in upload request")
            return jsonify({"error": "No file selected"}), 400

        file = request.files['file']

        if file.filename == '':
            logger.warning("⚠️ Empty filename")
            return jsonify({"error": "Empty filename"}), 400

        # Validate CSV extension
        if not file.filename.endswith('.csv'):
            logger.warning(f"⚠️ Invalid file type: {file.filename}")
            return jsonify({"error": "Only CSV files allowed"}), 400

        # Save temporary file
        temp_path = 'products_temp.csv'
        file.save(temp_path)
        logger.info(f"📁 Temp file saved: {temp_path}")

        # Validate CSV structure
        try:
            df = pd.read_csv(temp_path, encoding='utf-8')
        except:
            # Try different encoding
            df = pd.read_csv(temp_path, encoding='latin-1')

        required_columns = ['Nume', 'Pret vanzare (cu promotie)', 'Descriere']
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
            import os as os_module
            os_module.remove(temp_path)
            logger.error(f"❌ Missing columns: {missing}")
            return jsonify({"error": f"Missing columns: {', '.join(missing)}"}), 400

        # Count old products
        old_count = len(bot.products) if bot.products else 0

        # Replace old file with new one (FULL SYNC)
        import os as os_module
        if os_module.path.exists('products.csv'):
            os_module.remove('products.csv')
            logger.info("📁 Old products.csv deleted")

        os_module.rename(temp_path, 'products.csv')
        logger.info("📁 New products.csv uploaded")

        # Reload products in bot
        bot.load_products()

        new_count = len(bot.products)
        removed_count = old_count - new_count
        added_or_updated = new_count

        logger.info(
            f"✅ Products synced - Old: {old_count}, New: {new_count}, Removed: {removed_count}")

        return jsonify({
            "status": "success",
            "message": f"Synced! {added_or_updated} products loaded, {removed_count} removed",
            "products_count": new_count,
            "old_count": old_count,
            "removed_count": removed_count
        }), 200

    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== ERROR HANDLERS ====================


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    logger.warning(f"⚠️ 404 error: {request.path}")
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"❌ 500 error: {error}")
    return jsonify({"error": "Server error"}), 500


# ==================== STARTUP ====================

if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("🚀 Starting Ejolie ChatBot...")
    logger.info("=" * 50)
    logger.info(f"📦 Products loaded: {len(bot.products)}")
    logger.info(f"💬 Conversations: {count_conversations()}")
    logger.info(
        f"⚙️ Admin password: {'SET' if ADMIN_PASSWORD != 'admin123' else 'DEFAULT'}")
    logger.info("=" * 50)

    port = int(os.environ.get('PORT', 3000))
    logger.info(f"🌐 Running on port {port}")

    app.run(debug=False, host='0.0.0.0', port=port)
