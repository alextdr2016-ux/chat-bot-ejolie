import pandas as pd
import openai
import json
import logging
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from database import db

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')


class ChatBot:
    def __init__(self):
        self.products = []
        self.config = {}
        self.load_products()
        self.load_config()
        logger.info("🤖 ChatBot initialized")

    def load_products(self):
        if not os.path.exists('products.csv'):
            self.products = []
            return

        try:
            df = pd.read_csv('products.csv', encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv('products.csv', encoding='latin-1')

        self.products = []

        for _, row in df.iterrows():
            name = str(row.get('Nume', ''))

            try:
                price = float(row.get('Pret vanzare (cu promotie)', 0))
            except:
                price = 0.0

            desc = str(row.get('Descriere', ''))

            # ✅ FIX: safe stock conversion
            raw_stock = row.get('Stoc numeric', 0)
            try:
                if pd.isna(raw_stock):
                    stock = 0
                else:
                    stock = int(raw_stock)
            except:
                stock = 0

            link = str(row.get('Link produs', '')).strip()

            self.products.append((name, price, desc, stock, link))

    def load_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception:
            self.config = {}

    def get_response(self, user_message, session_id=None, user_ip=None, user_agent=None):
        if not session_id:
            session_id = str(uuid.uuid4())

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Ești asistentul ejolie.ro"},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=300,
                temperature=0.5,
                timeout=15
            )

            bot_response = response.choices[0].message.content

            db.save_conversation(
                session_id, user_message, bot_response, user_ip, user_agent, True
            )

            return {
                "response": bot_response,
                "status": "success",
                "session_id": session_id
            }

        except openai.RateLimitError as e:
            logger.warning(f"⚠️ OpenAI rate limit: {e}")
            return {
                "response": "⏳ Prea multe cereri. Te rog așteaptă câteva secunde.",
                "status": "rate_limited",
                "session_id": session_id
            }

        except Exception as e:
            logger.error(f"❌ GPT error: {e}")
            return {
                "response": "⚠️ Eroare temporară. Te rog încearcă din nou.",
                "status": "error",
                "session_id": session_id
            }


# ✅ Bot instanțiat
bot = ChatBot()
