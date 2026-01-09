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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')


class ChatBot:
    def __init__(self):
        """Initialize ChatBot"""
        self.products = []
        self.config = {}
        self.load_products()
        self.load_config()
        logger.info("🤖 ChatBot initialized with database support")

    # ========== PRODUCT LOADING ==========

    def load_products(self):
        """Load products from CSV"""
        products_path = 'products.csv'

        if not os.path.exists(products_path):
            logger.warning(f"⚠️ Products file not found")
            self.products = []
            return

        try:
            df = pd.read_csv(products_path, encoding='utf-8')
            logger.info(f"✅ Products loaded - {len(df)} items")
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(products_path, encoding='latin-1')
                logger.info(f"✅ Products loaded (latin-1) - {len(df)} items")
            except Exception as e:
                logger.error(f"❌ Failed to load products: {e}")
                self.products = []
                return
        except Exception as e:
            logger.error(f"❌ Error loading products: {e}")
            self.products = []
            return

        try:
            self.products = []
            for idx, row in df.iterrows():
                name = str(row.get('Nume', ''))
                try:
                    price = float(row.get('Pret vanzare (cu promotie)', 0))
                except:
                    price = 0

                description = str(row.get('Descriere', ''))

                stock = 0
                try:
                    stock_value = (
                        row.get('Stoc numeric') or
                        row.get('stoc numeric') or
                        row.get('stoc') or
                        row.get('Stoc') or
                        row.get('Stock') or
                        row.get('STOC') or
                        row.get('disponibil') or
                        row.get('Disponibil') or
                        0
                    )
                    if stock_value and pd.notna(stock_value):
                        stock = int(stock_value)
                except Exception as e:
                    logger.warning(f"⚠️ Error parsing stock: {e}")
                    stock = 0

                link = str(row.get('Link produs', ''))
                if link and link.lower() != 'nan' and link.strip():
                    link = link.strip()
                else:
                    link = ""

                product = (name, price, description, stock, link)
                self.products.append(product)

                if idx < 3:
                    logger.info(
                        f"📦 Product {idx+1}: {name} | {price}RON | Stock:{stock}")

            logger.info(f"✅ {len(self.products)} products ready")
        except Exception as e:
            logger.error(f"❌ Error processing products: {e}")
            self.products = []

    # ========== CONFIG LOADING ==========

    def load_config(self):
        """Load configuration from config.json"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info("✅ Config loaded")
        except Exception as e:
            logger.warning(f"⚠️ Config load error: {e}")
            self.config = {}

    # ========== PRODUCT SEARCH ==========

    def search_products(self, query, limit=3):
        """Search products by name"""
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
        """Check if product is in stock"""
        if len(product) >= 4:
            return product[3] > 0
        return True

    def search_products_in_stock(self, query, limit=3):
        """Search products and filter by stock"""
        all_results = self.search_products(query, limit * 2)
        in_stock = [p for p in all_results if self.is_in_stock(p)]
        return in_stock[:limit]

    # ========== PRODUCT FORMATTING ==========

    def format_product(self, product):
        """Format product for display"""
        if not product or len(product) < 3:
            return "Produs nedisponibil"

        name = product[0]
        price = product[1]
        desc = product[2]
        stock = product[3] if len(product) >= 4 else 1
        link = product[4] if len(product) >= 5 else ""

        stock_status = "✅ În stoc" if stock > 0 else "❌ Epuizat"

        if link:
            return f"🎀 **{name}** - {price}RON [{stock_status}]\n📝 {desc}\n🔗 {link}"
        else:
            return f"🎀 **{name}** - {price}RON [{stock_status}]\n📝 {desc}"

    def format_products_for_context(self, products):
        """Format multiple products for GPT context"""
        if not products:
            return "Niciun produs găsit în stoc."

        formatted = []
        for p in products:
            formatted.append(self.format_product(p))

        return "\n\n".join(formatted)

    # ========== MAIN GET RESPONSE ==========

    def get_response(self, user_message, session_id=None, user_ip=None, user_agent=None):
        """Get chatbot response with database logging"""

        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"📨 User message: {user_message[:50]}...")

        # ========== TOPIC FILTERING ==========
        off_topic_keywords = [
            'matematica', 'radical', 'ecuatie', 'formula', 'calcul',
            'geografie', 'tara', 'capital', 'harta', 'continent',
            'fizica', 'chimie', 'biologie', 'atom', 'molecula',
            'istorie', 'imperiu', 'epoca', 'rege', 'regina',
            'religie', 'dumnezeu', 'iisus', 'biblie',
            'politica', 'guvern', 'minister', 'lege',
            'sport', 'fotbal', 'tenis', 'baschet', 'meci',
            'film', 'cinema', 'actor', 'regizor',
            'muzica', 'cantaret', 'piesa', 'melodie',
            'programare', 'code', 'python', 'java', 'javascript',
            'china', 'america', 'europa', 'africa',
            'programului', 'text despre'
        ]

        on_topic_keywords = [
            'rochie', 'dress', 'rochii', 'dresses',
            'pret', 'price', 'cost', 'euro', 'lei', 'ron',
            'comanda', 'order', 'cumpar', 'buy', 'cumpara',
            'livrare', 'delivery', 'transport', 'shipping',
            'retur', 'return', 'schimb', 'exchange', 'schimbare',
            'plata', 'payment', 'card', 'card de credit',
            'masura', 'size', 'marimea', 'sizes',
            'culoare', 'color', 'colors', 'culori', 'alb', 'negru', 'rosu', 'albastru',
            'material', 'tafta', 'matase', 'voal', 'bumbac',
            'descriere', 'description', 'detalii', 'details',
            'nunta', 'wedding', 'botez', 'christening',
            'ocazie', 'occasion', 'eveniment', 'event',
            'petrecere', 'party', 'gala', 'cina',
            'stock', 'disponibil', 'availability', 'available',
            'ejolie', 'trendya', 'magazin', 'shop', 'store',
            'promo', 'promocie', 'reducere', 'reduction', 'oferta', 'offer', 'discount',
            'contact', 'contactati', 'help', 'ajutor',
            'telefon', 'phone', 'email', 'mail',
            'fara', 'gratuit', 'free', 'transport gratuit',
            'nume', 'numar', 'gasesc', 'gasit', 'find', 'search', 'cauta'
        ]

        user_lower = user_message.lower()
        is_off_topic = any(
            keyword in user_lower for keyword in off_topic_keywords)
        is_on_topic = any(
            keyword in user_lower for keyword in on_topic_keywords)

        if is_off_topic and not is_on_topic:
            logger.info(f"⛔ Off-topic question")

            off_topic_response = "🎀 Sunt asistentul virtual al magazinului ejolie.ro și răspund doar la întrebări legate de rochii, preturi, comenzi și livrare.\n\nPot ajuta cu:\n✅ Căutare rochii (după culoare, preț, ocazie)\n✅ Informații despre preturi și comenzi\n✅ Întrebări despre livrare și retur\n✅ Informații despre măsuri și materiale\n\nCe rochie cauți?"

            # Save to database
            db.save_conversation(
                session_id, user_message, off_topic_response, user_ip, user_agent, is_on_topic=False)

            return {
                "response": off_topic_response,
                "status": "off_topic",
                "session_id": session_id
            }

        # ========== NORMAL PROCESSING ==========
        logger.info(f"✅ Processing dress-related question...")

        try:
            logger.info("🔍 Searching products...")
            products = self.search_products_in_stock(user_message, limit=3)
            products_context = self.format_products_for_context(
                products) if products else "Niciun produs găsit în stoc."
            logger.info(f"📦 Found {len(products)} products")

            # Get config info
            logistics = self.config.get('logistics', {})
            contact = logistics.get('contact', {})
            shipping = logistics.get('shipping', {})

            contact_email = contact.get('email', 'contact@ejolie.ro')
            contact_phone = contact.get('phone', '+40 XXX XXX XXX')
            shipping_days = shipping.get('days', '3-5 zile')
            shipping_cost = shipping.get('cost_standard', '25 lei')
            return_policy = logistics.get('return_policy', '30 de zile')

            logger.info("🤖 Building GPT prompt...")

            system_prompt = f"""
Tu ești Levyn, asistentul virtual al magazinului online ejolie.ro.

INSTRUCȚIUNI CRITICE:
1. RĂSPUNZI DOAR LA ÎNTREBĂRI DESPRE ROCHII, PRETURI, COMENZI, LIVRARE ȘI RETUR
2. Dacă intrebarea nu e legata de rochii, cere politicos sa reformuleze
3. Fii prietenos si helpful in toate raspunsurile

IMPORTANT - AFISEAZA PRODUSELE CU NUMELE EXACT DIN LISTA SI LINK-URILE!
- NU rescrii sau parafrazezi numele produselor!
- INCLUDE LINK-URI (🔗) pentru fiecare produs
- Arată exact cum sunt în listă

INFORMAȚII DESPRE MAGAZIN:
- Email: {contact_email}
- Telefon: {contact_phone}
- Livrare: {shipping_days}
- Cost livrare: {shipping_cost}
- Politica retur: {return_policy}

PRODUSE DISPONIBILE:
{products_context}

STIL DE COMUNICARE:
- Foloseste emoji (🎀, 👗, ✅, 🔗, etc.)
- Fii prietenos și helpful
- Dă răspunsuri concise
- INCLUDE NAMES EXACTE din lista de produse
- INCLUDE LINK-URI pentru click direct la produs
"""

            logger.info("🔄 Calling GPT-3.5-turbo...")

            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=300,
                    temperature=0.5,
                    timeout=15
                )

                bot_response = response['choices'][0]['message']['content']
                logger.info(f"✅ GPT response generated")

            except Exception as e:
                logger.error(f"❌ GPT call error: {e}")
                bot_response = "⚠️ A apărut o eroare. Te rog încearcă din nou."

            # Save to database
            db.save_conversation(
                session_id, user_message, bot_response, user_ip, user_agent, is_on_topic=True)

            return {
                "response": bot_response,
                "status": "success",
                "session_id": session_id
            }

        except Exception as e:
            logger.error(f"❌ Error: {e}")

            error_response = "⚠️ Moment de pauză tehnică. Te rog încearcă din nou."
            db.save_conversation(
                session_id, user_message, error_response, user_ip, user_agent, is_on_topic=True)

            return {
                "response": error_response,
                "status": "error",
                "session_id": session_id
            }


# ========== INITIALIZE BOT ==========

bot = ChatBot()
