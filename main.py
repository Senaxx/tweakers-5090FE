import requests
import time
import logging
import os
from typing import Dict, Tuple

class NvidiaChecker:
  
  def get_sku(self) -> str:
    url = "https://api.nvidia.partners/edge/product/search?page=1&limit=12&locale=nl-nl&category=GPU"
    try:
      proxy = self.get_next_proxy()
      proxy_display = f"http://***:***@{proxy['http'].split('@')[1]}"
      logging.info(f"Using proxy for SKU fetch: {proxy_display}")

      session = requests.Session()
      session.trust_env = False
      session.proxies = proxy
      session.headers.update(self.get_headers())

      response = session.get(url, timeout=5)
      response.raise_for_status()
      data = response.json()
      
      for product in data["searchedProducts"]["productDetails"]:
        if product["displayName"] == "NVIDIA RTX 5090":
          sku = product["productSKU"]
          logging.info(f"Successfully fetched SKU from API: {sku}")
          return sku
      logging.info("SKU niet gevodnen gebruik fallback: 5090FEPROSHOP")
      return "5090FEPROSHOP"  # Fallback SKU
    except Exception as e:
      logging.error(f"Error fetching SKU: {e}")
      return "5090FEPROSHOP"  # Fallback SKU

  def __init__(self):
    self.current_proxy_index = 0
    self.setup_logging()
    self.product_configs = {}

    # Defineer proxies als class attribute
    self.proxies = [{
        'http': f'http://xxxxx:xxxxx{ip}:50100'
    } for ip in [
        'xxxx', 'xxxxx', 'xxxxxx', 'xxxxx',
        'xxxxxx', 'xxxxx', 'xxxxxx', 'xxxxxx',
        'xxxxxx', 'xxxxxxx'
    ]]

  
  @staticmethod
  def setup_logging() -> None:
    #Configureer logging met consistent formaat
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

  @staticmethod
  def get_headers() -> Dict[str, str]:
    #Defineer headers voor API-verzoek
    return {
        "authority": "api.nvidia.partners",
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-GB,en;q=0.9,en-US;q=0.8,nl;q=0.7",
        "content-type": "application/json",
        "dnt": "1",
        "origin": "https://marketplace.nvidia.com",
        "priority": "u=1, i",
        "referer": "https://marketplace.nvidia.com/",
        "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Microsoft Edge";v="132"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site":  "cross-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"
    }

  def get_next_proxy(self) -> Dict[str, str]:
    #Haal volgende proxy op uit de rotatie
    proxy = self.proxies[self.current_proxy_index]
    self.current_proxy_index = (self.current_proxy_index + 1) % len(
        self.proxies)
    return proxy

  def send_to_telegram(self, message: str) -> None:
  #Stuur notificatie naar Telegram
    try:
      api_token = os.environ['tg_bot_token']
      chat_id = os.environ['tg_chatID']
      api_url = f'https://api.telegram.org/bot{api_token}/sendMessage'
  
      response = requests.post(api_url,json={'chat_id': chat_id,'text': message})
      response.raise_for_status()
      logging.info("Telegram bericht succcesvol verstuurd.")
    
    except Exception as e:
     logging.error(f"Failed to send Telegram message: {e}")

  def handle_request(self, session: requests.Session, product_name: str, config: Dict) -> bool:
    try:
      response = session.get(config['url'], timeout=5)
      response.raise_for_status()
      data = response.json()
      
      # Log the complete JSON response for debugging
      logging.info(f"Response for {product_name}: {data}")
      
      if data.get("success") and data.get("listMap"):
        product = data["listMap"][0]
        if product.get("is_active") == "true" and product.get("product_url"):
          product_url = product['product_url']
          logging.info(f"{product_name} beschikbaar op: {product_url}")
          message = f"{config['message']}\n{product_url}"
          self.send_to_telegram(message)
          return True
      return False
      
    except (requests.exceptions.RequestException, ValueError) as e:
      logging.error(f"Error checking {product_name}: {e}")
      return False

  def check_availability(self) -> Tuple[bool, bool]:
    try:
      proxy = self.get_next_proxy()
      proxy_display = f"http://***:***@{proxy['http'].split('@')[1]}"
      logging.info(f"Using proxy for availability check: {proxy_display}")

      session = requests.Session()
      session.trust_env = False
      session.proxies = proxy
      session.headers.update(self.get_headers())
      
      found_products = [
        product_name for product_name, config in self.product_configs.items()
        if self.handle_request(session, product_name, config)
      ]
      
      return len(found_products) > 0, False

    except requests.exceptions.HTTPError as e:
      if getattr(e.response, 'status_code', None) == 503:
        logging.error("503 Server Error - Meteen opnieuw proberen")
        return False, True
      raise
    except requests.exceptions.Timeout:
      logging.error("Request timed out - Meteen opnieuw proberen")
      return False, True
    except Exception as e:
      logging.error(f"Error checking availability: {e}")
      return False, False

  def run(self) -> None:
    #Hoofdloop om productbeschikbaarheid te controleren.
    while True:
      # Get the SKU first
      sku = self.get_sku()
      
      # Initialize product configs with current SKU
      self.product_configs = {
        "5090FE_NL": {
          "url": f"https://api.store.nvidia.com/partner/v1/feinventory?status=1&skus={sku}&locale=nl-nl",
          "message": "🇳🇱 RTX 5090FE FE nu te koop op in NEDERLAND!\n\nKoop op:"
        },
        "5090FE_DE": {
          "url": f"https://api.store.nvidia.com/partner/v1/feinventory?status=1&skus={sku}&locale=de-de",
          "message": "🇩🇪 RTX 5090FE FE verfügbar in DEUTSCHLAND!\n\nKaufen Sie jetzt bei:"
        },
        "5090FE_DK": {
          "url": f"https://api.store.nvidia.com/partner/v1/feinventory?status=1&skus={sku}&locale=da-dk",
          "message": "🇩🇰 RTX 5090FE FE te koop in DENEMARKEN!\n\nKoop op:"
        }
      }
      
      logging.info("Check voor product in de API...")
      found, retry = self.check_availability()

      if found:
        logging.info("Product gevonden! Checking again in 10 seconds...")
        time.sleep(10)
      elif retry:
        logging.info("503 error - Meteen opnieuw proberen...")
        continue
      else:
        logging.info("Geen product gevonden. Probeer opnieuw in 3 seconden...")
        time.sleep(3)

def main():
  checker = NvidiaChecker()
  checker.run()


if __name__ == "__main__":
  main()
