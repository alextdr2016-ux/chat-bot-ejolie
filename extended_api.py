import requests
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ExtendedAPI:
    def __init__(self):
        self.api_key = os.getenv('EXTENDED_API_KEY')
        self.base_url = "https://ejolie.ro/api/"

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

            response = requests.get(
                self.base_url,
                params=params,
                timeout=10
            )

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
