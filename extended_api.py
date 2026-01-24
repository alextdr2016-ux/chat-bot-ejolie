import requests
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ExtendedAPI:
    def __init__(self):
        self.api_key = os.getenv('EXTENDED_API_KEY')
        self.base_url = "https://ejolie.ro/api/"

    def search_products_exact(self, query, limit=10, category=None):
        """Search products with EXACT MATCH using platform API

        Args:
            query: Search query (e.g., "marina", "veda")
            limit: Max number of results
            category: Optional category filter

        Returns:
            List of products matching exact query
        """
        if not self.api_key:
            logger.warning(
                "⚠️ EXTENDED_API_KEY not configured - falling back to CSV")
            return None

        try:
            params = {
                'produse': '',              # Endpoint pentru produse
                'cautare': query,           # Query de căutat
                'exact': 1,                 # EXACT MATCH flag
                'limit': limit,
                'apikey': self.api_key
            }

            # Add category filter if provided
            if category:
                params['categorie'] = category

            logger.info(f"🔍 API EXACT search: '{query}' (limit: {limit})")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }

            response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=10
            )

            logger.info(f"📡 API Response status: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"❌ API error: {response.status_code}")
                return None

            data = response.json()

            # Check for API errors
            if isinstance(data, dict) and data.get('eroare') == 1:
                logger.error(f"❌ API error: {data.get('mesaj')}")
                return None

            # Extract products array
            products = data.get('produse', []) if isinstance(
                data, dict) else []

            logger.info(f"✅ API returned {len(products)} products")

            # Format products to match CSV structure
            # Expected: [name, price, description, stock, link, image]
            formatted_products = []
            for p in products:
                try:
                    formatted = [
                        p.get('nume', ''),
                        float(p.get('pret', 0)),
                        p.get('descriere', ''),
                        int(p.get('stoc', 0)),
                        p.get('link', ''),
                        p.get('imagine', '')
                    ]
                    formatted_products.append(formatted)
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ Error formatting product: {e}")
                    continue

            return formatted_products

        except requests.exceptions.Timeout:
            logger.error("❌ API request timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API request error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error in API search: {e}")
            return None

    def search_products_fuzzy(self, query, limit=10, category=None,
                              price_min=None, price_max=None):
        """Search products with FUZZY MATCH (similarity search)

        Args:
            query: Search query
            limit: Max results
            category: Optional category filter
            price_min: Min price filter
            price_max: Max price filter

        Returns:
            List of products matching fuzzy query
        """
        if not self.api_key:
            logger.warning(
                "⚠️ EXTENDED_API_KEY not configured - falling back to CSV")
            return None

        try:
            params = {
                'produse': '',
                'cautare': query,
                'limit': limit,
                'apikey': self.api_key
            }

            # Add optional filters
            if category:
                params['categorie'] = category
            if price_min is not None:
                params['pret_min'] = price_min
            if price_max is not None:
                params['pret_max'] = price_max

            logger.info(f"🔍 API FUZZY search: '{query}' (limit: {limit})")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }

            response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=10
            )

            if response.status_code != 200:
                logger.error(f"❌ API error: {response.status_code}")
                return None

            data = response.json()

            if isinstance(data, dict) and data.get('eroare') == 1:
                logger.error(f"❌ API error: {data.get('mesaj')}")
                return None

            products = data.get('produse', []) if isinstance(
                data, dict) else []

            logger.info(f"✅ API returned {len(products)} products")

            # Format products
            formatted_products = []
            for p in products:
                try:
                    formatted = [
                        p.get('nume', ''),
                        float(p.get('pret', 0)),
                        p.get('descriere', ''),
                        int(p.get('stoc', 0)),
                        p.get('link', ''),
                        p.get('imagine', '')
                    ]
                    formatted_products.append(formatted)
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ Error formatting product: {e}")
                    continue

            return formatted_products

        except Exception as e:
            logger.error(f"❌ Error in fuzzy search: {e}")
            return None

    def get_order_status(self, order_id):
        """Get order status and details from Extended API"""
        if not self.api_key:
            logger.error("❌ EXTENDED_API_KEY not configured")
            return None

        try:
            params = {
                'comenzi': '',
                'id_comanda': order_id,
                'apikey': self.api_key
            }

            logger.info(f"🔍 Fetching order #{order_id} from Extended API")

            # Add proper headers to mimic browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }

            response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=10
            )

            # Log response for debugging
            logger.info(f"📡 API Response status: {response.status_code}")
            logger.info(
                f"📡 API Response text (first 200 chars): {response.text[:200]}")

            if response.status_code != 200:
                logger.error(f"❌ API error: {response.status_code}")
                return None

            data = response.json()

            # Check for API errors
            if isinstance(data, dict) and data.get('eroare') == 1:
                logger.error(f"❌ Extended API error: {data.get('mesaj')}")
                return None

            # Extract order data (API returns dict with order_id as key)
            # Try both string and integer keys
            order = None
            if isinstance(data, dict):
                if str(order_id) in data:
                    order = data[str(order_id)]
                elif int(order_id) in data:
                    order = data[int(order_id)]

            if order:
                logger.info(f"✅ Order #{order_id} found")
                return self._format_order_data(order)

            logger.warning(f"⚠️ Order #{order_id} not found in response")
            logger.info(
                f"📋 Response keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
            return None

        except requests.exceptions.Timeout:
            logger.error("❌ API request timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API request error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return None

    def get_user_info(self, session_token=None, user_cookie=None):
        """Get logged-in user information from Extended API

        Args:
            session_token: Session token from cookie
            user_cookie: Full cookie string

        Returns:
            Dict with user info: {user_id, name, email} or None
        """
        if not self.api_key:
            logger.warning("⚠️ EXTENDED_API_KEY not configured")
            return None

        try:
            params = {
                'user_info': '',  # Endpoint pentru user info
                'apikey': self.api_key
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }

            # Add session cookie if provided
            if session_token:
                headers['Cookie'] = f'PHPSESSID={session_token}'
            elif user_cookie:
                headers['Cookie'] = user_cookie

            logger.info(f"🔍 Fetching user info from Extended API")

            response = requests.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=10
            )

            logger.info(f"📡 API Response status: {response.status_code}")

            if response.status_code != 200:
                logger.warning(f"⚠️ API error: {response.status_code}")
                return None

            data = response.json()

            # Check for API errors
            if isinstance(data, dict) and data.get('eroare') == 1:
                logger.warning(f"⚠️ User not logged in or invalid session")
                return None

            # Extract user data
            if isinstance(data, dict) and 'user' in data:
                user = data['user']
                user_info = {
                    'user_id': user.get('id'),
                    'name': user.get('nume') or user.get('name'),
                    'email': user.get('email'),
                    'phone': user.get('telefon')
                }

                logger.info(
                    f"✅ User info retrieved: {user_info.get('name')} ({user_info.get('email')})")
                return user_info

            logger.warning("⚠️ User not logged in")
            return None

        except requests.exceptions.Timeout:
            logger.error("❌ API request timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API request error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return None

    def _format_order_data(self, order):
        """Format order data for chatbot response"""
        try:
            formatted = {
                'id': order.get('id_comanda'),
                'data': order.get('data'),
                'status': order.get('status'),
                'total': order.get('total_comanda', 0),
                'livrare_cost': order.get('pret_livrare', 0),
                'metoda_livrare': order.get('metoda_livrare'),
                'metoda_plata': order.get('metoda_plata'),
                'awb': None,
                'awb_link': None,
                'awb_status': None,
                'stadii': []
            }

            # Extract AWB info if available
            awb_data = order.get('awb', {})
            if awb_data and isinstance(awb_data, dict):
                # Get first AWB (in case there are multiple)
                first_awb = next(iter(awb_data.values()), None)
                if first_awb:
                    formatted['awb'] = first_awb.get('awb')
                    formatted['awb_link'] = first_awb.get('link')
                    formatted['awb_status'] = first_awb.get('last')
                    formatted['stadii'] = first_awb.get('stadii', [])

            # Extract products
            products = order.get('produse', {})
            formatted['produse_count'] = len(products) if products else 0

            return formatted

        except Exception as e:
            logger.error(f"❌ Error formatting order data: {e}")
            return None


# Initialize API instance
extended_api = ExtendedAPI()
