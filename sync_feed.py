import requests
import pandas as pd
import logging
import os
from datetime import datetime
from io import StringIO

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Feed URL
FEED_URL = "https://ejolie.ro/continut/feed/fb_product.tsv"


def sync_products_from_feed():
    """Descarcă feed-ul și actualizează products.csv"""

    logger.info("=" * 60)
    logger.info(
        f"🔄 SYNC FEED START - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        # 1. Descarcă feed-ul
        logger.info(f"📥 Downloading feed from: {FEED_URL}")
        response = requests.get(FEED_URL, timeout=60)
        response.raise_for_status()

        logger.info(f"✅ Feed downloaded - {len(response.content)} bytes")

        # 2. Parsează TSV
        logger.info("📊 Parsing TSV...")
        df = pd.read_csv(StringIO(response.text), sep='\t', encoding='utf-8')

        logger.info(f"✅ Parsed {len(df)} products")
        logger.info(f"📋 Columns: {list(df.columns)}")

        # 3. Transformă în formatul nostru
        logger.info("🔄 Transforming to chatbot format...")

        products = []
        for idx, row in df.iterrows():
            try:
                # Extrage datele
                name = str(row.get('title', '')).strip()

                # Parse price (format: "154.00 RON")
                price_str = str(row.get('sale_price', row.get('price', '0')))
                price = float(price_str.replace(
                    'RON', '').replace(',', '.').strip())

                description = str(row.get('description', '')).strip()
                # Curăță HTML entities
                description = description.replace(
                    '&mdash;', '-').replace('&icirc;', 'î').replace('&acirc;', 'â')

                # Stock: 1 dacă "in stock", 0 dacă nu
                availability = str(row.get('availability', '')).lower()
                stock = 1 if 'in stock' in availability else 0

                link = str(row.get('link', '')).strip()

                category = str(row.get('product_type', '')).strip()

                # NOU: Extrage brand-ul (Ejolie sau Trendya)
                brand = str(row.get('brand', '')).strip()

                # Adaugă doar produse valide
                if name and price > 0:
                    products.append({
                        'Nume': name,
                        'Pret vanzare (cu promotie)': price,
                        'Descriere': description[:500],  # Limitează descrierea
                        'Stoc numeric': stock,
                        'Link produs': link,
                        'Categorie': category,
                        'Brand': brand  # NOU: Salvăm brand-ul
                    })

            except Exception as e:
                logger.warning(f"⚠️ Error parsing row {idx}: {e}")
                continue

        logger.info(f"✅ Transformed {len(products)} valid products")

        # Numără produse per brand
        ejolie_count = sum(1 for p in products if p.get(
            'Brand', '').lower() == 'ejolie')
        trendya_count = sum(1 for p in products if p.get(
            'Brand', '').lower() == 'trendya')
        logger.info(
            f"📊 Brands: Ejolie={ejolie_count}, Trendya={trendya_count}")

        # 4. Salvează în CSV
        if products:
            output_df = pd.DataFrame(products)
            output_df.to_csv('products.csv', index=False, encoding='utf-8')

            logger.info(f"✅ Saved to products.csv")
            logger.info("=" * 60)
            logger.info(f"🎉 SYNC COMPLETE - {len(products)} products")
            logger.info("=" * 60)

            return {
                "status": "success",
                "products_count": len(products),
                "ejolie_count": ejolie_count,
                "trendya_count": trendya_count,
                "timestamp": datetime.now().isoformat()
            }
        else:
            logger.error("❌ No valid products found!")
            return {
                "status": "error",
                "message": "No valid products found",
                "products_count": 0
            }

    except requests.RequestException as e:
        logger.error(f"❌ Download error: {e}")
        return {"status": "error", "message": f"Download failed: {e}"}
    except Exception as e:
        logger.error(f"❌ Sync error: {e}")
        return {"status": "error", "message": str(e)}


# Test direct
if __name__ == "__main__":
    result = sync_products_from_feed()
    print(f"\nResult: {result}")
