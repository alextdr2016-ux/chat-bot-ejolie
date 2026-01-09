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

            # ✅ FIX: safe stock conversion (NaN handling)
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

    def search_products(self, query, limit=3):
        if not self.products:
            return []

        query_lower = query.lower()
        results = []

        for product in self.products:
            name = product[0].lower() if product[0] else ''
            desc = product[2].lower() if product[2] else ''

            score = 0
            if query_lower in name:
                score += 10
            if query_lower in desc:
                score += 5

            if score > 0:
                results.append((product, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in results[:limit]]

    def is_in_stock(self, product):
        if len(product) >= 4:
            return product[3] > 0
        return True

    def search_products_in_stock(self, query, limit=3):
        all_results = self.search_products(query, limit * 2)
        in_stock = [p for p in all_results if self.is_in_stock(p)]
        return in_stock[:limit]

    def format_product(self, product):
        if not product or len(product) < 3:
            return "Produs nedisponibil"

        name = product[0]
        price = product[1]
        desc = product[2]
        stock = product[3] if len(product) >= 4 else 1
        link = product[4] if len(product) >= 5 else ""

        stock_status = "✅ În stoc" if stock > 0 else "❌ Epuizat"

        if link:
            return f"🎀 **{name}** - {price} RON [{stock_status}]\n📝 {desc}\n🔗 {link}"
        else:
            return f"🎀 **{name}** - {price} RON [{stock_status}]\n📝 {desc}"

    def format_products_for_context(self, products):
        if not products:
            return "Niciun produs găsit în stoc."

        return "\n\n".join(self.format_product(p) for p in products)

    def get_response(self, user_message, session_id=None, user_ip=None, user_agent=None):
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"📩 User message: {user_message[:50]}...")

        try:
            products = self.search_products_in_stock(user_message, limit=3)
            products_context = self.format_products_for_context(products)

            # ✅ NOUL PROMPT GPT - 100% brand Ejolie
            system_prompt = f"""
🎀 Tu ești **Maria**, asistentul virtual al magazinului online **Ejolie.ro** – specializat în rochii elegante de eveniment pentru femei.

🎯 **ROLUL TĂU**: ajuți clientele cu răspunsuri clare, rapide și prietenoase despre:
- produse (rochii, mărimi, culori, materiale)
- comenzi, plată, livrare și retur
- prețuri, reduceri, disponibilitate

📌 **Informații fixe pe care le știi:**
- Cost livrare: **19 lei** oriunde în România
- Transport gratuit pentru comenzi peste **200 lei**
- Termen livrare: **5–7** zile lucrătoare** pentru produsle cu Brandul Trendya pentru restul **1-2 zile**  
- Retur: posibil în **14 zile** calendaristice
- Email contact: **contact@ejolie.ro**
- Telefon: **0757 10 51 51**
- Website: **https://ejolie.ro**

💬 **Reguli stricte**:
1. Nu spui niciodată că nu știi – dacă întrebarea e despre Ejolie, răspunzi folosind datele de mai sus.
2. Nu redirecționezi către site („verifică pe site” ❌).
3. Nu menționezi că ești un model de limbaj sau AI.
4. Fii caldă, empatică și prietenoasă – ca o consilieră de modă.
5. Folosește emoji în răspunsuri (🎀, 👗, ✅, 🔗, 💌, 📦 etc.) pentru un ton feminin & friendly.
6. Scrie clar, concis și fără paragrafe lungi.

📦 Dacă întreabă: „Cât costă transportul?”, „Cum se face returul?”, „Cât durează livrarea?” → RĂSPUNZI direct, fără ezitare.

🛍️ Produse disponibile în stoc:
{products_context}

Ești aici să oferi o experiență de asistență excelentă pentru clientele Ejolie.ro. Tu EȘTI vocea brandului.
"""

            logger.info("🔄 Sending message to OpenAI...")

            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=300,
                temperature=0.5,
                timeout=15
            )

            bot_response = response.choices[0].message.content
            logger.info(f"✅ GPT response received")

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


# ✅ Instanțierea chatbotului
bot = ChatBot()
