import json
import pandas as pd
import os
import openai
import datetime
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')


class ChatBot:
    """Chatbot inteligent cu OpenAI GPT"""

    def __init__(self):
        self.config = {}
        self.products = []
        self.load_config()
        self.load_products()

    def load_config(self):
        """Încarcă config.json"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info("✅ Config loaded")
        except Exception as e:
            logger.error(f"❌ Config error: {e}")
            self.config = {}

    def load_products(self):
        """Încarcă produsele din CSV"""
        import os as os_module

        products_path = 'products.csv'
        logger.info(f"🔍 Trying to load from: {products_path}")
        logger.info(f"📁 File exists: {os_module.path.exists(products_path)}")

        if os_module.path.exists(products_path):
            logger.info(
                f"📊 File size: {os_module.path.getsize(products_path)} bytes")

        try:
            # Try UTF-8 first
            try:
                df = pd.read_csv(products_path, encoding='utf-8')
                logger.info(f"✅ CSV loaded (utf-8) - Rows: {len(df)}")
            except UnicodeDecodeError:
                # Fall back to latin-1
                logger.warning("⚠️ UTF-8 failed, trying latin-1...")
                df = pd.read_csv(products_path, encoding='latin-1')
                logger.info(f"✅ CSV loaded (latin-1) - Rows: {len(df)}")

            logger.info(f"📋 Columns: {list(df.columns)}")

            self.products = df.to_dict('records')
            logger.info(f"✅ Loaded {len(self.products)} products from CSV")
        except Exception as e:
            logger.error(f"❌ Products error: {e}")
            logger.error(f"📋 Stack trace: {traceback.format_exc()}")
            self.products = []

    def is_in_stock(self, product):
        """Verifică dacă produsul e în stoc"""
        try:
            stock = int(product.get('stoc', 0))
            return stock > 0
        except:
            return False

    def search_products(self, query, max_results=3):
        """Caută produse similare"""
        if not query or not self.products:
            return []

        query_lower = query.lower()
        results = []

        for product in self.products:
            try:
                nume = str(product.get('Nume', '')).lower()
                descriere = str(product.get('Descriere', '')).lower()

                score = 0
                if query_lower in nume:
                    score += 3
                if query_lower in descriere:
                    score += 1

                for word in query_lower.split():
                    if len(word) > 2:
                        if word in nume:
                            score += 2
                        if word in descriere:
                            score += 1

                if score > 0:
                    results.append((score, product))
            except Exception:
                pass

        results.sort(reverse=True, key=lambda x: x[0])
        return [p for s, p in results[:max_results]]

    def search_products_in_stock(self, query, max_results=3):
        """Caută doar produse în stoc"""
        results = self.search_products(query, max_results=10)
        in_stock = [p for p in results if self.is_in_stock(p)][:max_results]
        return in_stock

    def filter_by_price(self, max_price, max_results=3):
        """Filtrează după preț (doar în stoc)"""
        results = []
        for product in self.products:
            try:
                if not self.is_in_stock(product):
                    continue

                price = float(product.get('Pret vanzare (cu promotie)', 0))
                if price <= max_price:
                    results.append(product)
                    if len(results) >= max_results:
                        break
            except Exception:
                pass
        return results

    def extract_price(self, text):
        """Extrage prețul din text"""
        import re
        numbers = re.findall(r'\d+', text)
        return int(numbers[-1]) if numbers else None

    def format_products_for_context(self, products):
        """Formatează produsele cu info de stoc"""
        if not products:
            return "Nu există produse disponibile în stoc pentru această solicitare."

        formatted = []
        for p in products:
            try:
                stock = int(p.get('stoc', 0))
                status = "✅ În stoc" if stock > 0 else "❌ Stoc epuizat"
                formatted.append(
                    f"- {p.get('Nume')}: {p.get('Pret vanzare (cu promotie)')} RON [{status}] – {p.get('Descriere', '')[:50]}..."
                )
            except:
                formatted.append(
                    f"- {p.get('Nume')}: {p.get('Pret vanzare (cu promotie)')} RON – {p.get('Descriere', '')[:50]}..."
                )

        return "\n".join(formatted)

    def log_conversation(self, user_message, bot_response):
        """Salvează conversația în JSON"""
        try:
            conversations = []
            try:
                with open('conversations.json', 'r', encoding='utf-8') as f:
                    conversations = json.load(f)
            except FileNotFoundError:
                conversations = []

            conversations.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "user_message": user_message,
                "bot_response": bot_response
            })

            with open('conversations.json', 'w', encoding='utf-8') as f:
                json.dump(conversations, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ Conversation logged - Total: {len(conversations)}")
        except Exception as e:
            logger.error(f"❌ Logging error: {e}")

    def get_response(self, user_message):
        """Generează răspuns inteligent cu OpenAI"""
        self.load_config()

        try:
            # Detectează tipul de întrebare
            is_logistics_question = any(
                word in user_message.lower() for word in [
                    'retur', 'returnare', 'schimb', 'livrare', 'plată',
                    'contact', 'telefon', 'email', 'orar', 'program', 'cost'
                ])

            is_stock_question = any(
                word in user_message.lower() for word in [
                    'stoc', 'disponibil', 'pe stoc', 'epuizat', 'disponibilitate'
                ])

            # ⭐ DOAR dacă NU e logistics question, caută produse
            if is_logistics_question:
                products = []
            else:
                # Pentru întrebări despre stoc, caută doar în stoc
                if is_stock_question:
                    products = self.search_products_in_stock(
                        user_message, max_results=3)
                else:
                    products = self.search_products_in_stock(
                        user_message, max_results=3)

                # Dacă user cere sub o anumită preț
                if 'sub' in user_message.lower():
                    price = self.extract_price(user_message)
                    if price:
                        products = self.filter_by_price(price, max_results=3)

            products_context = self.format_products_for_context(products)

            logistics = self.config.get('logistics', {})
            contact = logistics.get('contact', {})
            faq = self.config.get('faq', [])

            faq_text = "\n".join([
                f"Q: {item['question']}\nA: {item['answer']}"
                for item in faq[:3]
            ])

            system_prompt = f"""Tu ești asistentul virtual oficial al ejolie.ro, magazin online de rochii de eveniment.

LIMBA: Exclusiv limba română
TON: elegant, calm, profesionist, NU agresiv

CONTACT:
📧 Email (doar pentru probleme speciale): {contact.get('email', 'N/A')}
📞 Telefon (DOAR dacă cere operator uman): {contact.get('phone', 'N/A')}

🚚 LIVRARE:
- Timp: {logistics.get('shipping', {}).get('days', 'N/A')}
- Cost: {logistics.get('shipping', {}).get('cost_standard', 'N/A')} lei (GRATUIT > 200 lei)

🔄 RETUR:
{logistics.get('return_policy', 'N/A')}

FAQ:
{faq_text}

PRODUSE DISPONIBILE (dacă relevant):
{products_context}

⭐ REGULI OBLIGATORII:

1. STOC:
   - Arată DOAR produse în stoc (✅ În stoc)
   - Dacă e epuizat, comunică clar: "Din păcate, această rochie nu mai este disponibilă"
   - Ofer alternative din stoc

2. RETUR / LIVRARE / PLATĂ / CONTACT:
   - Răspunde DIRECT și COMPLET
   - Max 3-4 rânduri
   - FĂRĂ link-uri
   - EMAIL DOAR dacă caz special

3. ROCHII / CULOARE / PREȚ / OCAZIE:
   - Recomandă MAXIM 3 produse
   - Format: "- Nume: PrețRON [✅ În stoc] - descriere scurtă"
   - FĂRĂ link-uri

4. DACĂ USER CERE "operator uman" / "să vorbesc cu cineva":
   - DAI TELEFON
   - FĂRĂ EMAIL

5. NU INVENTA INFORMAȚII - folosește DOAR ce ai în config

6. OBIECTIV: Chatbot să REZOLVE totul, fără email inbox overload

IMPORTANT: TU EȘTI SOLUȚIA - nu redirector la email!
"""

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.5,
                max_tokens=300
            )

            bot_response = response['choices'][0]['message']['content']

            # LOG CONVERSATION
            self.log_conversation(user_message, bot_response)

            logger.info(f"✅ Response generated - Length: {len(bot_response)}")

            return {
                "response": bot_response,
                "products": products,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"❌ OpenAI error: {e}")
            return {
                "response": "A apărut o eroare. Te rugăm să ne contactezi: contact@ejolie.ro",
                "status": "error"
            }


# Initialize bot
bot = ChatBot()
