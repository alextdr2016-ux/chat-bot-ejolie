import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time


class EjolieScraper:

    def __init__(self):
        self.base_url = "https://www.ejolie.ro"
        self.headers = {
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def scrape_products(self):
        """Scrapa produsele de pe ejolie.ro"""
        print(f"\n{'='*60}")
        print(
            f"🌐 SCRAPE EJOLIE.RO - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print(f"{'='*60}\n")

        try:
            products = []
            page = 1
            max_pages = 5  # Scrapa primele 5 pagini (50+ produse)

            while page <= max_pages:
                try:
                    # URL pentru pagina de produse
                    url = f"{self.base_url}/search?q=&page={page}"
                    print(f"📥 Scrape pagina {page}: {url}")

                    response = requests.get(url,
                                            headers=self.headers,
                                            timeout=10)
                    response.raise_for_status()

                    soup = BeautifulSoup(response.content, 'lxml')

                    # Găsește produsele (adaptează selectori)
                    product_elements = soup.find_all('div',
                                                     class_='product-item')

                    if not product_elements:
                        # Alternativ selector
                        product_elements = soup.find_all('article',
                                                         class_='product')

                    if not product_elements:
                        print(f"⚠️ Nu am găsit produse pe pagina {page}")
                        break

                    for elem in product_elements:
                        try:
                            # Extrage datele (adaptează selectori)
                            name_elem = elem.find(
                                'h2', class_='product-name') or elem.find(
                                    'a', class_='product-title')
                            name = name_elem.text.strip(
                            ) if name_elem else 'N/A'

                            price_elem = elem.find(
                                'span', class_='price') or elem.find(
                                    'span', class_='product-price')
                            price_text = price_elem.text.strip(
                            ) if price_elem else '0'
                            price = self.extract_price(price_text)

                            desc_elem = elem.find('p', class_='description')
                            description = desc_elem.text.strip(
                            ) if desc_elem else 'N/A'

                            link_elem = elem.find(
                                'a', class_='product-link') or elem.find('a')
                            link = link_elem[
                                'href'] if link_elem and link_elem.get(
                                    'href') else '#'
                            if not link.startswith('http'):
                                link = self.base_url + link

                            stock_elem = elem.find('span', class_='stock')
                            stock = stock_elem.text.strip(
                            ) if stock_elem else 'În Stoc'

                            product = {
                                'Nume': name,
                                'Pret vanzare (cu promotie)': price,
                                'Descriere': description,
                                'Stoc': stock,
                                'Link produs': link
                            }

                            products.append(product)
                        except Exception as e:
                            print(f"   ⚠️ Eroare parse produs: {e}")
                            continue

                    print(
                        f"   ✅ {len(product_elements)} produse extrase de pe pagina {page}"
                    )
                    page += 1
                    time.sleep(1)  # Pauză între pagini

                except Exception as e:
                    print(f"   ❌ Eroare pagina {page}: {e}")
                    break

            if products:
                self.save_to_csv(products)
                return True
            else:
                print("❌ Nu am găsit niciun produs!")
                return False

        except Exception as e:
            print(f"❌ Eroare scraping: {e}")
            return False

    def extract_price(self, price_text):
        """Extrage prețul din text"""
        import re
        numbers = re.findall(r'\d+[\.,]\d+|\d+', price_text)
        if numbers:
            return float(numbers[0].replace(',', '.'))
        return 0

    def save_to_csv(self, products):
        """Salvează produsele în CSV"""
        df = pd.DataFrame(products)
        df.to_csv('products.csv', index=False, encoding='utf-8')
        print(f"\n✅ SCRAPE COMPLET!")
        print(f"   - {len(products)} produse descarcate")
        print(f"   - Salvate în: products.csv")
        print(f"{'='*60}\n")


# Test scraper
if __name__ == "__main__":
    scraper = EjolieScraper()
    scraper.scrape_products()
