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
        """Load products from CSV feed"""
        if not os.path.exists('products.csv'):
            self.products = []
            return

        try:
            # ✅ Read CSV with comma separator (NOT tab!)
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
            # ✅ USE CORRECT CSV COLUMNS from your file
            name = str(row.get('Nume', '')).strip()

            # Price: handle both float and string formats
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

            # Description - use the plain text version
            desc = str(row.get('Descriere', '')).strip()

            # Stock: use the numeric stock column
            try:
                stock_raw = row.get('Stoc numeric', 0)
                if pd.isna(stock_raw):
                    stock = 0
                else:
                    stock = int(stock_raw)
            except:
                stock = 0

            # Link
            link = str(row.get('Link produs', '')).strip()

            # ✅ IMAGE LINK - This is the KEY field for carousel!
            # Try both column names
            image_link = str(row.get('Imagine (principala)',
                             row.get('image_link', ''))).strip()

            # Only add products with valid name and price
            if name and price > 0:
                # Append as tuple: (name, price, desc, stock, link, image_link)
                self.products.append(
                    (name, price, desc, stock, link, image_link))

        logger.info(f"✅ Loaded {len(self.products)} products from feed")

        # Log sample for debugging
        if self.products:
            sample = self.products[0]
            logger.info(
                f"📦 Sample product: name={sample[0][:30]}, price={sample[1]}, stock={sample[3]}, has_image={bool(sample[5])}")

    def load_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception:
            self.config = {}

    def deduplicate_products(self, products):
        """
        Elimină produse duplicate (aceeași rochie, culori diferite)

        Exemplu:
        - "Rochie Elysia neagra" și "Rochie Elysia bordo" → păstrează doar prima
        """
        seen_base_names = set()
        unique = []

        for product in products:
            name = product[0].lower() if product[0] else ''

            # Elimină cuvinte de culoare comune din română
            base_name = name
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

            for color in colors:
                # Remove color words (with word boundaries)
                base_name = re.sub(r'\b' + color + r'\b', '',
                                   base_name, flags=re.IGNORECASE)

            # Elimină spații multiple și strip
            base_name = ' '.join(base_name.split()).strip()

            # Only add if we haven't seen this base name before
            if base_name and base_name not in seen_base_names:
                seen_base_names.add(base_name)
                unique.append(product)

        logger.info(
            f"🔍 Deduplication: {len(products)} → {len(unique)} unique products")
        return unique

    def extract_price_range(self, query):
        """Extract price range from query like 'sub 500' or 'sub 300 lei'"""
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

        # ✅ Extract search keywords (split by spaces, remove common words)
        stop_words = {'sub', 'peste', 'vreau', 'caut', 'imi', 'trebuie',
                      'doresc', 'lei', 'ron', 'pentru', 'cu', 'de', 'la', 'in', 'si', 'sau'}
        keywords = [w.strip() for w in query_lower.split() if w.strip(
        ) and w.strip() not in stop_words and not w.strip().isdigit()]

        # ✅ Normalize colors (rosii -> rosie, negre -> neagra, etc.)
        color_normalizations = {
            'rosii': 'rosie',
            'rosie': 'rosie',
            'roșii': 'rosie',
            'roșie': 'rosie',
            'negre': 'neagra',
            'negru': 'neagra',
            'albe': 'alba',
            'alb': 'alba',
            'albastru': 'albastra',
            'albastră': 'albastra',
            'verzi': 'verde',
            'galbene': 'galbena',
            'galben': 'galbena',
            'roz': 'roz',
            'mov': 'mov',
        }

        normalized_keywords = []
        for kw in keywords:
            normalized_keywords.append(color_normalizations.get(kw, kw))

        results = []

        for product in self.products:
            name = product[0].lower() if product[0] else ''
            desc = product[2].lower() if product[2] else ''
            price = product[1]

            score = 0

            # ✅ Score based on keyword matches (not exact phrase)
            for keyword in normalized_keywords:
                if keyword in name:
                    score += 10
                elif keyword in desc:
                    score += 5

            # ✅ Bonus for category match (rochie, rochii -> rochie)
            if any(word in ['rochie', 'rochii'] for word in keywords):
                if 'rochie' in name:
                    score += 3

            # ✅ Price filtering
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

    def search_products_in_stock(self, query, limit=4):
        """
        Search with smart price extraction and deduplication

        🎯 NOW RETURNS 4 PRODUCTS (not 3) and removes duplicates!
        """
        max_price = self.extract_price_range(query)

        # Search for MORE products initially (to have room for deduplication)
        all_results = self.search_products(
            query, limit * 3, max_price=max_price)

        if all_results:
            in_stock = [p for p in all_results if self.is_in_stock(p)]

            if in_stock:
                # 🎯 DEDUPLICATE before returning!
                unique_products = self.deduplicate_products(in_stock)
                # Return up to 4 unique products
                return unique_products[:limit]
            else:
                logger.warning(
                    f"⚠️ No in-stock products for '{query}', showing all matches")
                unique_products = self.deduplicate_products(all_results)
                return unique_products[:limit]

        return []

    def get_delivery_time(self, product_name):
        """Return delivery time based on brand"""
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
        image = product[5] if len(product) >= 6 else ""  # 🎯 NEW: image field

        stock_status = "✅ În stoc" if stock > 0 else "⚠️ Epuizat"
        delivery_time = self.get_delivery_time(name)

        base = f"🎀 {name} - {price} RON [{stock_status}]\n📝 {desc}\n⏱️ Livrare: {delivery_time}"

        if link:
            base += f"\n🔗 {link}"

        return base

    def format_products_for_context(self, products):
        if not products:
            return "❌ Niciun produs găsit în criteriile tale."

        return "\n\n".join(self.format_product(p) for p in products)

    def get_response(self, user_message, session_id=None, user_ip=None, user_agent=None):
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(f"📩 Chat request: {user_message[:50]}...")

        try:
            # 🎯 Search for 4 products (not 3) with deduplication
            products = self.search_products_in_stock(user_message, limit=4)
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

            # ✅ ANTI-HALLUCINATION PROMPT
            system_prompt = f"""Tu ești Maria, asistentul virtual al magazinului online ejolie.ro, care vinde rochii pentru femei.

⚠️ INSTRUCȚIUNE CRITICĂ - CITIT CU ATENTIE:
**POTI RECOMANDA NUMAI ROCHIILE DIN LISTA "PRODUSE DISPONIBILE" DE MAI JOS!**
**NU INVENTA PRODUSE! NU MODIFICA NUME, PRETURI SAU LINK-URI!**
**DACA NU GASESTI PRODUS IN LISTA, SPUNE CLAR: "Ne pare rău, nu avem rochii care să se potrivească criteriilor tale momentan"**

INSTRUCȚIUNI GENERALE:
1. RĂSPUNZI DOAR LA ÎNTREBĂRI DESPRE ROCHII, PRETURI, COMENZI, LIVRARE ȘI RETUR
2. Dacă întrebarea nu e legată de rochii, cere politicos să reformuleze
3. Fii prietenos și helpful în toate răspunsurile

REGULI STRICTE PENTRU RECOMANDĂRI:
✅ TREBUIE SĂ FACI:
- Recomandă NUMAI produse care sunt în lista de mai jos
- Copie EXACT numele produselor din lista
- Copie EXACT link-urile din lista (fără modificări!)
- Copie EXACT prețurile din lista
- Include status-ul din listă (în stoc / epuizat)
- Afișează descrierea produsului din listă
- Include timp livrare pentru fiecare produs

❌ NU TREBUIE SĂ FACI:
- NU inventa produse! (ex: "Rochie Fantasy Blue" dacă nu e în listă)
- NU rescrii sau parafrazezi niciodată numele produselor!
- NU modifica link-uri sau preturi!
- NU sugera produse care nu sunt în listă!
- NU folosi markdown [text](url) pentru link-uri - doar plain text!

EXEMPLU DE RĂSPUNS CORECT:
✅ "🎀 Desigur! Iată 4 rochii disponibile:
   1. Rochie Red Passion - 850 RON [În stoc]
   📝 O rochie seducătoare, perfectă pentru evenimente speciale.
   ⏱️ Livrare: 1-2 zile
   🔗 https://ejolie.ro/product/rochie-red-passion-12345
   
   2. Rochie Scarlet Elegance - 890 RON [În stoc]
   📝 Elegantă și rafinată, ideală pentru seară.
   ⏱️ Livrare: 1-2 zile
   🔗 https://ejolie.ro/product/rochie-scarlet-elegance-12346"

EXEMPLU DE RĂSPUNS GREȘIT (NU FACE!):
❌ "Iată rochie Fantasy Blue - 750 RON" ← INVENTATA! Nu e în listă!
❌ "Iată rochie Aurora Pink" ← INVENTATA! Nu sunt în listă!

RASPUNS CAND NU GASESTI PRODUSE:
"Ne pare rău, momentan nu avem rochii care să se potrivească exact criteriilor tale. Te pot ajuta cu alte culori sau preturi?"

📌 **Informații fixe:**
- Cost livrare: **19 lei** oriunde în România
- Transport gratuit peste 200 lei
- Termen livrare: **5–7 zile lucrătoare** (Trendya), **1-2 zile** (altele)
- Retur: **14 zile** calendaristice
- Email: **contact@ejolie.ro**
- Website: **https://ejolie.ro**

Politica retur: {return_policy}

═════════════════════════════════════════════════════════════
📦 LISTA EXACTA DE PRODUSE (NUMAI ACESTEA!):
═════════════════════════════════════════════════════════════
{products_context}
═════════════════════════════════════════════════════════════

INFORMAȚII FRECVENTE:
{faq_text}

REGULI CUSTOM:
{custom_rules_text}

STIL DE COMUNICARE:
- Foloseste emoji (🎀, 👗, ✅, 🔗, ⏱️)
- Fii prietenos și helpful
- Dă răspunsuri concise (max 4 produse)
- VERIFICA mereu LISTA înainte să recomanzi
- Include NUME EXACT, PRET EXACT, LINK EXACT
- Include timp livrare
- Întreabă despre ocazie pentru recomandări mai bune

⚠️ AVERTISMENT FINAL:
DACA RECOMANZI UN PRODUS CARE NU E IN LISTA, GRESESTI!
VERIFICA MEREU LISTA INAINTE SA RECOMANZI!
"""

            logger.info("🔄 Calling GPT-4o...")

            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=500,  # Increased from 300 for 4 products
                temperature=0.5,
                timeout=15
            )

            bot_response = response.choices[0].message.content
            logger.info(f"✅ GPT response received")

            # 🎯 NEW: Prepare products array for frontend (with images!)
            products_for_frontend = []
            for product in products:
                if len(product) >= 6:  # Must have all 6 fields including image
                    products_for_frontend.append({
                        "name": product[0],
                        "price": f"{product[1]:.2f} RON",
                        "description": product[2][:150] + "..." if len(product[2]) > 150 else product[2],
                        "stock": product[3],
                        "link": product[4],
                        "image": product[5]  # 🎯 IMAGE LINK FOR CAROUSEL!
                    })

            # Save to database
            db.save_conversation(
                session_id, user_message, bot_response, user_ip, user_agent, True
            )

            return {
                "response": bot_response,
                "products": products_for_frontend,  # 🎯 NEW: Array with products + images!
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
