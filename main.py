from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from chatbot import bot

load_dotenv()

app = Flask(__name__)

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
config_data = {}


def load_config():
    """Încarcă config.json"""
    global config_data
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except:
        config_data = {}


load_config()


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/admin', methods=['GET'])
def admin():
    return render_template('admin.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')

    print(f"📨 User message: {user_message}")

    try:
        bot_response = bot.get_response(user_message)
        print(f"🤖 Bot response: {bot_response['response']}")

        return jsonify({
            "response": bot_response['response'],
            "status": "success"
        })
    except Exception as e:
        print(f"❌ Eroare: {e}")
        return jsonify({"response": f"❌ Eroare: {str(e)}", "status": "error"})


@app.route('/api/config', methods=['GET'])
def get_config():
    load_config()
    return jsonify(config_data)


@app.route('/api/admin/save-config', methods=['POST'])
def save_config():
    password = request.headers.get('X-Admin-Password')
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Wrong password"}), 401

    data = request.json
    new_config = data.get('config', {})

    try:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=2, ensure_ascii=False)

        load_config()
        bot.load_config()

        return jsonify({"status": "success", "message": "Salvat cu succes!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Obține conversații - PROTEJAT cu parola"""
    password = request.args.get('password')
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with open('conversations.json', 'r', encoding='utf-8') as f:
            conversations = json.load(f)
        return jsonify(conversations)
    except:
        return jsonify([])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(debug=False, host='0.0.0.0', port=port)
