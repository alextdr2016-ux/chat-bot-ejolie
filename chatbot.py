import pandas as pd
import openai
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

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')


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
            # Convert DataFrame to list of tuples with link support
            # Format: (name, price, description, stock, link)
            self.products = []
            for idx, row in df.iterrows():
                # Get name
                name = str(row.get('Nume', ''))

                # Get price
                try:
                    price = float(row.get('Pret vanzare (cu promotie)', 0))
                except:
                    price = 0

                # Get description
                description = str(row.get('Descriere', ''))

                # Get stock - try multiple column names including "Stoc numeric"
                stock = 0
                try:
                    # Try different possible column names for stock
                    stock_value = (
                        row.get('Stoc numeric') or    # ✅ MAIN - Capital S!
                        row.get('stoc numeric') or    # Fallback lowercase
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

                # Create tuple with link
                product = (name, price, description, stock, link)
                self.products.append(product)

                # Log first 5 products for debug (show exact structure)
                if idx < 5:
                    logger.info(f"📦 Product {idx+1}:")
                    logger.info(f"   Name: {name}")
                    logger.info(f"   Price: {price}")
                    logger.info(f"   Description: {description[:50]}...")
                    logger.info(f"   Stock: {stock}")
                    logger.info(
                        f"   Link: {link[:50] if link else 'NO LINK'}...")

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
        all_results = self.search_products(
            query, limit * 2)  # Get more results
        in_stock = [p for p in all_results if self.is_in_stock(p)]
        return in_stock[:limit]

    # ========== PRODUCT FORMATTING ==========

    def format_products_for_context(self, products):
        """Format products in STRICT structured format to prevent GPT rewriting"""
        if not products:
            return "Niciun produs găsit în stoc."

        # Format as structured list that FORCES GPT to copy-paste exact values
        lines = []
        lines.append("=" * 80)
        lines.append("🚨 PRODUSE - TREBUIE COPIATE EXACT, FĂRĂ MODIFICĂRI! 🚨")
        lines.append("=" * 80)
        lines.append("")

        for idx, p in enumerate(products, 1):
            name = p[0] if len(p) > 0 else ""
            price = p[1] if len(p) > 1 else 0
            desc = p[2] if len(p) > 2 else ""
            stock = p[3] if len(p) > 3 else 0
            link = p[4] if len(p) > 4 else ""

            stock_text = "✅ În stoc" if stock > 0 else "❌ Epuizat"

            lines.append(f"PRODUS #{idx}:")
            lines.append(f"  NUME EXACT: {name}")
            lines.append(f"  PREȚ: {price} RON")
            lines.append(f"  STOC: {stock_text}")
            lines.append(f"  DESCRIERE: {desc}")
            if link:
                lines.append(f"  LINK: {link}")
            lines.append("")

        lines.append("=" * 80)
        lines.append(
            "INSTRUCȚIUNE: Copiază EXACT aceste valori în răspuns. NU RESCRII!")
        lines.append("=" * 80)

        return "\n".join(lines)

    # ========== LOGGING ==========

    def log_conversation(self, user_message, bot_response):
        """Log conversation to file with robust error handling"""
        try:
            # Load existing conversations
            conversations = []
            try:
                with open('conversations.json', 'r', encoding='utf-8') as f:
                    conversations = json.load(f)
                    if not isinstance(conversations, list):
                        logger.warning(
                            "⚠️ conversations.json is not a list, resetting")
                        conversations = []
            except FileNotFoundError:
                logger.info("ℹ️ No conversations file found, creating new one")
                conversations = []
            except json.JSONDecodeError:
                logger.warning(
                    "⚠️ conversations.json is corrupted, starting fresh")
                conversations = []
            except Exception as e:
                logger.warning(f"⚠️ Error reading conversations: {e}")
                conversations = []

            # Add new conversation
            conversation = {
                "timestamp": datetime.now().isoformat(),
                "user_message": user_message,
                "bot_response": bot_response
            }
            conversations.append(conversation)

            # Save with safe write
            try:
                with open('conversations.json', 'w', encoding='utf-8') as f:
                    json.dump(conversations, f, indent=2, ensure_ascii=False)
                logger.info(
                    f"💾 Conversation logged ({len(conversations)} total)")
            except Exception as e:
                logger.error(f"❌ Error writing conversations.json: {e}")
        except Exception as e:
            logger.error(f"❌ Critical logging error: {e}")

    # ========== MAIN GET RESPONSE ==========

    def get_response(self, user_message):
        """Get chatbot response with strict product name preservation"""

        logger.info(f"📨 User message: {user_message[:50]}...")

        # ========== TOPIC FILTERING ==========
        # OFF-TOPIC keywords
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

        # ON-TOPIC keywords
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
            logger.info(f"⛔ Off-topic question: {user_message[:50]}")

            off_topic_response = "🎀 Sunt asistentul virtual al magazinului ejolie.ro și răspund doar la întrebări legate de rochii, preturi, comenzi și livrare.\n\nPot ajuta cu:\n✅ Căutare rochii (după culoare, preț, ocazie)\n✅ Informații despre preturi și comenzi\n✅ Întrebări despre livrare și retur\n✅ Informații despre măsuri și materiale\n\nCe rochie cauți?"

            self.log_conversation(user_message, off_topic_response)

            return {
                "response": off_topic_response,
                "status": "off_topic"
            }

        # ========== NORMAL PROCESSING ==========
        logger.info(f"✅ Processing dress-related question...")

        try:
            # Search for relevant products
            logger.info("🔍 Searching products...")
            products = self.search_products_in_stock(user_message, limit=3)
            products_context = self.format_products_for_context(
                products) if products else "Niciun produs găsit în stoc."
            logger.info(f"📦 Found {len(products)} products")

            # Get custom rules and FAQ
            custom_rules = self.config.get('custom_rules', [])
            custom_rules_text = "\n".join(
                [f"- {rule.get('title', '')}: {rule.get('content', '')}" for rule in custom_rules]) if custom_rules else ""

            faq = self.config.get('faq', [])
            faq_text = "\n".join(
                [f"Q: {item.get('question', '')}\nA: {item.get('answer', '')}" for item in faq]) if faq else ""

            # Get logistics info
            logistics = self.config.get('logistics', {})
            contact = logistics.get('contact', {})
            shipping = logistics.get('shipping', {})

            contact_email = contact.get('email', 'contact@ejolie.ro')
            contact_phone = contact.get('phone', '+40 XXX XXX XXX')
            shipping_days = shipping.get('days', '3-5 zile')
            shipping_cost = shipping.get('cost_standard', '25 lei')
            return_policy = logistics.get('return_policy', '30 de zile')

            logger.info("🤖 Building GPT prompt with STRICT instructions...")

            # Build system prompt with STRICT instructions to prevent rewriting
            system_prompt = f"""
Tu ești Levyn, asistentul virtual al magazinului online ejolie.ro.

🚨 INSTRUCȚIUNI STRICTE - OBLIGATORII! 🚨

1️⃣ PRODUSE - COPY-PASTE EXACT!
   ✅ TREBUIE să copiezi EXACT valorile din lista furnizată
   ❌ NU rescrii, NU parafrazezi, NU schimbi nume
   ❌ NU inventezi descrieri gen "Rochie neagră din dantelă"
   
2️⃣ LINKURI - COPIAZĂ INTEGRAL!
   ✅ Copiază link-ul EXACT cum apare în PRODUS #X: LINK
   ❌ NU modifici URL-ul
   ❌ NU rescrii linkul

3️⃣ FORMAT RĂSPUNS - TREBUIE SĂ URMEZI!
   Folosește EXACT acest format:
   "🎀 Desigur! Iată [NUMĂR] opțiuni:
   
   1️⃣ [COPIERE EXACTĂ A NUMELUI] - [PREȚ] RON [STOC]
      📝 [DESCRIERE EXACTĂ]
      🔗 [LINK EXACT]
   
   2️⃣ [COPIERE EXACTĂ A NUMELUI] - [PREȚ] RON [STOC]
      📝 [DESCRIERE EXACTĂ]
      🔗 [LINK EXACT]"

INFORMAȚII MAGAZIN:
- Email: {contact_email}
- Telefon: {contact_phone}
- Livrare: {shipping_days}, Cost: {shipping_cost}
- Retur: {return_policy}

LISTA PRODUSE DISPONIBILE:
{products_context}

FAQ:
{faq_text}

REGULI CUSTOM:
{custom_rules_text}

⚠️ AVERTISMENT FINAL:
Dacă rescrii produsele sau linkurile, utilizatorul nu va putea cumpăra!
Copiază EXACT sau NU RECOMANDA!

STIL:
- Emojis: 🎀, 👗, ✅, 🔗, etc.
- Prietenos și helpful
- Răspunsuri concise
"""

            logger.info("🔄 Calling GPT-3.5-turbo with STRICT instructions...")

            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=350,
                    temperature=0.5,  # Lower temperature for more compliance
                    timeout=10
                )

                bot_response = response['choices'][0]['message']['content']
                logger.info(
                    f"✅ GPT response generated ({len(bot_response)} chars)")

            except openai.error.RateLimitError:
                logger.error("❌ GPT Rate limit exceeded")
                bot_response = "⚠️ Momentan suntem în cerere mare. Te rog încearcă din nou în câteva secunde."
            except openai.error.APIError as e:
                logger.error(f"❌ GPT API error: {e}")
                bot_response = "⚠️ Avem o problemă tehnică. Te rog contactează-ne la contact@ejolie.ro"
            except Exception as e:
                logger.error(f"❌ GPT call error: {e}")
                bot_response = "⚠️ A apărut o eroare. Te rog încearcă din nou."

            # Log conversation
            self.log_conversation(user_message, bot_response)

            return {
                "response": bot_response,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"❌ Error in get_response: {e}", exc_info=True)

            error_response = "⚠️ Moment de pauză tehnică. Te rog încearcă din nou."
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
