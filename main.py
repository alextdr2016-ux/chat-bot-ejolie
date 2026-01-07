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


def serialize_product(product):
    """
    Convert product object to JSON-serializable dict
    Auto-detects product structure (tuple, dict, or object)
    """
    try:
        # Case 1: Tuple/List format: (name, price, description, stock)
        if isinstance(product, (tuple, list)):
            if len(product) >= 4:
                return {
                    'name': str(product[0]) if product[0] else '',
                    'price': float(product[1]) if product[1] else 0,
                    'description': str(product[2]) if product[2] else '',
                    'stock': int(product[3]) if product[3] else 0
                }
            elif len(product) >= 3:
                return {
                    'name': str(product[0]) if product[0] else '',
                    'price': float(product[1]) if product[1] else 0,
                    'description': str(product[2]) if product[2] else '',
                    'stock': 0
                }

        # Case 2: Dictionary format
        if isinstance(product, dict):
            return {
                'name': str(product.get('name', product.get('Nume', ''))),
                'price': float(product.get('price', product.get('Pret vanzare (cu promotie)', 0)) or 0),
                'description': str(product.get('description', product.get('Descriere', ''))),
                'stock': int(product.get('stock', product.get('stoc', 0)) or 0)
            }

        # Case 3: Object with attributes
        if hasattr(product, '__dict__'):
            obj_dict = vars(product)
            return {
                'name': str(obj_dict.get('name', obj_dict.get('Nume', ''))),
                'price': float(obj_dict.get('price', obj_dict.get('Pret vanzare (cu promotie)', 0)) or 0),
                'description': str(obj_dict.get('description', obj_dict.get('Descriere', ''))),
                'stock': int(obj_dict.get('stock', obj_dict.get('stoc', 0)) or 0)
            }

        # Case 4: String representation
        return {
            'name': str(product),
            'price': 0,
            'description': '',
            'stock': 0
        }

    except Exception as e:
        logger.warning(f"⚠️ Error serializing product: {e}")
        return {
            'name': 'Error',
            'price': 0,
            'description': str(e),
            'stock': 0
        }


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
    """Upload and SYNC products CSV file - FULL DEBUG"""
    import os as os_module

    password = request.headers.get('X-Admin-Password')
    if password != ADMIN_PASSWORD:
        logger.warning("⚠️ Unauthorized upload attempt")
        return jsonify({"error": "Wrong password"}), 401

    try:
        logger.info("=" * 60)
        logger.info("🟢 UPLOAD PRODUCTS - START")
        logger.info("=" * 60)

        # Check file exists
        if 'file' not in request.files:
            logger.error("❌ No file in request.files")
            return jsonify({"error": "No file selected"}), 400

        file = request.files['file']
        logger.info(f"📁 File received: {file.filename}")

        if file.filename == '':
            logger.error("❌ Empty filename")
            return jsonify({"error": "Empty filename"}), 400

        # Validate CSV extension
        if not file.filename.endswith('.csv'):
            logger.error(f"❌ Invalid file type: {file.filename}")
            return jsonify({"error": "Only CSV files allowed"}), 400

        # Save temporary file
        temp_path = 'products_temp.csv'
        logger.info(f"💾 Saving to temp: {temp_path}")
        file.save(temp_path)

        # Verify temp file exists
        if not os_module.path.exists(temp_path):
            logger.error(f"❌ Temp file NOT created at {temp_path}")
            return jsonify({"error": "Failed to save temp file"}), 500

        temp_size = os_module.path.getsize(temp_path)
        logger.info(f"✅ Temp file created - Size: {temp_size} bytes")

        # Read CSV
        logger.info("📖 Reading CSV...")
        try:
            df = pd.read_csv(temp_path, encoding='utf-8')
            logger.info(
                f"✅ CSV read OK - Rows: {len(df)}, Columns: {list(df.columns)}")
        except Exception as e:
            logger.error(f"❌ UTF-8 failed: {e}, trying latin-1...")
            try:
                df = pd.read_csv(temp_path, encoding='latin-1')
                logger.info(f"✅ CSV read OK (latin-1) - Rows: {len(df)}")
            except Exception as e2:
                logger.error(f"❌ CSV read failed: {e2}")
                os_module.remove(temp_path)
                return jsonify({"error": f"Invalid CSV: {e2}"}), 400

        # Validate columns
        required_columns = ['Nume', 'Pret vanzare (cu promotie)', 'Descriere']
        logger.info(f"🔍 Checking columns: {required_columns}")

        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            logger.error(f"❌ Missing columns: {missing}")
            logger.error(f"   Available: {list(df.columns)}")
            os_module.remove(temp_path)
            return jsonify({"error": f"Missing columns: {missing}"}), 400

        logger.info(f"✅ All required columns found")

        # Check data
        if len(df) == 0:
            logger.error("❌ CSV is empty")
            os_module.remove(temp_path)
            return jsonify({"error": "CSV file is empty"}), 400

        logger.info(f"✅ CSV has {len(df)} rows of data")

        # Count old
        old_count = len(bot.products)
        logger.info(f"📊 Old products count: {old_count}")

        # Delete old file
        products_path = 'products.csv'
        if os_module.path.exists(products_path):
            logger.info(f"🗑️ Deleting old {products_path}")
            try:
                os_module.remove(products_path)
                logger.info(f"✅ Old file deleted")
            except Exception as e:
                logger.error(f"❌ Failed to delete: {e}")
                os_module.remove(temp_path)
                return jsonify({"error": f"Cannot delete old file: {e}"}), 500

        # Move temp to final
        logger.info(f"📤 Moving {temp_path} → {products_path}")
        try:
            os_module.rename(temp_path, products_path)
            logger.info(f"✅ File renamed successfully")
        except Exception as e:
            logger.error(f"❌ Rename failed: {e}")
            if os_module.path.exists(temp_path):
                os_module.remove(temp_path)
            return jsonify({"error": f"Cannot rename file: {e}"}), 500

        # Verify final file exists and has size
        if not os_module.path.exists(products_path):
            logger.error(f"❌ Final file NOT found at {products_path}")
            return jsonify({"error": "File was not saved"}), 500

        final_size = os_module.path.getsize(products_path)
        logger.info(f"✅ Final file exists - Size: {final_size} bytes")

        # Reload bot
        logger.info("🤖 Reloading products in bot...")
        try:
            bot.load_products()
            logger.info(f"✅ Bot reloaded")
        except Exception as e:
            logger.error(f"❌ Reload failed: {e}")
            return jsonify({"error": f"Failed to reload: {e}"}), 500

        # Verify new count
        new_count = len(bot.products)
        removed_count = old_count - new_count

        logger.info(f"📊 New products count: {new_count}")
        logger.info(f"📊 Removed: {removed_count}")

        if new_count == 0:
            logger.error("❌ NO PRODUCTS LOADED!")
            return jsonify({
                "status": "error",
                "message": "No products loaded. Check CSV format.",
                "products_count": 0
            }), 400

        logger.info("=" * 60)
        logger.info(f"✅ SUCCESS - Synced {new_count} products")
        logger.info("=" * 60)

        return jsonify({
            "status": "success",
            "message": f"Synced! {new_count} products loaded, {removed_count} removed",
            "products_count": new_count,
            "old_count": old_count,
            "removed_count": removed_count
        }), 200

    except Exception as e:
        logger.error(f"❌ UNEXPECTED ERROR: {e}")
        return jsonify({"error": f"Error: {str(e)}"}), 500


@app.route('/api/admin/check-products', methods=['GET'])
def check_products():
    """Debug endpoint - check products status with proper JSON serialization"""
    import os as os_module

    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        logger.warning("⚠️ Unauthorized check-products attempt")
        return jsonify({"error": "Unauthorized"}), 401

    products_path = 'products.csv'

    try:
        logger.info("🔍 Checking products status...")

        # Check if file exists
        file_exists = os_module.path.exists(products_path)

        # Get file size
        file_size = 0
        if file_exists:
            try:
                file_size = int(os_module.path.getsize(products_path))
                logger.info(f"✅ File exists - Size: {file_size} bytes")
            except Exception as e:
                logger.warning(f"⚠️ Cannot get file size: {e}")
                file_size = 0
        else:
            logger.warning(f"⚠️ File not found at {products_path}")

        # Get product count
        bot_products_count = 0
        try:
            bot_products_count = int(len(bot.products))
            logger.info(f"✅ Products loaded: {bot_products_count}")
        except Exception as e:
            logger.warning(f"⚠️ Cannot get product count: {e}")
            bot_products_count = 0

        # Get sample products (first 2)
        bot_products_sample = []
        try:
            if bot.products and len(bot.products) > 0:
                # Serialize each product properly
                sample_products = bot.products[:2]
                bot_products_sample = [
                    serialize_product(p) for p in sample_products]
                logger.info(
                    f"✅ Sample products prepared: {len(bot_products_sample)}")
                logger.info(
                    f"📦 Sample 1: {bot_products_sample[0] if bot_products_sample else 'None'}")
                if len(bot_products_sample) > 1:
                    logger.info(f"📦 Sample 2: {bot_products_sample[1]}")
            else:
                logger.info("ℹ️ No products available")
                bot_products_sample = []
        except Exception as e:
            logger.warning(f"⚠️ Error preparing sample products: {e}")
            bot_products_sample = []

        # Build response
        response = {
            "file_exists": bool(file_exists),
            "file_size": file_size,
            "bot_products_count": bot_products_count,
            "bot_products_sample": bot_products_sample
        }

        logger.info(f"✅ Response ready: {response}")

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"❌ Check products error: {e}", exc_info=True)
        return jsonify({
            "error": str(e),
            "file_exists": False,
            "file_size": 0,
            "bot_products_count": 0,
            "bot_products_sample": []
        }), 500


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
