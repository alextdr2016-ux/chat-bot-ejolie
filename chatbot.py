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
from extended_api import extended_api
from faq_matcher import FAQMatcher  # ← NOU! Importăm matcher-ul

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

        # 🎯 NEW: Extract all product names (NO HARDCODING!)
        self.product_names = self.extract_all_product_names()
        logger.info(
            f"✅ Extracted {len(self.product_names)} unique product names")

        # 🎯 NEW: FAQ Matcher Inteligent (înlocuiește faq_cache vechi)
        self.faq_matcher = FAQMatcher('faq_config.json')  # ← NOU!
        logger.info("✅ FAQ Matcher initialized")

        # 🎯 OPTIMIZATION: Rate Limiting per User (Strategy 6)
        self.user_limits = {}

        # 🎯 OPTIMIZATION: Conversation Memory (Strategy 7)
        self.conversation_cache = {}

        logger.info("🤖 ChatBot initialized with optimizations")

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

    # 🎯 NEW: Auto-extract product names (NO HARDCODING!)
    def extract_all_product_names(self):
        """Extract unique product base names from products list

        Returns:
            set: Unique product names (e.g. {'marina', 'veda', 'florence'})
        """
        product_names = set()

        for product in self.products:
            product_name = product[0]  # "Rochie Marina roșie"
            base_name = self.extract_base_name(product_name)

            if base_name:
                product_names.add(base_name.lower())

        logger.info(
            f"📋 Extracted product names: {sorted(list(product_names))[:10]}...")
        return product_names

    def extract_base_name(self, full_product_name):
        """Extract base model name from full product name

        Args:
            full_product_name: "Rochie Marina roșie"

        Returns:
            str: "Marina"
        """
        name = full_product_name.lower()

        # Remove category words
        category_words = ['rochie', 'rochii', 'compleu', 'compleuri',
                          'pantalon', 'pantaloni', 'camasa', 'camasi',
                          'bluza', 'bluze', 'fusta', 'fuste']
        for word in category_words:
            name = name.replace(word, '').strip()

        # Remove common color words
        color_words = ['rosu', 'rosie', 'roșu', 'roșie',
                       'negru', 'neagra', 'neagră',
                       'alb', 'alba', 'albă',
                       'albastru', 'albastra', 'albastră',
                       'verde', 'verzi',
                       'galben', 'galbena', 'galbenă',
                       'roz', 'portocaliu', 'mov', 'violet',
                       'maro', 'bej', 'gri', 'argintiu', 'auriu']
        for color in color_words:
            name = name.replace(color, '').strip()

        # Remove size words
        size_words = ['xs', 's', 'm', 'l', 'xl', 'xxl', 'xxxl']
        for size in size_words:
            name = name.replace(size, '').strip()

        # Get first meaningful word (usually the model name)
        words = name.split()
        meaningful_words = [w for w in words if len(w) > 2]

        if meaningful_words:
            return meaningful_words[0].capitalize()

        return ""

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

    def extract_price_range_advanced(self, query):
        """Extract price range (single limit or range)"""
        query_lower = query.lower()

        # Range: 100-200, între 100 și 200
        range_patterns = [
            r'(\d+)\s*-\s*(\d+)',  # 100-200
            r'intre\s+(\d+)\s+si\s+(\d+)',  # între 100 și 200
            r'intre\s+(\d+)\s+(\d+)',  # între 100 200
            r'de\s+la\s+(\d+)\s+la\s+(\d+)',  # de la 100 la 200
        ]

        for pattern in range_patterns:
            match = re.search(pattern, query_lower)
            if match:
                return {
                    'min': float(match.group(1)),
                    'max': float(match.group(2))
                }

        # Single limit (sub, peste, mai ieftin de)
        single_patterns = [
            (r'sub\s+(\d+)', 'max'),
            (r'pana\s+la\s+(\d+)', 'max'),
            (r'mai\s+ieftin\s+de\s+(\d+)', 'max'),
            (r'maxim\s+(\d+)', 'max'),
            (r'peste\s+(\d+)', 'min'),
            (r'mai\s+scump\s+de\s+(\d+)', 'min'),
            (r'minim\s+(\d+)', 'min'),
        ]

        for pattern, limit_type in single_patterns:
            match = re.search(pattern, query_lower)
            if match:
                value = float(match.group(1))
                if limit_type == 'max':
                    return {'max': value}
                else:
                    return {'min': value}

        return None

    def extract_materials(self, query):
        """Extract material filters from query"""
        query_lower = query.lower()

        materials_map = {
            'catifea': ['catifea', 'velur', 'velvet'],
            'dantela': ['dantela', 'dantelă', 'lace'],
            'matase': ['matase', 'mătase', 'silk'],
            'bumbac': ['bumbac', 'cotton'],
            'in': ['in', 'în', 'linen'],
            'poliester': ['poliester', 'polyester'],
            'vascoza': ['vascoza', 'viscoză', 'viscose'],
            'piele': ['piele', 'leather'],
            'lana': ['lana', 'lână', 'wool']
        }

        detected_materials = []
        for material, keywords in materials_map.items():
            if any(kw in query_lower for kw in keywords):
                detected_materials.append(material)

        return detected_materials

    def extract_colors_multiple(self, query):
        """Extract multiple colors from query"""
        query_lower = query.lower()

        colors_map = {
            'neagra': ['neagra', 'neagră', 'negru', 'black'],
            'alba': ['alba', 'albă', 'alb', 'white'],
            'rosie': ['rosie', 'roșie', 'rosu', 'roșu', 'red'],
            'albastra': ['albastra', 'albastră', 'albastru', 'blue'],
            'verde': ['verde', 'green'],
            'bordo': ['bordo', 'burgundy', 'visiniu'],
            'aurie': ['aurie', 'auriu', 'gold'],
            'galbena': ['galbena', 'galbenă', 'galben', 'yellow'],
            'maro': ['maro', 'maroniu', 'brown'],
            'bej': ['bej', 'crem', 'beige', 'cream'],
            'turcoaz': ['turcoaz', 'turquoise'],
            'mov': ['mov', 'violet', 'lila', 'purple'],
            'roz': ['roz', 'pink'],
            'portocaliu': ['portocaliu', 'orange']
        }

        detected_colors = []
        for color, keywords in colors_map.items():
            if any(kw in query_lower for kw in keywords):
                detected_colors.append(color)

        return detected_colors

    def extract_sort_preference(self, query):
        """Extract sorting preference"""
        query_lower = query.lower()

        # Cheapest first
        if any(kw in query_lower for kw in ['ieftin', 'mai ieftin', 'cele mai ieftine', 'pret mic']):
            return 'price_asc'

        # Most expensive first
        if any(kw in query_lower for kw in ['scump', 'mai scump', 'cele mai scumpe', 'pret mare']):
            return 'price_desc'

        # Newest first
        if any(kw in query_lower for kw in ['nou', 'noi', 'cele mai noi', 'ultimele']):
            return 'newest'

        return None

    def extract_order_number(self, query):
        """Extract order number from query"""
        query_lower = query.lower()

        # Patterns for order detection
        patterns = [
            r'comanda\s*#?(\d+)',
            r'comanda\s+nr\s*\.?\s*(\d+)',
            r'order\s*#?(\d+)',
            r'nr\s*\.?\s*comanda\s*:?\s*(\d+)',
            r'(?:unde|status|tracking).*?(\d{5,})',  # 5+ digits
        ]

        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                order_id = match.group(1)
                logger.info(f"📦 Detected order ID: {order_id}")
                return order_id

        return None

    def format_order_response(self, order_data):
        """Format order data into elegant response"""
        if not order_data:
            return None

        response = f"""Comanda #{order_data['id']}

Status: {order_data['status']}
Data: {order_data['data']}

Detalii:
- Produse: {order_data['produse_count']} articole
- Total: {order_data['total']} RON
- Livrare: {order_data['metoda_livrare']} ({order_data['livrare_cost']} RON)
- Plată: {order_data['metoda_plata']}"""

        # Add AWB info if available
        if order_data['awb']:
            response += f"\n\nTracking AWB:"
            response += f"\n• Număr: {order_data['awb']}"
            response += f"\n• Status: {order_data['awb_status']}"

            if order_data['awb_link']:
                response += f"\n• Link tracking: {order_data['awb_link']}"

            # Add tracking stages if available
            if order_data['stadii'] and len(order_data['stadii']) > 0:
                response += f"\n\nIstoric livrare:"
                # stadii is a dict, convert to list and get last 3
                stadii_list = list(order_data['stadii'].values())
                for stadiu in stadii_list[:3]:  # Show last 3 stages
                    status_text = stadiu.get('status', '')
                    data_text = stadiu.get('data', '')
                    response += f"\n• {status_text} - {data_text}"

        response += f"\n\nContact: 0757 10 51 51 | contact@ejolie.ro"

        return response

    def search_products(self, query, limit=3, max_price=None, category=None, price_range=None, materials=None, colors=None, sort_by=None):
        """Search products with advanced filtering"""
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

            # 🎯 ADVANCED FILTERS

            # Price range filter
            if price_range:
                if 'min' in price_range and price < price_range['min']:
                    score = 0
                if 'max' in price_range and price > price_range['max']:
                    score = 0

            # Material filter
            if materials and score > 0:
                material_found = False
                for material in materials:
                    if material in desc or material in name:
                        score += 3  # Bonus for material match
                        material_found = True
                        break
                if not material_found:
                    score = 0  # Exclude if material not found

            # Color filter (multiple colors OR logic)
            if colors and score > 0:
                color_found = False
                for color in colors:
                    if color in name or color in desc:
                        score += 2  # Bonus for color match
                        color_found = True
                if not color_found:
                    score = 0  # Exclude if no color match

            if score > 0:
                results.append((product, score))

        results.sort(key=lambda x: x[1], reverse=True)

        # 🎯 SORTING
        if sort_by == 'price_asc':
            results.sort(key=lambda x: x[0][1])  # Sort by price ascending
        elif sort_by == 'price_desc':
            # Sort by price descending
            results.sort(key=lambda x: x[0][1], reverse=True)

        return [p[0] for p in results[:limit]]

    def is_in_stock(self, product):
        if len(product) >= 4:
            return product[3] > 0
        return True

    def search_products_in_stock(self, query, limit=4, category=None, deduplicate=True, exact_match=False):
        """Search with optional deduplication and advanced filters

        Args:
            exact_match: If True, only return products that contain the exact search term
        """

        # 🎯 Extract all filters
        price_range = self.extract_price_range_advanced(query)
        materials = self.extract_materials(query)
        colors = self.extract_colors_multiple(query)
        sort_by = self.extract_sort_preference(query)

        # Log detected filters
        if price_range:
            logger.info(f"💰 Price range: {price_range}")
        if materials:
            logger.info(f"🧵 Materials: {materials}")
        if colors:
            logger.info(f"🎨 Colors: {colors}")
        if sort_by:
            logger.info(f"🔢 Sort by: {sort_by}")

        # 🎯 PRIORITY: Try API search first (scalable for 10,000+ products)
        api_results = None

        if exact_match:
            # Extract product name for exact search
            query_clean = self._extract_product_name_for_api(query)
            logger.info(f"🔍 Trying API EXACT search for: '{query_clean}'")

            # Try API exact search
            api_results = extended_api.search_products_exact(
                query=query_clean,
                limit=limit,
                category=category
            )
        else:
            # Try API fuzzy search
            logger.info(f"🔍 Trying API FUZZY search for: '{query}'")

            price_min = price_range.get('min') if price_range else None
            price_max = price_range.get('max') if price_range else None

            api_results = extended_api.search_products_fuzzy(
                query=query,
                limit=limit * 3,  # Get more for filtering
                category=category,
                price_min=price_min,
                price_max=price_max
            )

        # 🎯 Extract exact search term FIRST (for both API and CSV)
        exact_search_term = None
        if exact_match:
            # Remove common words to extract the product name
            query_lower = query.lower()
            remove_words = ['rochie', 'rochii', 'compleu', 'compleuri', 'pantalon',
                            'pantaloni', 'camasa', 'camasi', 'vreau', 'caut', 'cauta',
                            'recomanda', 'arata', 'mi', 'ma', 'o', 'un', 'pentru']

            # Extract the specific product name
            words = query_lower.split()
            product_name_words = [
                w for w in words if w not in remove_words and len(w) > 2]

            if product_name_words:
                exact_search_term = product_name_words[0]
                logger.info(f"🎯 EXACT MATCH search for: '{exact_search_term}'")

        # 🎯 If API returned results, use them
        if api_results is not None and len(api_results) > 0:
            logger.info(f"✅ Using API results: {len(api_results)} products")
            all_results = api_results
        else:
            # 🎯 FALLBACK: Use CSV search (backwards compatibility)
            logger.info(f"⚠️ API unavailable - falling back to CSV search")

            # 🎯 For exact match, search ALL products (no limit) to find all color variants
            search_limit = 9999 if exact_match and exact_search_term else limit * 3

            all_results = self.search_products(
                query,
                search_limit,
                category=category,
                price_range=price_range,
                materials=materials,
                colors=colors,
                sort_by=sort_by
            )

        # 🎯 EXACT MATCH FILTERING (for BOTH API and CSV results)
        if exact_match and exact_search_term and all_results:
            # Filter to only products that contain the exact search term
            filtered_results = []
            for product in all_results:
                product_name_lower = product[0].lower() if product else ""
                # Check if product name contains the exact search term
                if exact_search_term in product_name_lower:
                    filtered_results.append(product)
                    logger.info(f"✅ Exact match found: {product[0]}")

            all_results = filtered_results
            logger.info(
                f"🎯 Exact match filtered results: {len(all_results)} products")

        if all_results:
            in_stock = [p for p in all_results if self.is_in_stock(p)]

            if in_stock:
                if deduplicate:
                    unique_products = self.deduplicate_products(
                        in_stock, category)
                    return unique_products[:limit]
                else:
                    # Show ALL color variants
                    return in_stock[:limit]
            else:
                logger.warning(f"⚠️ No in-stock products for '{query}'")
                if deduplicate:
                    unique_products = self.deduplicate_products(
                        all_results, category)
                    return unique_products[:limit]
                else:
                    return all_results[:limit]

        # 🎯 FIX: Return empty list if no results
        return []

    def _extract_product_name_for_api(self, query):
        """Extract clean product name from query for API search"""
        query_lower = query.lower()

        # Remove common words
        remove_words = ['rochie', 'rochii', 'compleu', 'compleuri',
                        'pantalon', 'pantaloni', 'camasa', 'camasi',
                        'vreau', 'caut', 'cauta', 'recomanda', 'arata',
                        'mi', 'ma', 'o', 'un', 'pentru', 'de', 'cu']

        words = query_lower.split()
        name_words = [w for w in words if w not in remove_words and len(w) > 2]

        # Return first meaningful word or original query
        return name_words[0] if name_words else query_lower.strip()

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

    # 🎯 NEW: Contextual messages per category - ELEGANT, NO EMOJI
    def get_contextual_message(self, user_message, category=None):
        """Generate elegant contextual message based on category - NO EMOJI"""
        if category is None:
            category = self.detect_category(user_message)

        message_lower = user_message.lower()

        # ROCHII
        if category == 'rochii':
            if "nunta" in message_lower or "eveniment" in message_lower:
                return "Am selectat pentru tine cele mai elegante rochii de eveniment din colecția noastră. Fiecare model este ales cu grijă pentru a te face să strălucești în această zi specială."
            elif "casual" in message_lower:
                return "Îți recomand aceste rochii versatile și confortabile, perfecte pentru un stil casual-chic rafinat. Sunt piese care îmbină eleganța cu naturalețea."
            elif "seara" in message_lower or "party" in message_lower:
                return "Am pregătit o selecție rafinată de rochii de seară care vor completa perfect orice ocazie elegantă. Fiecare model este gândit pentru a sublinia frumusețea ta."
            else:
                return "Am căutat printre cele mai frumoase modele din colecția noastră și am selectat aceste rochii special pentru tine. Sper că vei găsi piesa perfectă care să îți reflecte stilul."

        # COMPLEURI
        elif category == 'compleuri':
            if "birou" in message_lower or "office" in message_lower:
                return "Îți recomand aceste compleuri elegante și profesionale, perfecte pentru ținuta de birou. Sunt piese care îmbină stilul cu confortul pentru o zi lungă de lucru."
            elif "casual" in message_lower:
                return "Am selectat compleuri versatile care îmbină confortul cu eleganța, ideale pentru un look casual-chic. Acestea pot fi purtate atât zi de zi cât și la evenimente mai relaxate."
            else:
                return "Am pregătit o selecție de compleuri rafinate care combină stilul cu versatilitatea. Fiecare set este gândit să ofere multiple posibilități de purtare."

        # CAMASI
        elif category == 'camasi':
            if "eleganta" in message_lower or "elegante" in message_lower:
                return "Iată o selecție de cămăși elegante, perfecte pentru ocazii speciale sau ținute business sofisticate. Fiecare piesă adaugă o notă de rafinament garderobei tale."
            else:
                return "Am selectat pentru tine aceste cămăși rafinate care completează orice garderobă. Sunt piese versatile care pot fi purtate în multiple contexte."

        # PANTALONI
        elif category == 'pantaloni':
            if "blugi" in message_lower or "jeans" in message_lower:
                return "Îți recomand acești blugi versatili, perfecti pentru orice ocazie casual. Sunt piese clasice care nu lipsesc niciodată dintr-o garderobă bine gândită."
            else:
                return "Am pregătit o selecție de pantaloni eleganți care îmbină confortul cu stilul. Acestea pot fi integrate ușor în diverse ținute, de la casual la formal."

        # GENERAL (dacă nu detectează categoria specifică)
        else:
            return "Am căutat cu atenție printre piesele noastre și am selectat aceste articole special pentru tine. Sper că vei găsi exact ce cauți."

    # 🎯 OPTIMIZATION: FAQ Cache Check (Strategy 2)
    def check_faq_cache(self, user_message):
        """Check FAQ with strict threshold - EXCLUDE salut if asking for products"""
        message_lower = user_message.lower()

        # 🚫 PRIORITY: Skip FAQ entirely if user is asking for products
        product_request_keywords = [
            'recomanda', 'recomandă', 'arata', 'arată', 'cauta', 'căută',
            'vreau rochie', 'vreau compleu', 'vreau camasa', 'vreau pantalon',
            'caut rochie', 'caut compleu', 'caut camasa', 'caut pantalon',
            'rochie', 'rochii', 'compleu', 'compleuri',
            'camasa', 'camasi', 'cămașă', 'cămași',
            'pantalon', 'pantaloni', 'blugi',
            'produse', 'articol', 'articole'
        ]

        # Dacă user cere produse, skip FAQ complet
        if any(keyword in message_lower for keyword in product_request_keywords):
            logger.info(f"🛍️ Product request detected - SKIPPING FAQ matching")
            return None

        # Altfel, check FAQ normal
        result = self.faq_matcher.get_response(user_message, threshold=70.0)

        if result and result['score'] >= 70.0:
            # 🚫 EXTRA CHECK: Nu returna "salut" dacă e ambiguu
            if result.get('category_id') == 'salut':
                # Verifică dacă e DOAR salut (1-2 cuvinte)
                words = message_lower.split()
                if len(words) > 2:
                    # E o întrebare mai complexă, nu doar salut
                    logger.info(f"⚠️ Salut FAQ skipped (complex question)")
                    return None

            logger.info(
                f"💨 FAQ Match: {result['category_name']} ({result['score']}%)")
            return result['response']

        logger.info(f"ℹ️  No FAQ match - proceeding to product search")
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

        # FAQ keywords = user NU vrea produse (EXPANDED LIST)
        faq_keywords = [
            # Livrare
            'livrare', 'livreaza', 'transport', 'curier', 'colet',
            'cat timp', 'cand ajunge', 'cand primesc', 'durata',

            # Costuri
            'cost', 'cat costa', 'pret livrare', 'taxa',

            # Plata
            'plata', 'platesc', 'card', 'ramburs', 'transfer',

            # Retur & Schimb
            'retur', 'returnare', 'returna', 'returnez',
            'schimb', 'schimba', 'inlocuire',
            'cum fac', 'cum pot', 'pot sa',

            # Contact & Info
            'contact', 'email', 'telefon', 'program', 'orar',
            'cum comand', 'cum plasez', 'cum cumpar',

            # Sizing & Details
            'marime', 'size', 'masura', 'ghid marimi',
            'material', 'compozitie', 'cum se spala',

            # Generale
            'politica', 'conditii', 'termeni'
        ]

        # Check if it's a FAQ question (STRICT MATCH)
        for keyword in faq_keywords:
            if keyword in message_lower:
                return False  # User wants INFO, not products

        # Product keywords = user WANTS products
        product_keywords = [
            'rochie', 'rochii', 'compleu', 'compleuri',
            'camasa', 'camasi', 'pantalon', 'pantaloni',
            'blugi', 'dress', 'vreau', 'caut', 'arată-mi', 'arata',
            'recomanda', 'sugera', 'propune'
        ]

        # Check if asking for products
        for keyword in product_keywords:
            if keyword in message_lower:
                return True  # User wants PRODUCTS

        # Default: if unclear, assume general question
        return False

    def is_product_question(self, user_message):
        """Detect if user is asking specific question about a product

        Returns:
            dict: {'is_question': bool, 'product_name': str, 'question_type': str}
        """
        message_lower = user_message.lower()

        # Question patterns for product details
        question_keywords = {
            'material': ['ce material', 'din ce', 'fabricat', 'tesatura', 'ce stofa'],
            'details': ['are nasturi', 'are fermoare', 'are buzunare', 'are captuseala',
                        'are centura', 'are gluga', 'are maneci'],
            'fit': ['cum se potriveste', 'cum cade', 'la ce marime', 'cum e talia'],
            'length': ['ce lungime', 'cat de lung', 'pana unde', 'cat de scurt'],
            'care': ['cum ingrijesc', 'cum spal', 'se calca', 'se curata'],
            'style': ['cu ce se poarta', 'pentru ce ocazie', 'ce stil', 'cum arata'],
            'color': ['ce culori', 'ce variante', 'culoare disponibil']
        }

        # Check if message contains question keywords
        question_type = None
        for qtype, keywords in question_keywords.items():
            if any(kw in message_lower for kw in keywords):
                question_type = qtype
                break

        if not question_type:
            return {'is_question': False, 'product_name': None, 'question_type': None}

        # Extract product name from question
        query_without_category = message_lower
        for cat_word in ['rochie', 'rochii', 'compleu', 'compleuri', 'pantalon',
                         'pantaloni', 'camasa', 'camasi', 'bluza', 'bluze']:
            query_without_category = query_without_category.replace(
                cat_word, '').strip()

        # Remove question words
        for keywords in question_keywords.values():
            for kw in keywords:
                query_without_category = query_without_category.replace(
                    kw, '').strip()

        # Extract product name
        words = query_without_category.split()
        meaningful_words = [w for w in words if len(
            w) > 2 and w in self.product_names]

        if meaningful_words:
            product_name = meaningful_words[0]
            logger.info(
                f"❓ Product question detected: {question_type} about '{product_name}'")
            return {
                'is_question': True,
                'product_name': product_name,
                'question_type': question_type
            }

        return {'is_question': False, 'product_name': None, 'question_type': None}

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

            # 🎯 OPTIMIZATION 2: FAQ Matcher (Strategy 2) - Check FIRST!
            cached_response = self.check_faq_cache(user_message)
            if cached_response:
                # Obținem și detaliile match-ului pentru logging
                match_details = self.faq_matcher.get_response(user_message)

                # ✅ Conversation saved in main.py (centralized)
                # db.save_conversation(
                #     session_id, user_message, cached_response, user_ip, user_agent, True)

                return {
                    "response": cached_response,
                    "products": [],
                    "status": "success",
                    "session_id": session_id,
                    "cached": True,
                    "faq_matched": True,
                    "faq_category": match_details.get('category_id') if match_details else None,
                    "faq_level": match_details.get('level') if match_details else None
                }

            # 🎯 ORDER TRACKING: Check if user is asking about order
            order_id = self.extract_order_number(user_message)
            if order_id:
                logger.info(f"📦 Order tracking request for order #{order_id}")

                # Fetch order from Extended API
                order_data = extended_api.get_order_status(order_id)

                if order_data:
                    # Format elegant response
                    order_response = self.format_order_response(order_data)

                    # ✅ Conversation saved in main.py (centralized)
                    # db.save_conversation(
                    #     session_id, user_message, order_response, user_ip, user_agent, True)

                    return {
                        "response": order_response,
                        "products": [],
                        "status": "success",
                        "session_id": session_id,
                        "order_tracking": True
                    }
                else:
                    # Order not found
                    error_response = f"""Nu am găsit comanda #{order_id}.

Te rog verifică:
- Numărul comenzii este corect
- Comanda a fost plasată pe ejolie.ro

Pentru asistență: 0757 10 51 51 | contact@ejolie.ro"""

                    # ✅ Conversation saved in main.py (centralized)
                    # db.save_conversation(
                    #     session_id, user_message, error_response, user_ip, user_agent, True)

                    return {
                        "response": error_response,
                        "products": [],
                        "status": "success",
                        "session_id": session_id
                    }
#
#             # 🎯 OPTIMIZATION 3: Conversation Memory (Strategy 7)
#             if self.is_followup_question(user_message):
#                 cached = self.conversation_cache.get(session_id, {})
#                 last_products = cached.get('products', [])
#
#                 if last_products:
#                     # Simple response without GPT call
#                     response_text = "Pentru mai multe detalii despre produse, click pe 'Vezi Produs' în carousel!"
#
#                     db.save_conversation(
#                         session_id, user_message, response_text, user_ip, user_agent, True)
#
#                     return {
#                         "response": response_text,
#                         "products": [],
#                         "status": "success",
#                         "session_id": session_id,
#                         "cached": True
#                     }

            # Detect category
            category = self.detect_category(user_message)
            logger.info(f"📂 Detected category: {category}")

            # 🎯 PRODUCT Q&A: Check if asking specific question about a product
            product_qa = self.is_product_question(user_message)
            if product_qa['is_question']:
                product_name = product_qa['product_name']
                logger.info(
                    f"❓ Product Q&A mode: '{product_qa['question_type']}' about '{product_name}'")

                # Search for specific product (all colors)
                products = self.search_products_in_stock(
                    product_name,
                    limit=10,
                    category=category,
                    deduplicate=False,  # Show ALL colors
                    exact_match=True  # EXACT match for product name
                )

                if products:
                    # Build context from product descriptions
                    product_context = []
                    for p in products:
                        product_context.append({
                            'name': p[0],
                            'price': f"{p[1]:.2f} RON",
                            'description': p[2][:300]  # First 300 chars
                        })

                    # Enhanced system prompt with product details
                    system_prompt = f"""Ești Maria, consultant de stil pentru ejolie.ro.

User întreabă despre produsul specific: {product_name.upper()}

PRODUSE DISPONIBILE (toate variantele):
{json.dumps(product_context, indent=2, ensure_ascii=False)}

INSTRUCȚIUNI SPECIALE:
1. Răspunde SPECIFIC la întrebare bazat pe descrierile produselor
2. Dacă informația există în descriere → răspunde cu detalii concrete
3. Dacă informația NU există → spune elegant "Nu găsesc această informație în descriere, dar..."
4. Menționează că afișezi produsul în carousel cu toate variantele disponibile
5. Dacă sunt mai multe culori, menționează-le elegant

TON: Elegant, profesionist, util - fără emoji
RĂSPUNS: 2-3 propoziții concise și utile

Întrebare user: {user_message}"""

                    logger.info("🔄 Calling GPT-4o-mini for Product Q&A...")

                    response = openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        max_tokens=300,
                        temperature=0.7,
                        timeout=15
                    )

                    bot_response = response.choices[0].message.content
                    logger.info(f"✅ Product Q&A response generated")

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

                    return {
                        "response": bot_response,
                        "products": products_for_frontend,
                        "status": "success",
                        "session_id": session_id,
                        "product_qa": True
                    }
                else:
                    # Product not found
                    logger.warning(
                        f"⚠️ Product '{product_name}' not found for Q&A")
                    # Continue to regular search...

            # Search products
            # 🎯 IMPROVED: Smart detection WITHOUT hardcoded lists!
            # Strategy:
            # - Specific product names → exact match (e.g. "rochie marina")
            # - General descriptions → fuzzy match (e.g. "rochii elegante")
            # - API does ALL the filtering server-side!

            # Analyze query
            words = user_message.split()
            word_count = len(words)

            # Remove common category words to analyze better
            query_without_category = user_message.lower()
            for cat_word in ['rochie', 'rochii', 'compleu', 'compleuri', 'pantalon',
                             'pantaloni', 'camasa', 'camasi', 'bluza', 'bluze']:
                query_without_category = query_without_category.replace(
                    cat_word, '').strip()

            remaining_words = query_without_category.split()
            meaningful_words = [w for w in remaining_words if len(w) > 2]
            meaningful_word_count = len(meaningful_words)

            # 🎯 SMART DETECTION: Specific product vs General description (NO HARDCODING!)
            # METHOD 1: Check if query contains known product name
            is_known_product = any(
                word in self.product_names for word in meaningful_words)

            # METHOD 2: Single uncommon word (probably a product name)
            is_single_word = meaningful_word_count == 1

            # 🎯 DECISION LOGIC (ZERO HARDCODING!):
            # Specific product IF:
            # - Contains a known product name (e.g. "marina", "veda")
            # - OR single uncommon word (probably a new product)
            #
            # Examples:
            # "rochie marina" → "marina" in product_names → SPECIFIC ✅
            # "rochie veda" → "veda" in product_names → SPECIFIC ✅
            # "rochii elegante" → "elegante" NOT in product_names → GENERAL ✅
            # "rochii de ocazie" → "de", "ocazie" NOT in product_names → GENERAL ✅
            # "rochie anastasia" → "anastasia" in product_names → SPECIFIC ✅ (auto!)

            search_for_specific_model = is_known_product or (
                is_single_word and len(meaningful_words[0]) > 4)

            if search_for_specific_model:
                if is_known_product:
                    logger.info(
                        f"🎯 Specific product search: '{user_message}' (known product name)")
                else:
                    logger.info(
                        f"🎯 Specific product search: '{user_message}' (single uncommon word)")
            else:
                logger.info(
                    f"🔍 General search: '{user_message}' (description/attributes)")

            # Search products (with or without deduplication)
            # 🎯 Specific products: show ALL color variants (max 10)
            # 🎯 General search: limit to 10 results for variety
            product_limit = 10  # Same limit for both, but deduplication differs

            products = self.search_products_in_stock(
                user_message,
                limit=product_limit,
                category=category,
                # Don't deduplicate for specific models (show ALL colors!)
                deduplicate=(not search_for_specific_model),
                # 🎯 EXACT MATCH for specific products
                exact_match=search_for_specific_model
            )

            # 🎯 OPTIMIZATION 4: Short Product Context (Strategy 3 & 4)
            if products:
                if search_for_specific_model:
                    # Produs specific - menționează toate variantele
                    if len(products) == 1:
                        product_summary = f"Am găsit produsul specific: {products[0][0]}. Oferă detalii despre produs (material, ocazii, stil)."
                    else:
                        # Simplified - just mention number of variants
                        product_summary = f"Am găsit {len(products)} variante de culoare disponibile. Prezintă toate variantele."
                else:
                    # Căutare generală - răspuns standard
                    product_summary = f"Am găsit {len(products)} produse relevante în categoria {category}."
            else:
                product_summary = "Nu am găsit produse care să corespundă."

            # 🎯 OPTIMIZATION 5: ELEGANT System Prompt - NO EMOJI (Strategy 3)
            system_prompt = f"""Ești Maria, consultant de stil și asistentă virtuală pentru ejolie.ro - magazinul online de rochii și ținute elegante pentru femei.

PERSONALITATEA TA:
- Profesionistă în modă feminină, cu experiență în stilism
- Comunicare caldă, rafinată și elegantă, fără a fi formală sau distantă
- Entuziasm autentic pentru frumusețe și eleganță
- Respect profund pentru gustul și preferințele fiecărei cliente

TON ȘI LIMBAJ:
- Folosește un vocabular ales și expresii feminine elegante
- NICIODATĂ emoji sau emoticoane - eleganța vine din cuvinte
- Evită limbajul prea tehnic sau comercial
- Preferă: "Am selectat pentru tine" în loc de "Am găsit"
- Evită: "Super!", "Perfect!", "Wow!" - folosește expresii rafinate
- Propoziții fluente și bine articulate, nu telegrafice

PENTRU RECOMANDĂRI DE PRODUSE:
Când prezinți produse, oferă un răspuns elegant în 2-4 propoziții care:
1. Recunoaște preferințele clientei
2. Descrie stilul colecției selectate (elegant, sofisticat, versatil)
3. Menționează ocazii potrivite sau cum se poate purta
4. Încheie cu o notă de încredere sau încurajare

Exemple bune:
- "Am căutat cu atenție printre cele mai rafinate modele din colecția noastră și am selectat aceste rochii special pentru tine. Fiecare piesă este perfectă pentru evenimente elegante și va sublinia frumusețea ta naturală."
- "Îmi face plăcere să îți prezint această selecție de compleuri sofisticate. Sunt piese versatile care îmbină eleganța cu confortul, ideale atât pentru birou cât și pentru întâlniri importante."

Exemple proaste (prea scurte sau cu emoji):
- "Iată rochiile! ✨"
- "Am găsit ceva fain pentru tine!"
- "Check this out 👗"

PENTRU ÎNTREBĂRI (FAQ):
- Răspunde complet dar concis
- Ton profesionist și empatic
- Structurează informația clar, fără bullet points excesive
- Oferă soluții, nu doar informații

REGULI IMPORTANTE:
- ZERO emoji sau emoticoane în orice răspuns
- Respectă limba română corectă (diacritice, punctuație)
- Dacă nu știi ceva, îndreaptă elegant către contact
- Nu face promisiuni despre livrare sau stoc fără certitudine
- Pentru probleme complexe, recomandă contactul direct

INFORMAȚII ESENȚIALE:
- Livrare: 19 lei pentru comenzi sub 200 lei, GRATUITĂ peste 200 lei
- Timp livrare: 24-48 ore (zile lucrătoare)
- Politică retur: 14 zile de la primirea produsului
- Contact: 0757 10 51 51 sau contact@ejolie.ro
- Program: Luni - Vineri, 09:00 - 18:00

CONTEXT PRODUSE:
{product_summary}

Răspunde acum clientei cu eleganță și profesionalism, fără emoji."""

            logger.info("🔄 Calling GPT-4o-mini...")

            # 🎯 OPTIMIZATION 6: GPT-4o-mini with appropriate tokens for elegant responses
            response = openai.chat.completions.create(
                model="gpt-4o-mini",  # ← 15x CHEAPER than GPT-4o!
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=300,  # ← Increased for elegant, complete responses
                temperature=0.7,  # ← Slightly higher for more natural, warm tone
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
#             db.save_conversation(
#                 session_id, user_message, bot_response, user_ip, user_agent, True
#             )

            return {
                "response": bot_response,
                "products": products_for_frontend,
                "status": "success",
                "session_id": session_id
            }

        except openai.RateLimitError as e:
            logger.warning(f"⚠️ OpenAI rate limit: {e}")
#             db.save_conversation(
#                 session_id, user_message, "Rate limit", user_ip, user_agent, False
#             )
            return {
                "response": "⏳ Prea multe cereri. Te rog așteaptă câteva secunde.",
                "status": "rate_limited",
                "session_id": session_id
            }

        except openai.AuthenticationError as e:
            logger.error(f"❌ OpenAI Auth error: {e}")
#             db.save_conversation(
#                 session_id, user_message, "Auth failed", user_ip, user_agent, False
#             )
            return {
                "response": "❌ Eroare de autentificare. Verifică OPENAI_API_KEY.",
                "status": "auth_error",
                "session_id": session_id
            }

        except Exception as e:
            logger.error(f"❌ GPT error: {type(e).__name__}: {e}")
#             db.save_conversation(
#                 session_id, user_message, f"Error: {str(e)}", user_ip, user_agent, False
#             )
            return {
                "response": "⚠️ Eroare temporară. Te rog încearcă din nou.",
                "status": "error",
                "session_id": session_id
            }


# ✅ Bot instance
bot = ChatBot()
