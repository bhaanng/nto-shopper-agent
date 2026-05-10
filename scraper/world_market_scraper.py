"""
World Market Product Scraper

Scrapes product information from worldmarket.com and saves to JSON.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin
import random


class WorldMarketScraper:
    def __init__(self):
        self.base_url = "https://www.worldmarket.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

        # Categories to scrape
        self.categories = {
            'furniture': '/category/furniture.do',
            'decor': '/category/home-decor.do',
            'kitchen': '/category/kitchen-and-dining.do',
            'food': '/category/food-and-drink.do',
            'outdoor': '/category/outdoor-and-garden.do',
            'bedding': '/category/bedding-and-bath.do',
            'storage': '/category/storage-and-organization.do',
        }

    def scrape_category(self, category_name: str, category_url: str, max_products: int = 50) -> List[Dict]:
        """Scrape products from a specific category"""
        print(f"\n🔍 Scraping {category_name}...")
        products = []

        try:
            url = urljoin(self.base_url, category_url)
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find product tiles/cards (adjust selectors based on actual HTML)
            # These selectors are educated guesses - may need adjustment after testing
            product_tiles = soup.find_all('div', class_=['product-tile', 'product-card', 'productTile'], limit=max_products)

            if not product_tiles:
                # Fallback: try different common selectors
                product_tiles = soup.find_all('article', class_='product')

            if not product_tiles:
                print(f"  ⚠️  No products found with current selectors. Page structure may differ.")
                return []

            for tile in product_tiles[:max_products]:
                try:
                    product = self._extract_product_info(tile, category_name)
                    if product:
                        products.append(product)
                        print(f"  ✓ {product['name'][:50]}...")
                except Exception as e:
                    print(f"  ⚠️  Error extracting product: {e}")
                    continue

                # Be polite - small delay between items
                time.sleep(random.uniform(0.1, 0.3))

            print(f"✅ Found {len(products)} products in {category_name}")

        except Exception as e:
            print(f"❌ Error scraping {category_name}: {e}")

        return products

    def _extract_product_info(self, tile, category: str) -> Optional[Dict]:
        """Extract product information from a product tile"""
        try:
            # Product name
            name_elem = (
                tile.find('a', class_=['product-name', 'link', 'product-title']) or
                tile.find('h3') or
                tile.find('h2')
            )
            name = name_elem.get_text(strip=True) if name_elem else "Unknown Product"

            # Product URL
            link_elem = tile.find('a', href=True)
            product_url = urljoin(self.base_url, link_elem['href']) if link_elem else ""

            # Price - try multiple selectors
            price_elem = (
                tile.find('span', class_=['price', 'product-price', 'price-sales']) or
                tile.find('div', class_='price')
            )
            price_text = price_elem.get_text(strip=True) if price_elem else "Price not available"

            # Clean price
            price = self._clean_price(price_text)

            # Image
            img_elem = tile.find('img')
            image_url = ""
            if img_elem:
                image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
                if image_url and not image_url.startswith('http'):
                    image_url = urljoin(self.base_url, image_url)

            # Description (if available on listing page)
            desc_elem = tile.find('p', class_=['product-description', 'description'])
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Product ID (try to extract from URL or data attributes)
            product_id = ""
            if link_elem and 'href' in link_elem.attrs:
                # Try to extract ID from URL pattern
                href = link_elem['href']
                if '/product/' in href:
                    product_id = href.split('/product/')[-1].split('.')[0].split('?')[0]

            if not product_id:
                # Fallback: use name-based ID
                product_id = name.lower().replace(' ', '-')[:50]

            return {
                'id': product_id,
                'name': name,
                'price': price,
                'price_display': price_text,
                'category': category,
                'url': product_url,
                'image_url': image_url,
                'description': description,
                'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

        except Exception as e:
            print(f"    ⚠️  Error extracting product details: {e}")
            return None

    def _clean_price(self, price_text: str) -> float:
        """Extract numeric price from text"""
        try:
            # Remove currency symbols, commas, and extract first number
            import re
            numbers = re.findall(r'[\d,]+\.?\d*', price_text.replace(',', ''))
            if numbers:
                return float(numbers[0])
        except:
            pass
        return 0.0

    def scrape_all_categories(self, max_products_per_category: int = 50) -> List[Dict]:
        """Scrape all categories"""
        all_products = []

        print("🚀 Starting World Market scraper...")
        print(f"📦 Scraping {len(self.categories)} categories")

        for category_name, category_url in self.categories.items():
            products = self.scrape_category(category_name, category_url, max_products_per_category)
            all_products.extend(products)

            # Be polite - delay between categories
            time.sleep(random.uniform(1, 2))

        print(f"\n✅ Total products scraped: {len(all_products)}")
        return all_products

    def save_to_json(self, products: List[Dict], filename: str = '../data/products.json'):
        """Save products to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(products, f, indent=2, ensure_ascii=False)
            print(f"💾 Saved {len(products)} products to {filename}")
        except Exception as e:
            print(f"❌ Error saving to JSON: {e}")


def main():
    """Main scraper execution"""
    scraper = WorldMarketScraper()

    # Scrape products (start small for testing - 20 per category)
    products = scraper.scrape_all_categories(max_products_per_category=20)

    # Save to JSON
    scraper.save_to_json(products, '../data/products.json')

    print("\n" + "="*60)
    print("📊 Scraping Summary")
    print("="*60)

    # Show category breakdown
    from collections import Counter
    categories = Counter(p['category'] for p in products)
    for cat, count in categories.items():
        print(f"  {cat}: {count} products")

    print("\n✅ Scraping complete!")
    print("💡 You can now run the agent with this product catalog.")


if __name__ == "__main__":
    main()
