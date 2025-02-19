import aiohttp
import asyncio
import logging
import os
from typing import Dict, Tuple
from rtx5090config import PROXY_USERNAME, PROXY_PASSWORD, PRODUCT_NAME, BASE_URL, BASE_MESSAGE, LOCALES_COUNTRIES, PROXY_IPS, SEARCH_API_URL, API_HEADERS

class NvidiaChecker:
    # Initialiseer de NvidiaChecker met proxy instellingen en logging configuratie
    def __init__(self):
        self.current_proxy_index = 0
        self.setup_logging()
        self.product_configs = {}
        self.last_known_sku = None
        self.pushbullet_token = os.environ.get('PUSHBULLET_TOKEN')
    
        self.proxies = [{
            'http': f'http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{ip}:50100'
        } for ip in PROXY_IPS]

    # Configureer de logging instellingen voor de applicatie
    @staticmethod
    def setup_logging() -> None:
        # Configure the format for logs
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        formatter = logging.Formatter(log_format)
        
        # Setup file handler for error logs
        error_file_handler = logging.FileHandler('error.log')
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(formatter)
        
        # Setup console handler for all logs
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Configure the root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(error_file_handler)
        root_logger.addHandler(console_handler)

    # Definieer de HTTP headers die worden gebruikt voor API requests
    @staticmethod
    def get_headers() -> Dict[str, str]:
        return API_HEADERS

    # Haal de volgende proxy op uit de rotatielijst
    def get_next_proxy(self) -> Dict[str, str]:
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return proxy

    # Verstuur een bericht naar Telegram via de Telegram Bot API
    async def send_to_pushbullet(self, message: str) -> None:
        if self.pushbullet_token:
            try:
                from pushbullet import Pushbullet
                pb = Pushbullet(self.pushbullet_token)
                devices = pb.devices
                if devices:
                    device = devices[0]
                    pb.push_link("NVIDIA Marketplace", message.split("\n")[-1], device=device)
                    logging.info("Pushbullet message sent successfully to device")
                else:
                    pb.push_link("NVIDIA Marketplace", message.split("\n")[-1])
                    logging.info("Pushbullet message sent to all devices")
            except Exception as e:
                logging.error(f"Failed to send Pushbullet message: {e}")

    async def send_to_telegram(self, message: str) -> None:
        try:
            api_token = os.environ['tg_bot_token']
            chat_ids = [os.environ['tg_chatID']]  # Add both chat IDs
            api_url = f'https://api.telegram.org/bot{api_token}/sendMessage'

            async with aiohttp.ClientSession() as session:
                for chat_id in chat_ids:
                    async with session.post(api_url, json={'chat_id': chat_id, 'text': message}) as response:
                        await response.json()
                        logging.info(f"Telegram bericht succesvol verstuurd naar {chat_id}")
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {e}")

    # Haal het SKU nummer op van de NVIDIA API
    async def get_sku(self) -> str | None:
        url = SEARCH_API_URL
        try:
            proxy = self.get_next_proxy()
            proxy_display = f"http://***:***@{proxy['http'].split('@')[1]}"
            logging.info(f"Huidige proxy voor SKU ophalen: {proxy_display}")

            async with aiohttp.ClientSession() as session:
                session.headers.update(self.get_headers())
                async with session.get(url, proxy=proxy['http'], timeout=aiohttp.ClientTimeout(total=5)) as response:
                    data = await response.json()

                    for product in data["searchedProducts"]["productDetails"]:
                        if product["displayName"] == PRODUCT_NAME:
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
                        message = f"{config['message']}"
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
            if sku is None:
                logging.error("Fout bij ophalen SKU, meteen opnieuw proberen...")
                await asyncio.sleep(1)
                continue

            #Controleer of het SKU nummer verschillt van het vorige SKU nummer
            if self.last_known_sku is None:
                logging.info(f"Huidige SKU is: {sku}")
                self.last_known_sku = sku
            elif sku != self.last_known_sku:
                logging.warning("SKU verandering gedetecteerd!")
                message = f"⚠️ SKU Veranderd!\nOude SKU: {self.last_known_sku}\nNieuwe SKU: {sku}"
                try:
                    await asyncio.gather(
                        self.send_to_telegram(message),
                        self.send_to_pushbullet(message)
                    )
                    logging.info(f"SKU veranderd van {self.last_known_sku} naar {sku}\n\nMarketplace: https://marketplace.nvidia.com/nl-nl/consumer/graphics-cards/")
                    self.last_known_sku = sku
                except Exception as e:
                    logging.error(f"Error sending SKU change notifications: {e}")
            else:
                logging.info(f"SKU onveranderd: {sku}")

          
            base_url = BASE_URL
            base_message = BASE_MESSAGE
            locales_countries = LOCALES_COUNTRIES

            self.product_configs = {
                locale.split('-')[1].upper(): {
                    "url": base_url.format(sku=sku, locale=locale),
                    "message": f"{flag} {base_message.format(locale=locale, country=country)}"
                } for locale, (flag, country) in locales_countries.items()
            } 

            logging.info("Check voor product in de API...")
            found, retry = await self.check_availability()

            if found:
                logging.info("Product gevonden! Checking again in 5 seconds...")
                await asyncio.sleep(5)
            elif retry:
                logging.info("503 error - Meteen opnieuw proberen...")
                await asyncio.sleep(1)
                continue
            else:
                logging.info("Geen product gevonden. Probeer opnieuw in 2 seconden...")
                await asyncio.sleep(2)

    async def test_pushbullet(self):
            """Test if Pushbullet token works by sending a test message"""
            try:
                from pushbullet import Pushbullet
                if self.pushbullet_token:
                    pb = Pushbullet(self.pushbullet_token)
                    sku = self.last_known_sku if self.last_known_sku else "No SKU found"
                    test_url = "https://marketplace.nvidia.com/nl-nl/consumer/graphics-cards/"
                    devices = pb.devices
                    if devices:
                        device = devices[0]
                        pb.push_link(f"Test Notification (SKU: {sku})", test_url, device=device)
                    else:
                        pb.push_link(f"Test Notification (SKU: {sku})", test_url)
                    logging.info("Pushbullet test message sent successfully")
                    return True
                else:
                    logging.error("No Pushbullet token configured")
                    return False
            except Exception as e:
                logging.error(f"Failed to send Pushbullet test message: {e}")
                return False

    # Start het hoofdprogramma
async def main():
    checker = NvidiaChecker()
    # First get the SKU
    sku = await checker.get_sku()
    if sku:
        checker.last_known_sku = sku
        # Now test Pushbullet with the known SKU
        await checker.test_pushbullet()
    # Start the main loop
    await checker.run()

if __name__ == "__main__":
    asyncio.run(main())
