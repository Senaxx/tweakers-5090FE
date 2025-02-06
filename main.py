
import aiohttp
import asyncio
import logging
import os
from typing import Dict, Tuple

class NvidiaChecker:
    # Initialiseer de NvidiaChecker met proxy instellingen en logging configuratie
    def __init__(self):
        self.current_proxy_index = 0
        self.setup_logging()
        self.product_configs = {}
        self.last_known_sku = None
        
        self.proxies = [{
            'http': f'http://xxxxxx:xxxxxx{ip}:50100'
        } for ip in [
            'xxxxxx', 'xxxxxx', 'xxxxxx', 'xxxxxx',
            'xxxxxx', 'xxxxxx', 'xxxxxx', 'xxxxxx',
            'xxxxxx', 'xxxxxx'
        ]]

    # Configureer de logging instellingen voor de applicatie
    @staticmethod
    def setup_logging() -> None:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Definieer de HTTP headers die worden gebruikt voor API requests
    @staticmethod
    def get_headers() -> Dict[str, str]:
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
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"
        }

    # Haal de volgende proxy op uit de rotatielijst
    def get_next_proxy(self) -> Dict[str, str]:
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return proxy

    # Verstuur een bericht naar Telegram via de Telegram Bot API
    async def send_to_telegram(self, message: str) -> None:
        try:
            api_token = os.environ['tg_bot_token']
            chat_id = os.environ['tg_chatID']
            api_url = f'https://api.telegram.org/bot{api_token}/sendMessage'
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json={'chat_id': chat_id, 'text': message}) as response:
                    await response.json()
                    logging.info("Telegram bericht succesvol verstuurd.")
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {e}")

    # Haal het SKU nummer op van de NVIDIA API
    async def get_sku(self) -> str | None:
        url = "https://api.nvidia.partners/edge/product/search?page=1&limit=12&locale=nl-nl&category=GPU"
        try:
            proxy = self.get_next_proxy()
            proxy_display = f"http://***:***@{proxy['http'].split('@')[1]}"
            logging.info(f"Huidige proxy voor SKU ophalen: {proxy_display}")

            async with aiohttp.ClientSession() as session:
                session.headers.update(self.get_headers())
                async with session.get(url, proxy=proxy['http'], timeout=aiohttp.ClientTimeout(total=5)) as response:
                    data = await response.json()
                    
                    for product in data["searchedProducts"]["productDetails"]:
                        if product["displayName"] == "NVIDIA RTX 5090":
                            sku = product["productSKU"]
                            logging.info(f"Successvol SKU uit de API gehaald: {sku}")
                            return sku
                    logging.error("SKU niet gevonden in API response")
                    return None
        except Exception as e:
            logging.error(f"Error fetching SKU: {e}")
            return None

    # Verwerk een enkele API request voor een specifiek product
    async def handle_request(self, session: aiohttp.ClientSession, product_name: str, config: Dict) -> bool:
        try:
            async with session.get(config['url'], timeout=aiohttp.ClientTimeout(total=5)) as response:
                data = await response.json()
                logging.info(f"Response for {product_name}: {data}")
                
                if data.get("success") and data.get("listMap"):
                    product = data["listMap"][0]
                    if product.get("is_active") == "true" and product.get("product_url"):
                        product_url = product['product_url']
                        logging.info(f"{product_name} beschikbaar op: {product_url}")
                        message = f"{config['message']}\n{product_url}"
                        await self.send_to_telegram(message)
                        return True
                return False
        except Exception as e:
            logging.error(f"Error checking {product_name}: {e}")
            return False

    # Controleer de beschikbaarheid van alle geconfigureerde producten
    async def check_availability(self) -> Tuple[bool, bool]:
        try:
            proxy = self.get_next_proxy()
            proxy_display = f"http://***:***@{proxy['http'].split('@')[1]}"
            logging.info(f"Gebruik deze proxy voor AP: {proxy_display}")

            async with aiohttp.ClientSession(headers=self.get_headers()) as session:
                tasks = [
                    self.handle_request(session, product_name, config)
                    for product_name, config in self.product_configs.items()
                ]
                results = await asyncio.gather(*tasks)
                return any(results), False

        except aiohttp.ClientError as e:
            if getattr(e, 'status', None) == 503:
                logging.error("503 Server Error - Meteen opnieuw proberen")
                return False, True
            raise
        except asyncio.TimeoutError:
            logging.error("Request timed out - Meteen opnieuw proberen")
            return False, True
        except Exception as e:
            logging.error(f"Error checking availability: {e}")
            return False, False

    # Hoofdloop die continue de producten controleert en updates verwerkt
    async def run(self) -> None:
        while True:
            sku = await self.get_sku()

            #Controleer of het SKU nummer verschillt van het vorige SKU nummer
            if self.last_known_sku is None:
                logging.info(f"Huidige SKU is: {sku}")
            elif sku != self.last_known_sku:
                message = f"⚠️ SKU Veranderd!\nOude SKU: {self.last_known_sku}\nNieuwe SKU: {sku}"
                await self.send_to_telegram(message)
                logging.info(f"SKU veranderd van {self.last_known_sku} naar {sku}")
            else:
                logging.info(f"SKU onveranderd: {sku}")

            self.last_known_sku = sku

            #Defineer de producten die moeten worden controleerd
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
                },
                "5090FE_AT": {
                    "url": f"https://api.store.nvidia.com/partner/v1/feinventory?status=1&skus={sku}&locale=da-at",
                    "message": "🇦🇹 RTX 5090FE FE te koop in OOSTENRIJK!\n\nKoop op:"
                },
                "5090FE_FI": {
                    "url": f"https://api.store.nvidia.com/partner/v1/feinventory?status=1&skus={sku}&locale=fi-fi",
                    "message": "🇫🇮 RTX 5090FE FE te koop in FINLAND! \nKoop op:",
                }
            }

            logging.info("Check voor product in de API...")
            found, retry = await self.check_availability()

            if found:
                logging.info("Product gevonden! Checking again in 10 seconds...")
                await asyncio.sleep(10)
            elif retry:
                logging.info("503 error - Meteen opnieuw proberen...")
                continue
            else:
                logging.info("Geen product gevonden. Probeer opnieuw in 3 seconden...")
                await asyncio.sleep(3)

# Start het hoofdprogramma
async def main():
    checker = NvidiaChecker()
    await checker.run()

if __name__ == "__main__":
    asyncio.run(main())
