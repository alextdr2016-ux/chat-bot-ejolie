import pandas as pd
import openai
import json
import logging
import os
import re
import uuid
import time
from datetime import datetime, timedelta
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

        # 🎯 OPTIMIZATION: FAQ Cache (Strategy 2)
        self.faq_cache = self._build_faq_cache()

        # 🎯 OPTIMIZATION: Rate Limiting per User (Strategy 6)
        self.user_limits = {}

        # 🎯 OPTIMIZATION: Conversation Memory (Strategy 7)
        self.conversation_cache = {}

        logger.info("🤖 ChatBot initialized with optimizations")

    def _build_faq_cache(self):
        """Build FAQ cache for instant responses (no GPT call)"""
        return {
            # Livrare
            'livrare': "📦 Livrăm în toată România! Cost: 19 lei. Transport GRATUIT peste 200 lei. Timp: 1-2 zile lucrătoare.",
            'cost livrare': "📦 Costul livrării este 19 lei. Transport GRATUIT la comenzi peste 200 lei!",
            'cat costa livrarea': "📦 19 lei pentru livrare. GRATUIT peste 200 lei!",
            'transport': "📦 Transport: 19 lei. GRATUIT la comenzi peste 200 lei. Livrăm în 1-2 zile!",
            'livrare gratuita': "📦 Da! Transport GRATUIT la comenzi peste 200 lei!",

            # Retur - Ton feminin elegant
            'retur': """✨ Draga mea, vrem ca fiecare piesă să fie perfectă pentru tine!
            - Dacă totuși nu se potrivește, o poți returna în următoarele condiții:
            - Completează formularul de retur din contul tău (sau accesează "Retur fără cont")
            - Ai la dispoziție 14 zile de la primire (trebuie să ajungă la noi în acest interval)
            - Piesa să fie impecabilă: fără urme de purtare, cu toate etichetele și sigiliul intact
            - Ambalaj original, cu factura și accesoriile incluse
            - Transportul returului este pe cont propriu
            - Îți returnăm banii în maximum 14 zile, în contul tău bancar
           📍 Adresa noastră: Str Serban Cioculescu nr 15, Gaești, Dâmbovița
           📞 Suntem aici pentru tine: 0757 10 51 51 | contact@ejolie.ro""",

            'returnare': """💝 Procesul de retur, pas cu pas:
             1. Completează formularul de retur din contul tău (sau accesează "Retur fără cont")
             2. Împachetează piesa cu grijă, împreună cu factura și toate accesoriile
             3. Contactează firma ta preferată de curierat (te rugăm să eviți Poșta Română)
             4. Costul transportului este suportat de tine, draga mea
             5. Trimite-ne coletul la: Str Serban Cioculescu nr 15, Gaești, Dâmbovița
               Banii tăi vor ajunge în cont în maximum 14 zile! 💕""",

            'pot returna': """🌸 Bineînțeles, iubita mea! Iată ce trebuie să reții:
            - Completează formularul de retur din contul tău (sau accesează "Retur fără cont")
            - Ai 14 zile de grație de la primirea coletului
            - Piesa trebuie să fie în stare perfectă: nepurtată, nespălată, fără urme de parfum sau cosmetice
            - Toate etichetele originale și sigiliul de securitate trebuie să fie intacte
            - Ambalajul original, factura și accesoriile (curele, broșe) incluse
            - Transportul îl organizezi tu, fără ramburs
            ✨ Important: Dacă sigiliul este rupt sau lipsesc etichetele, nu putem accepta returul
             📞 Ne poți contacta oricând: 0757 10 51 51""",

            'politica retur': """👗 Politica noastră de retur, explicată elegant:
              - Completează formularul de retur din contul tău (sau accesează "Retur fără cont")
            ⏰ Termen: 14 zile calendaristice de la primire
            ✨ Acceptăm: piese impecabile, cu etichete + sigiliu intact, ambalaj original
            🚫 Nu acceptăm: sigiliu rupt, lipsă etichete, urme de purtare sau parfum
            💳 Rambursare: maximum 14 zile în contul tău bancar (doar RON)
            📦 Trimite la: Str Serban Cioculescu nr 15, Gaești, Dâmbovița
            💌 Contact: 0757 10 51 51 | contact@ejolie.ro
            💝 Te rugăm să nu trimiți colete ramburs sau prin Poșta Română!""",

            'cum returnez': """💕 Draga mea, iată cum returnezi ușor:
            1. Completează formularul de retur din contul tău (sau accesează "Retur fără cont")
            2. Împachetează piesa cu atenție, cu factura și accesoriile
            3. Alege un curier de încredere (orice firmă,除外 Poșta Română)
            4. Te rugam sa achiți costul transportului retur
            5. Adresa noastră: Str Serban Cioculescu nr 15, Gaești, Dâmbovița
            📞 Suntem aici să te ajutăm: 0757 10 51 51""",

            'schimb produs': """✨ Schimburi - pentru că meriti piesa perfectă:
           - Cere schimbul din cont sau la contact@ejolie.ro sau la telefon 0757 10 51 51
           - Returul piesei originale: pe noi! 💝
           - Livrarea noii piese: 19 lei (investiție mică în garderoba ta perfectă)
           - Diferență de preț: o plătești sau o primești înapoi, după caz
            💡 Știi că: Al doilea schimb costă 38 lei (ambele transporturi), iar al treilea nu mai este disponibil
             Suntem aici să găsim împreună piesa care ți se potrivește perfect! 💕""",

            # Plata
            'plata': "💳 Poți plăti: Card online, Ramburs la livrare, Transfer bancar.",
            'metode plata': "💳 Acceptăm: Card (Visa, Mastercard), Ramburs, Transfer bancar.",
            'card': "💳 Da, acceptăm plata cu cardul online (Visa, Mastercard).",
            'ramburs': "💳 Da, acceptăm plata ramburs la livrare!",

            # Contact
            'contact': "📧 Email: contact@ejolie.ro | 🌐 https://ejolie.ro",
            'email': "📧 contact@ejolie.ro",
            'telefon': "📱 Găsești numărul pe site: https://ejolie.ro/contact",

            # Program
            'program': "🕐 Programul nostru: Luni-Vineri 9:00-18:00. Comenzi online 24/7!",
            'orar': "🕐 Luni-Vineri 9:00-18:00.",

            # Generale
            'salut': "👋 Bună! Sunt Maria, asistenta virtuală ejolie.ro. Cu ce te pot ajuta?",
            'buna': "👋 Buna! Cu ce te pot ajuta astăzi?",
            'hello': "👋 Hello! How can I help you?",
        }

    def load_products(self):
        """Load products from CSV feed"""
        if not os.path.exists('products.csv'):
            self.products = []
            return

        try:
            df = pd.read_csv('products.csv', encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv('products.csv', encoding='latin-1')
        except Exception as e:
            logger.error(f"❌ Error reading products.csv: {e}")
            self.products = []
            return

        self.products = []
        logger.info(f"📋 CSV Columns found: {list(df.columns)}")

        for _, row in df.iterrows():
            name = str(row.get('Nume', '')).strip()

            try:
                price_raw = row.get('Pret vanzare (cu promotie)', 0)
                if pd.isna(price_raw):
                    price = 0.0
                else:
                    price_str = str(price_raw).replace(
                        'RON', '').replace(',', '.').strip()
                    price = float(price_str)
            except:
                price = 0.0

            desc = str(row.get('Descriere', '')).strip()

            try:
                stock_raw = row.get('Stoc numeric', 0)
                if pd.isna(stock_raw):
                    stock = 0
                else:
                    stock = int(stock_raw)
            except:
                stock = 0

            link = str(row.get('Link produs', '')).strip()
            image_link = str(row.get('Imagine (principala)',
                             row.get('image_link', ''))).strip()

            if name and price > 0:
                self.products.append(
                    (name, price, desc, stock, link, image_link))

        logger.info(f"✅ Loaded {len(self.products)} products from feed")

        if self.products:
            sample = self.products[0]
            logger.info(
                f"📦 Sample: {sample[0][:30]}, {sample[1]} RON, stock={sample[3]}")

    def load_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception:
            self.config = {}

    # 🎯 NEW: Category Detection
    def detect_category(self, user_message):
        """Detect product category from user message"""
        message_lower = user_message.lower()

        # Priority order (check specific first)
        if any(word in message_lower for word in ['compleu', 'compleuri', 'costum', 'costume', 'set']):
            return 'compleuri'
        elif any(word in message_lower for word in ['camasa', 'camasi', 'cămașă', 'cămași', 'bluza', 'bluze']):
            return 'camasi'
        elif any(word in message_lower for word in ['pantalon', 'pantaloni', 'blugi', 'jeans']):
            return 'pantaloni'
        elif any(word in message_lower for word in ['rochie', 'rochii', 'dress']):
            return 'rochii'
        else:
            return 'general'

    def deduplicate_products(self, products, category=None):
        """Remove duplicates (same item, different colors/sizes)"""
        seen_base_names = set()
        unique = []

        for product in products:
            name = product[0].lower() if product[0] else ''
            base_name = name

            # Remove colors
            colors = [
                'neagra', 'neagră', 'negru',
                'alba', 'albă', 'alb',
                'rosie', 'roșie', 'rosu', 'roșu',
                'albastra', 'albastră', 'albastru',
                'verde', 'verzi',
                'bordo', 'burgundy',
                'aurie', 'auriu',
                'galbena', 'galbenă', 'galben',
                'maro', 'maroniu',
                'bej', 'crem',
                'bleu', 'blue',
                'turcoaz',
                'mov', 'violet', 'lila',
                'portocaliu', 'orange',
                'roz', 'pink'
            ]

            # 🎯 NEW: Remove sizes
            sizes = ['xs', 'x s', 's', 'm', 'l', 'xl', 'x l', 'xxl', 'x x l',
                     'marime s', 'marime m', 'marime l', 'marime xl']

            for color in colors:
                base_name = re.sub(r'\b' + color + r'\b', '',
                                   base_name, flags=re.IGNORECASE)

            for size in sizes:
                base_name = re.sub(r'\b' + size + r'\b', '',
                                   base_name, flags=re.IGNORECASE)

            base_name = ' '.join(base_name.split()).strip()

            if base_name and base_name not in seen_base_names:
                seen_base_names.add(base_name)
                unique.append(product)

        logger.info(f"🔍 Deduplication: {len(products)} → {len(unique)} unique")
        return unique

    def extract_price_range(self, query):
        """Extract price range from query"""
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

    def search_products(self, query, limit=3, max_price=None, category=None):
        """Search products by category and keywords"""
        if not self.products:
            return []

        # Detect category if not specified
        if category is None:
            category = self.detect_category(query)

        query_lower = query.lower()

        # Category-specific keywords
        category_keywords = {
            'rochii': ['rochie', 'rochii', 'dress'],
            'compleuri': ['compleu', 'compleuri', 'costum', 'set'],
            'camasi': ['camasa', 'camasi', 'cămașă', 'bluza'],
            'pantaloni': ['pantalon', 'pantaloni', 'blugi', 'jeans']
        }

        stop_words = {'sub', 'peste', 'vreau', 'caut', 'imi', 'trebuie',
                      'doresc', 'lei', 'ron', 'pentru', 'cu', 'de', 'la', 'in', 'si', 'sau'}
        keywords = [w.strip() for w in query_lower.split() if w.strip(
        ) and w.strip() not in stop_words and not w.strip().isdigit()]

        color_normalizations = {
            'rosii': 'rosie', 'roșii': 'rosie',
            'negre': 'neagra', 'negru': 'neagra',
            'albe': 'alba', 'alb': 'alba',
            'verzi': 'verde',
        }

        normalized_keywords = [
            color_normalizations.get(kw, kw) for kw in keywords]

        results = []

        for product in self.products:
            name = product[0].lower() if product[0] else ''
            desc = product[2].lower() if product[2] else ''
            price = product[1]

            score = 0

            # Keyword matching
            for keyword in normalized_keywords:
                if keyword in name:
                    score += 10
                elif keyword in desc:
                    score += 5

            # 🎯 NEW: Category bonus
            if category in category_keywords:
                for cat_kw in category_keywords[category]:
                    if cat_kw in name:
                        score += 5

            # Price filtering
            if max_price is not None and price > max_price:
                score = 0

            if score > 0:
                results.append((product, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in results[:limit]]

    def is_in_stock(self, product):
        if len(product) >= 4:
            return product[3] > 0
        return True

    def search_products_in_stock(self, query, limit=4, category=None):
        """Search with deduplication"""
        max_price = self.extract_price_range(query)

        all_results = self.search_products(
            query, limit * 3, max_price=max_price, category=category)

        if all_results:
            in_stock = [p for p in all_results if self.is_in_stock(p)]

            if in_stock:
                unique_products = self.deduplicate_products(in_stock, category)
                return unique_products[:limit]
            else:
                logger.warning(f"⚠️ No in-stock products for '{query}'")
                unique_products = self.deduplicate_products(
                    all_results, category)
                return unique_products[:limit]

        return []

    def get_delivery_time(self, product_name):
        """Return delivery time based on brand"""
        if product_name and 'trendya' in product_name.lower():
            return "5-7 zile lucrătoare"
        else:
            return "1-2 zile lucrătoare"

    # 🎯 OPTIMIZATION: Short product context (Strategy 3)
    def format_products_for_context_short(self, products):
        """SHORT product context for GPT (save tokens!)"""
        if not products:
            return "Niciun produs găsit."

        # Just essentials: name, price, stock
        lines = []
        for i, p in enumerate(products, 1):
            stock = "✅" if p[3] > 0 else "❌"
            lines.append(f"{i}. {p[0]} - {p[1]} RON {stock}")

        return "\n".join(lines)

    # 🎯 NEW: Contextual messages per category
    def get_contextual_message(self, user_message, category=None):
        """Generate short message based on category and context"""
        if category is None:
            category = self.detect_category(user_message)

        message_lower = user_message.lower()

        # ROCHII
        if category == 'rochii':
            if "nunta" in message_lower or "eveniment" in message_lower:
                return "🎉 Iată rochii elegante pentru eveniment:"
            elif "casual" in message_lower:
                return "👗 Iată rochii casual:"
            elif "seara" in message_lower or "party" in message_lower:
                return "✨ Iată rochii de seară:"
            else:
                return "👗 Iată câteva rochii pentru tine:"

        # COMPLEURI
        elif category == 'compleuri':
            if "birou" in message_lower or "office" in message_lower:
                return "💼 Iată compleuri elegante pentru birou:"
            elif "casual" in message_lower:
                return "👔 Iată compleuri casual:"
            else:
                return "👔 Iată câteva compleuri pentru tine:"

        # CAMASI
        elif category == 'camasi':
            if "eleganta" in message_lower or "elegante" in message_lower:
                return "👕 Iată cămăși elegante:"
            else:
                return "👕 Iată câteva cămăși pentru tine:"

        # PANTALONI
        elif category == 'pantaloni':
            if "blugi" in message_lower or "jeans" in message_lower:
                return "👖 Iată blugi pentru tine:"
            else:
                return "👖 Iată câteva pantaloni pentru tine:"

        # GENERAL
        else:
            return "🎀 Iată câteva produse pentru tine:"

    # 🎯 OPTIMIZATION: FAQ Cache Check (Strategy 2)
    def check_faq_cache(self, user_message):
        """Check if message matches FAQ - return cached response"""
        message_lower = user_message.lower().strip()
        clean_msg = message_lower.replace('?', '').replace('.', '').strip()

        # Exact match
        if clean_msg in self.faq_cache:
            logger.info(f"💾 FAQ Cache HIT: {clean_msg[:30]}")
            return self.faq_cache[clean_msg]

        # Partial match
        for key, response in self.faq_cache.items():
            if key in clean_msg:
                logger.info(f"💾 FAQ Cache PARTIAL HIT: {key}")
                return response

        return None

    # 🎯 OPTIMIZATION: Rate Limiting (Strategy 6)
    def check_rate_limit(self, session_id):
        """Check if user exceeded personal limit (10 req/min)"""
        now = time.time()

        if session_id not in self.user_limits:
            self.user_limits[session_id] = []

        # Clean old requests (older than 1 minute)
        self.user_limits[session_id] = [
            req_time for req_time in self.user_limits[session_id]
            if now - req_time < 60
        ]

        # Check limit: max 10 requests per minute
        if len(self.user_limits[session_id]) >= 10:
            logger.warning(
                f"⚠️ Rate limit exceeded for session: {session_id[:8]}")
            return False

        # Add current request
        self.user_limits[session_id].append(now)
        return True

    # 🎯 OPTIMIZATION: Conversation Memory (Strategy 7)
    def is_followup_question(self, message):
        """Detect if referring to previous results"""
        followup_patterns = [
            'prima', 'primul', 'a doua', 'al doilea', 'a treia', 'ultima',
            'asta', 'aceasta', 'acestea', 'cea', 'cel',
            'mai mult', 'detalii', 'info', 'informatii',
            'spune-mi despre', 'vreau sa stiu'
        ]
        return any(pattern in message.lower() for pattern in followup_patterns)

    def user_wants_products(self, user_message):
        """Detect if user is asking for products or just info"""
        message_lower = user_message.lower()

        # FAQ keywords = user NU vrea produse
        faq_keywords = [
            'livrare', 'transport', 'cost', 'plata', 'ramburs',
            'retur', 'returnare', 'schimb', 'cum fac',
            'contact', 'email', 'telefon', 'program', 'orar',
            'cat costa', 'cum comand', 'marime', 'size'
        ]

        # Check if it's a FAQ question
        for keyword in faq_keywords:
            if keyword in message_lower:
                return False  # User wants INFO, not products

        # Product keywords = user WANTS products
        product_keywords = [
            'rochie', 'rochii', 'compleu', 'compleuri',
            'camasa', 'camasi', 'pantalon', 'pantaloni',
            'blugi', 'dress', 'vreau', 'caut', 'arată-mi', 'arata'
        ]

        # Check if asking for products
        for keyword in product_keywords:
            if keyword in message_lower:
                return True  # User wants PRODUCTS

        # Default: if unclear, assume general question
        return False

    def get_response(self, user_message, session_id=None, user_ip=None, user_agent=None):
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"📩 Chat request: {user_message[:50]}...")

        try:
            # 🎯 OPTIMIZATION 1: Rate Limiting (Strategy 6)
            if not self.check_rate_limit(session_id):
                return {
                    "response": "⏳ Prea multe mesaje! Te rog așteaptă puțin.",
                    "status": "rate_limited",
                    "session_id": session_id
                }

            # 🎯 OPTIMIZATION 2: FAQ Cache (Strategy 2) - Check FIRST!
            cached_response = self.check_faq_cache(user_message)
            if cached_response:
                db.save_conversation(
                    session_id, user_message, cached_response, user_ip, user_agent, True)

                return {
                    "response": cached_response,
                    "products": [],
                    "status": "success",
                    "session_id": session_id,
                    "cached": True
                }

            # 🎯 OPTIMIZATION 3: Conversation Memory (Strategy 7)
            if self.is_followup_question(user_message):
                cached = self.conversation_cache.get(session_id, {})
                last_products = cached.get('products', [])

                if last_products:
                    # Simple response without GPT call
                    response_text = "Pentru mai multe detalii despre produse, click pe 'Vezi Produs' în carousel!"

                    db.save_conversation(
                        session_id, user_message, response_text, user_ip, user_agent, True)

                    return {
                        "response": response_text,
                        "products": [],
                        "status": "success",
                        "session_id": session_id,
                        "cached": True
                    }

            # Detect category
            category = self.detect_category(user_message)
            logger.info(f"📂 Detected category: {category}")

            # Search products
            products = self.search_products_in_stock(
                user_message, limit=4, category=category)

            # 🎯 OPTIMIZATION 4: Short Product Context (Strategy 3 & 4)
            if products:
                product_summary = f"Am găsit {len(products)} produse relevante în categoria {category}."
            else:
                product_summary = "Nu am găsit produse care să corespundă."

            # 🎯 OPTIMIZATION 5: SHORT System Prompt (Strategy 3)
            system_prompt = f"""Ești Maria, asistent virtual ejolie.ro.

Vindem: rochii, compleuri, cămăși, pantaloni.

REGULI:
- Pentru recomandări: răspuns SCURT (max 10 cuvinte)
- Pentru FAQ: răspuns direct
- Produsele apar în carousel automat

INFO:
- Livrare: 19 lei (gratuit >200 lei), 1-2 zile
- Retur: 14 zile
- Email: contact@ejolie.ro

{product_summary}
"""

            logger.info("🔄 Calling GPT-4o-mini...")  # 🎯 Strategy 1!

            # 🎯 OPTIMIZATION 6: GPT-4o-mini + Reduced tokens (Strategy 1 & 5)
            response = openai.chat.completions.create(
                model="gpt-4o-mini",  # ← 15x CHEAPER than GPT-4o!
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=150,  # ← Reduced from 500!
                temperature=0.5,
                timeout=15
            )

            bot_response = response.choices[0].message.content
            logger.info(f"✅ GPT response received")

            # Prepare products for frontend
            products_for_frontend = []
            for product in products:
                if len(product) >= 6:
                    products_for_frontend.append({
                        "name": product[0],
                        "price": f"{product[1]:.2f} RON",
                        "description": product[2][:150] + "..." if len(product[2]) > 150 else product[2],
                        "stock": product[3],
                        "link": product[4],
                        "image": product[5]
                    })

            # 🎯 SHORT RESPONSE: Override ONLY if user wants products
            if products_for_frontend and len(products_for_frontend) > 0:
                if self.user_wants_products(user_message):
                    bot_response = self.get_contextual_message(
                        user_message, category)
                    logger.info(f"✂️ Short response applied: {bot_response}")
                else:
                    # User asked info question but we found products - use GPT response
                    logger.info(
                        f"ℹ️ Info question detected, using GPT response")

            # 🎯 OPTIMIZATION: Cache products for follow-ups
            self.conversation_cache[session_id] = {
                'products': products,
                'timestamp': datetime.now(),
                'category': category
            }

            # Save to database
            db.save_conversation(
                session_id, user_message, bot_response, user_ip, user_agent, True
            )

            return {
                "response": bot_response,
                "products": products_for_frontend,
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


# ✅ Bot instance
bot = ChatBot()
