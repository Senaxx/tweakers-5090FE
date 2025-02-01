import requests
import time
import logging
import os
from typing import Dict, Tuple

class NvidiaChecker:

  def __init__(self):
    self.url = "https://api.store.nvidia.com/partner/v1/feinventory?status=1&skus=PROGFTNV590&locale=nl-nl"
    self.current_proxy_index = 0
    self.setup_logging()

    # Defineer proxies als class attribute
    self.proxies = [{
        'http': f'http://xxxxx:xxxxxx@{ip}:50100'
    } for ip in [
        '255.255.255.0', '255.255.255.0', '255.255.255.0', '255.255.255.0',
        '255.255.255.0', '255.255.255.0', '255.255.255.0', '255.255.255.0',
        '255.255.255.0', '255.255.255.0'
    ]]

  @staticmethod
  def setup_logging() -> None:
    #Configureer logging met consistent formaat
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

  @staticmethod
  def get_headers() -> Dict[str, str]:
    #Defineer headers voor API-verzoek
    return {
        "authority": "api.nvidia.partners",
        "accept":"application/json, text/javascript, */*; q=0.01",
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
        "sec-fetch-site": "cross-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"
    }

  def get_next_proxy(self) -> Dict[str, str]:
    #Haal volgende proxy op uit de rotatie op volgorde
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

      response = requests.post(api_url,
                               json={
                                   'chat_id': chat_id,
                                   'text': message
                               })
      response.raise_for_status()
      logging.info("Telegram bericht succcesvol verstuurd.")
    except Exception as e:
      logging.error(f"Failed to send Telegram message: {e}")

  def check_availability(self) -> Tuple[bool, bool]:
    #Controleer productbeschikbaarheid.
    try:
      proxy = self.get_next_proxy()
      proxy_display = f"http://***:***@{proxy['http'].split('@')[1]}"
      logging.info(f"Using proxy: {proxy_display}")

      response = requests.get(self.url,
                              headers=self.get_headers(),
                              proxies=proxy,
                              timeout=10)
      response.raise_for_status()
      data = response.json()
      logging.info(f"Response JSON: {data}")

      if data.get("success") and data.get("listMap"):
        product = data["listMap"][0]
        if product.get("is_active") == "true" and product.get("product_url"):
          product_url = product['product_url']
          logging.info(f"Product beschikbaar op: {product_url}")
          self.send_to_telegram(f"\n\n**5090FE url:**\n\n {product_url}")
          return True, False
      return False, False

    except requests.exceptions.HTTPError as e:
      if e.response.status_code == 503:
        logging.error("503 Server Error - Meteen opnieuw proberen")
        return False, True
      logging.error(f"HTTP Error: {e}")
      return False, False

    except requests.exceptions.Timeout:
      logging.error("Request timed out - Meteen opnieuw proberen")
      return False, True

    except Exception as e:
      logging.error(f"Error checking availability: {e}")
      return False, False

  def run(self) -> None:
    #Hoofdloop om productbeschikbaarheid te controleren.
    while True:
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
