import pandas as pd
from openai import OpenAI
import json
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure OpenAI - NEW SDK
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


class ChatBot:
    def __init__(self):
        """Initialize ChatBot"""
        self.products = []
        self.config = {}
        self.conversations = []
        self.load_products()
        self.load_config()
        logger.info("🤖 ChatBot initialized")

    # ========== PRODUCT LOADING ==========

    def load_products(self):
        """Load products from CSV with encoding fallback"""
        products_path = 'products.csv'

        if not os.path.exists(products_path):
            logger.warning(f"⚠️ Products file not found at {products_path}")
            self.products = []
            return

        try:
            # Try UTF-8 first
            df = pd.read_csv(products_path, encoding='utf-8')
            logger.info(f"✅ Products loaded (UTF-8) - {len(df)} items")
            logger.info(f"📋 Columns: {list(df.columns)}")
        except UnicodeDecodeError:
            logger.warning("⚠️ UTF-8 failed, trying latin-1...")
            try:
                df = pd.read_csv(products_path, encoding='latin-1')
                logger.info(f"✅ Products loaded (latin-1) - {len(df)} items")
                logger.info(f"📋 Columns: {list(df.columns)}")
            except Exception as e:
                logger.error(f"❌ Failed to load products: {e}")
                self.products = []
                return
        except Exception as e:
            logger.error(f"❌ Error loading products: {e}")
            self.products = []
            return

        try:
            # Convert DataFrame to list of tuples for compatibility
            self.products = []
            for idx, row in df.iterrows():
                # Get name
                name = str(row.get('Nume', ''))

                # Get price
                try:
                    price = float(row.get('Pret vanzare (cu promotie)', 0))
                except (ValueError, TypeError):
                    price = 0

                # Get description
                description = str(row.get('Descriere', ''))

                # Get stock - try multiple column names including "Stoc numeric"
                stock = 0
                try:
                    # Try different possible column names for stock
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
                    logger.warning(f"⚠️ Error parsing stock for {name}: {e}")
                    stock = 0

                # Get product link
                link = str(row.get('Link produs', ''))
                if link and link.lower() != 'nan' and link.strip():
                    link = link.strip()
                else:
                    link = ""

                # Add link to tuple: (name, price, description, stock, link)
                product = (name, price, description, stock, link)
                self.products.append(product)

                # Log first 5 products for debug (show exact structure)
                if idx < 5:
                    logger.info(f"📦 Product {idx+1}:")
                    logger.info(f"   Name: {name}")
                    logger.info(f"   Price: {price}")
                    logger.info(f"   Stock: {stock}")
                    logger.info(f"   Link: {link}")

            logger.info(f"✅ {len(self.products)} products ready for use")
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
        """Search products by name with scoring"""
        if not self.products:
            return []

        query_lower = query.lower()
        results = []

        for product in self.products:
            name = product[0].lower() if product[0] else ''
            desc = product[2].lower() if product[2] else ''

            # Scoring
            score = 0
            if query_lower in name:
                score += 10
            if query_lower in desc:
                score += 5

            # Check for individual words
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 2:  # Skip short words
                    if word in name:
                        score += 3
                    if word in desc:
                        score += 1

            if score > 0:
                results.append((product, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Return top products (limit)
        return [p[0] for p in results[:limit]]

    # ========== STOCK MANAGEMENT ==========

    def is_in_stock(self, product):
        """Check if product is in stock"""
        if len(product) >= 4:
            return product[3] > 0  # stock > 0
        return True  # Default to in stock if no stock info

    def search_products_in_stock(self, query, limit=3):
        """Search products and filter by stock"""
        all_results = self.search_products(query, limit * 3)
        in_stock = [p for p in all_results if self.is_in_stock(p)]
        return in_stock[:limit]

    # ========== PRODUCT FORMATTING ==========

    def format_product(self, product):
        """Format product for display with FULL link"""
        if not product or len(product) < 3:
            return "Produs nedisponibil"

        name = product[0]
        price = product[1]
        desc = product[2]
        stock = product[3] if len(product) >= 4 else 1
        link = product[4] if len(product) >= 5 else ""

        stock_status = "✅ În stoc" if stock > 0 else "❌ Epuizat"

        # Format with FULL link - make it very explicit for GPT
        if link and link.startswith('http'):
            return f"• {name} | Preț: {price} RON | {stock_status}\n  Link direct: {link}"
        else:
            return f"• {name} | Preț: {price} RON | {stock_status}"

    def format_products_for_context(self, products):
        """Format multiple products for GPT context"""
        if not products:
            return "Niciun produs disponibil."

        formatted = []
        for p in products:
            formatted.append(self.format_product(p))

        return "\n\n".join(formatted)

    # ========== CONVERSATION LOGGING ==========

    def log_conversation(self, user_message, bot_response):
        """Log conversation to file"""
        try:
            conversations = []
            try:
                with open('conversations.json', 'r', encoding='utf-8') as f:
                    conversations = json.load(f)
            except FileNotFoundError:
                conversations = []

            conversations.append({
                "timestamp": datetime.now().isoformat(),
                "user_message": user_message,
                "bot_response": bot_response
            })

            # Keep only last 1000 conversations to prevent file bloat
            if len(conversations) > 1000:
                conversations = conversations[-1000:]

            with open('conversations.json', 'w', encoding='utf-8') as f:
                json.dump(conversations, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"❌ Error logging conversation: {e}")

    # ========== MAIN RESPONSE ==========

    def get_response(self, user_message):
        """Generate response to user message"""
        if not user_message or not user_message.strip():
            return {
                "response": "Te rog să scrii o întrebare.",
                "status": "error"
            }

        logger.info(f"📩 Processing: {user_message[:50]}...")

        # ========== TOPIC FILTERING ==========
        # OFF-TOPIC keywords - definitively reject
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

        # ON-TOPIC keywords - should answer
        on_topic_keywords = [
            # Dress/Fashion related
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
            'promo', 'promocie', 'reducere', 'reduction', 'reducere', 'oferta', 'offer', 'discount',
            'contact', 'contactati', 'help', 'ajutor',
            'telefon', 'phone', 'email', 'mail',
            'fara', 'gratuit', 'free', 'transport gratuit',
            'nume', 'numar', 'gasesc', 'gasit', 'find', 'search', 'cauta',
            'camasa', 'bluza', 'fusta', 'pantaloni', 'sacou', 'salopeta', 'trening'
        ]

        user_lower = user_message.lower()

        # Check OFF-TOPIC first
        is_off_topic = any(
            keyword in user_lower for keyword in off_topic_keywords)

        # Check ON-TOPIC
        is_on_topic = any(
            keyword in user_lower for keyword in on_topic_keywords)

        # Decision logic
        if is_off_topic and not is_on_topic:
            # Definitively off-topic
            logger.info(f"⛔ Off-topic question: {user_message[:50]}")

            off_topic_response = "🎀 Sunt asistentul virtual al magazinului ejolie.ro și răspund doar la întrebări legate de produsele noastre, prețuri, comenzi și livrare.\n\nPot ajuta cu:\n✅ Căutare rochii, bluze, fuste (după culoare, preț, ocazie)\n✅ Informații despre prețuri și comenzi\n✅ Întrebări despre livrare și retur\n✅ Informații despre mărimi și materiale\n\nCe produs cauți?"

            self.log_conversation(user_message, off_topic_response)

            return {
                "response": off_topic_response,
                "status": "off_topic"
            }

        # ========== NORMAL PROCESSING ==========
        logger.info(f"✅ On-topic question, processing with GPT...")

        try:
            # Search for relevant products
            logger.info("🔍 Searching products...")
            products = self.search_products_in_stock(user_message, limit=5)
            products_context = self.format_products_for_context(
                products) if products else "Niciun produs găsit în stoc."
            logger.info(f"📦 Found {len(products)} products")

            # Get custom rules from config
            custom_rules = self.config.get('custom_rules', [])
            custom_rules_text = ""
            if custom_rules:
                custom_rules_text = "REGULI CUSTOM:\n" + "\n".join(
                    [f"- {rule.get('title', '')}: {rule.get('content', '')}" for rule in custom_rules])

            # Get FAQ from config
            faq = self.config.get('faq', [])
            faq_text = ""
            if faq:
                faq_text = "\n".join(
                    [f"Q: {item.get('question', '')}\nA: {item.get('answer', '')}" for item in faq])

            # Get logistics info
            logistics = self.config.get('logistics', {})
            contact = logistics.get('contact', {})
            shipping = logistics.get('shipping', {})

            contact_email = contact.get('email', 'contact@ejolie.ro')
            contact_phone = contact.get('phone', '0757 10 51 51')
            shipping_days = shipping.get('days', '24-48 ore')
            shipping_cost = shipping.get('cost_standard', '19 lei')
            return_policy = logistics.get('return_policy', 'Retur în 14 zile')

            logger.info("🤖 Building GPT prompt...")

            # Build system prompt
            system_prompt = f"""Tu ești Levyn, asistentul virtual al magazinului online ejolie.ro.

REGULI STRICTE:
1. Răspunzi DOAR despre produse, prețuri, comenzi, livrare și retur
2. Pentru FIECARE produs recomandat, COPIAZĂ link-ul EXACT din lista de mai jos
3. NU inventa link-uri! Folosește DOAR link-urile din PRODUSE DISPONIBILE

INFORMAȚII MAGAZIN:
📧 Email: {contact_email}
📞 Telefon: {contact_phone}
🚚 Livrare: {shipping_days}
💰 Cost livrare: {shipping_cost} (gratuit peste 200 RON)

PRODUSE DISPONIBILE:
{products_context}

FAQ:
{faq_text}

{custom_rules_text}

FORMAT OBLIGATORIU PENTRU RĂSPUNS:
Când recomanzi produse, folosește EXACT acest format pentru fiecare produs:

🎀 [Nume produs] - [Preț] RON [Status stoc]
🔗 [copiază link-ul exact din lista de mai sus]

EXEMPLU CORECT DE RĂSPUNS:
"Îți recomand:

🎀 Rochie Marta turcoaz din neopren - 154 RON ✅ În stoc
🔗 https://ejolie.ro/product/rochie-marta-turcoaz-din-neopren-cu-cordon-maxi

🎀 Camasa Miruna alba cu nasturi negri - 270 RON ✅ În stoc
🔗 https://ejolie.ro/product/camasa-miruna-alba-cu-nasturi-negri-7505

Dorești mai multe detalii despre vreunul?"

⚠️ FOARTE IMPORTANT: 
- Link-ul trebuie să fie URL-ul COMPLET care începe cu https://ejolie.ro/product/...
- NU scrie "(link)" sau "[link]" sau "click aici" - scrie URL-ul REAL din lista de produse!
- Fii prietenos și folosește emoji-uri 🎀 👗 ✅ 🔗
"""

            logger.info("🔄 Calling GPT-3.5-turbo...")

            # Call GPT with NEW SDK syntax
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=500,
                    temperature=0.7,
                    timeout=30
                )

                # NEW SDK: access response differently
                bot_response = response.choices[0].message.content
                logger.info(
                    f"✅ GPT response generated ({len(bot_response)} chars)")

            except Exception as e:
                error_str = str(e).lower()
                if 'rate' in error_str or 'limit' in error_str:
                    logger.error("❌ GPT Rate limit exceeded")
                    bot_response = "⚠️ Momentan suntem în cerere mare. Te rog încearcă din nou în câteva secunde."
                elif 'api' in error_str or 'auth' in error_str:
                    logger.error(f"❌ GPT API error: {e}")
                    bot_response = "⚠️ Avem o problemă tehnică. Te rog contactează-ne la contact@ejolie.ro"
                else:
                    logger.error(f"❌ GPT call error: {e}")
                    bot_response = "⚠️ A apărut o eroare. Te rog încearcă din nou sau contactează-ne."

            # Log conversation
            self.log_conversation(user_message, bot_response)

            return {
                "response": bot_response,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"❌ Error in get_response: {e}", exc_info=True)

            error_response = "⚠️ Moment de pauză tehnică. Te rog încearcă din nou sau contactează-ne la contact@ejolie.ro"
            try:
                self.log_conversation(user_message, error_response)
            except Exception as log_error:
                logger.error(f"❌ Could not log error: {log_error}")

            return {
                "response": error_response,
                "status": "error"
            }


# ========== INITIALIZE BOT ==========

bot = ChatBot()
