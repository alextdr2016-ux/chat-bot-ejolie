import pandas as pd
import openai
import json
import logging
import os
import re
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

    def extract_price_range(self, query):
        """Extract price range from query like 'sub 500' or 'sub 300 lei'"""
        # Match patterns like: "sub 500", "sub 300 lei", "pana la 500", "mai ieftin de 600"
        patterns = [
            r'sub\s+(\d+)',
            r'pana\s+la\s+(\d+)',
            r'mai\s+ieftin\s+de\s+(\d+)',
            r'under\s+(\d+)',
            r'(\d+)\s+ron',
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return float(match.group(1))

        return None

    def search_products(self, query, limit=3, max_price=None):
        """Search products by name/description and optional price"""
        if not self.products:
            return []

        query_lower = query.lower()
        results = []

        for product in self.products:
            name = product[0].lower() if product[0] else ''
            desc = product[2].lower() if product[2] else ''
            price = product[1]

            score = 0
            if query_lower in name:
                score += 10
            if query_lower in desc:
                score += 5

            # ✅ Price filtering
            if max_price is not None and price > max_price:
                score = 0  # Exclude products over budget

            if score > 0:
                results.append((product, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in results[:limit]]

    def is_in_stock(self, product):
        if len(product) >= 4:
            return product[3] > 0
        return True

    def search_products_in_stock(self, query, limit=3):
        """Search with smart price extraction"""
        # ✅ Extract price limit from query
        max_price = self.extract_price_range(query)

        all_results = self.search_products(
            query, limit * 2, max_price=max_price)

        if all_results:
            in_stock = [p for p in all_results if self.is_in_stock(p)]
            if in_stock:
                return in_stock[:limit]
            else:
                # Fallback: show all matching products even if out of stock
                logger.warning(
                    f"⚠️ No in-stock products for '{query}', showing all matches")
                return all_results[:limit]

        return []

    def get_delivery_time(self, product_name):
        """Return delivery time based on brand"""
        # ✅ Check if it's a Trendya brand product
        if product_name and 'trendya' in product_name.lower():
            return "5-7 zile lucrătoare"
        else:
            return "1-2 zile lucrătoare"

    def format_product(self, product):
        """Format product with delivery time"""
        if not product or len(product) < 3:
            return "Produs nedisponibil"

        name = product[0]
        price = product[1]
        desc = product[2]
        stock = product[3] if len(product) >= 4 else 1
        link = product[4] if len(product) >= 5 else ""

        stock_status = "✅ În stoc" if stock > 0 else "⚠️ Epuizat"
        delivery_time = self.get_delivery_time(name)

        if link:
            return f"🎀 **{name}** - {price} RON [{stock_status}]\n📝 {desc}\n⏱️ Livrare: {delivery_time}\n🔗 {link}"
        else:
            return f"🎀 **{name}** - {price} RON [{stock_status}]\n📝 {desc}\n⏱️ Livrare: {delivery_time}"

    def format_products_for_context(self, products):
        if not products:
            return "Niciun produs găsit în criteriile tale."

        return "\n\n".join(self.format_product(p) for p in products)

    def get_response(self, user_message, session_id=None, user_ip=None, user_agent=None):
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"📩 Chat request: {user_message[:50]}...")

        try:
            products = self.search_products_in_stock(user_message, limit=3)
            products_context = self.format_products_for_context(products)

            # ✅ FIX: Initialize variables from config BEFORE using them in prompt
            return_policy = self.config.get('logistics', {}).get('return_policy',
                                                                 'Retur în 30 de zile calendaristice')

            faq_list = self.config.get('faq', [])
            faq_text = "\n".join([f"Q: {f.get('question', '')}\nA: {f.get('answer', '')}"
                                  for f in faq_list]) if faq_list else "Nu sunt FAQ disponibile"

            rules_list = self.config.get('custom_rules', [])
            custom_rules_text = "\n".join([f"- {r.get('title', '')}: {r.get('content', '')}"
                                           for r in rules_list]) if rules_list else "Nu sunt reguli custom"

            # ✅ NOUL PROMPT GPT - cu delivery time
            system_prompt = f"""Tu ești Maria, asistentul virtual al magazinului online ejolie.ro, care vinde rochii pentru femei.

INSTRUCȚIUNI CRITICE:
1. RĂSPUNZI DOAR LA ÎNTREBĂRI DESPRE ROCHII, PRETURI, COMENZI, LIVRARE ȘI RETUR
2. Dacă intrebarea nu e legata de rochii, cere politicos sa reformuleze
3. Fii prietenos si helpful in toate raspunsurile

IMPORTANT - AFISEAZA PRODUSELE CU NUMELE EXACT DIN LISTA SI LINK-URILE!
- NU rescrii sau parafrazezi numele produselor!
- INCLUDE LINK-URI pentru fiecare produs
- INCLUDE TIMP LIVRARE: "⏱️ Livrare: 5-7 zile (Trendya) sau 1-2 zile (altele)"
- Arată: "Rochie Florence aurie - 662.5 RON [În stoc]\\n📝 Descriere...\\n⏱️ Livrare: 1-2 zile\\n🔗 https://ejolie.ro/produs"

📌 **Informații fixe pe care le știi:**
- Cost livrare: **19 lei** oriunde în România
- Transport gratuit pentru comenzi peste **200 lei**
- Termen livrare: **5–7 zile lucrătoare** pentru produsele cu Brandul Trendya, pentru restul **1-2 zile**
- Retur: posibil în **14 zile** calendaristice
- Email contact: **contact@ejolie.ro**
- Website: **https://ejolie.ro**

Politica retur: {return_policy}

PRODUSE DISPONIBILE:
{products_context}

INFORMAȚII FRECVENTE:
{faq_text}

REGULI CUSTOM:
{custom_rules_text}

STIL DE COMUNICARE:
- Foloseste emoji (🎀, 👗, ✅, 🔗, ⏱️, etc.)
- Fii prietenos și helpful
- Dă răspunsuri concise (max 3-4 linii)
- INCLUDE NAMES EXACTE din lista de produse
- INCLUDE LINK-URI și TIMP LIVRARE pentru fiecare produs
- Sugerează alte rochii dacă nu găsești exact ce caută
- Întreabă despre ocazie pentru recomandări mai bune

EXEMPLE DE RĂSPUNSURI CORECTE:
✅ "🎀 Desigur! Iată 2 opțiuni sub 700 RON:
   1. Rochie Florence aurie - 662.5 RON [În stoc]
   📝 Elegantă și luminoasă...
   ⏱️ Livrare: 1-2 zile
   🔗 https://ejolie.ro/product/rochie-florence-aurie-12344
   
   2. Rochie Florence neagra - 662.5 RON [În stoc]
   📝 Clasică și misterioasă...
   ⏱️ Livrare: 1-2 zile
   🔗 https://ejolie.ro/product/rochie-florence-neagra-12343"

RĂSPUNSURI TIPICE:
- Pentru căutări cu filtru (culoare, preț): Afișează produse relevante cu NUME EXACT, preț, stoc, LIVRARE ȘI LINK-URI
- Pentru preturi: Confirmă preț și adaugă info despre livrare
- Pentru comenzi: Explică procesul și oferi contact
- Pentru retur: Menționează politica de 14 zile pasii necesari si numarul de telefon.
- Pentru intrebari nelinistite: "Scuze, nu inteleg bine. Poti reformula?"
"""

            logger.info("🔄 Calling GPT-4o...")

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

            # Save to database
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
            db.save_conversation(
                session_id, user_message, "Rate limit", user_ip, user_agent, False
            )
            return {
                "response": "⏳ Prea multe cereri. Te rog așteaptă câteva secunde.",
                "status": "rate_limited",
                "session_id": session_id
            }

        except openai.AuthenticationError as e:
            logger.error(f"❌ OpenAI Auth error: {e}")
            db.save_conversation(
                session_id, user_message, "Auth failed", user_ip, user_agent, False
            )
            return {
                "response": "❌ Eroare de autentificare. Verifică OPENAI_API_KEY.",
                "status": "auth_error",
                "session_id": session_id
            }

        except Exception as e:
            logger.error(f"❌ GPT error: {type(e).__name__}: {e}")
            db.save_conversation(
                session_id, user_message, f"Error: {str(e)}", user_ip, user_agent, False
            )
            return {
                "response": "⚠️ Eroare temporară. Te rog încearcă din nou.",
                "status": "error",
                "session_id": session_id
            }


# ✅ Instanțierea chatbotului
bot = ChatBot()
