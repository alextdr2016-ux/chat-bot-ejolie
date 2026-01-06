import requests
import pandas as pd
from datetime import datetime
import os
import json

# Extended API Credentials
API_KEY = "p30xyRzDlQstGZaYNi1A6THC8BhPIM"
API_BASE_URL = "https://extended.cloud/api"  # Adjust if needed


class ProductSyncer:

    def __init__(self):
        self.api_key = API_KEY
        self.api_url = API_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def fetch_products(self, limit=500, offset=0):
        """Descarcă produsele din Extended API"""
        try:
            # Endpoint pentru produse
            url = f"{self.api_url}/produse?limit={limit}&offset={offset}"

            print(f"📥 Descarcă din: {url}")
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            print(f"✅ Răspuns primit: {json.dumps(data, indent=2)[:500]}...")

            return data
        except Exception as e:
            print(f"❌ Eroare fetch: {e}")
            return None

    def transform_products(self, raw_data):
        """Transformă datele brute în format CSV"""
        products = []

        # Adaptez la structura API-ului
        items = raw_data.get('data', raw_data.get('items', []))

        for product in items:
            try:
                products.append({
                    'Nume':
                    product.get('name') or product.get('titlu') or 'N/A',
                    'Pret vanzare (cu promotie)':
                    product.get('price') or product.get('pret') or 0,
                    'Stoc':
                    'În Stoc' if product.get('stock', 0) > 0 else 'Lipsa Stoc',
                    'Stoc numeric':
                    product.get('stock', 0),
                    'Descriere':
                    product.get('description') or product.get('descriere')
                    or 'N/A',
                    'Link produs':
                    product.get('url') or product.get('link') or '#'
                })
            except Exception as e:
                print(f"⚠️ Eroare parse produs: {e}")
                continue

        return products

    def sync_to_csv(self):
        """Sincronizează produsele în CSV"""
        print(f"\n{'='*50}")
        print(
            f"📥 SYNC PRODUSE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")

        # Descarcă din API
        raw_data = self.fetch_products(limit=500)

        if not raw_data:
            print("❌ Nu am putut descarca datele")
            return False

        # Transformă
        products = self.transform_products(raw_data)

        if not products:
            print("❌ Nu am găsit produse în răspuns")
            return False

        # Salvează în CSV
        df = pd.DataFrame(products)
        df.to_csv('products.csv', index=False, encoding='utf-8')

        print(f"✅ SYNC COMPLET!")
        print(f"   - {len(products)} produse descarcate")
        print(f"   - Salvate în: products.csv")
        print(f"{'='*50}\n")

        return True


# Run sync
if __name__ == "__main__":
    syncer = ProductSyncer()
    syncer.sync_to_csv()
