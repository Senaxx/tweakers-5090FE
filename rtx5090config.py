
# Proxy Configuration
PROXY_IPS = [
  'xxxx', 'xxxx', 'xxxx', 'xxxx',
  'xxx'
]

PROXY_USERNAME = "xxxx"
PROXY_PASSWORD = "xxxx"

# Product Configuration
PRODUCT_NAME = "NVIDIA RTX 5090"
BASE_URL = "https://api.store.nvidia.com/partner/v1/feinventory?status=1&skus={sku}&locale={locale}"
SEARCH_API_URL = "https://api.nvidia.partners/edge/product/search?page=1&limit=12&locale=fi-fi&category=GPU"

#Telegram Message
BASE_MESSAGE = "RTX 5090FE te koop in {country}!\n\n**Marketplace:** https://marketplace.nvidia.com/{locale}/consumer/graphics-cards/"

# Locale Configuration
LOCALES_COUNTRIES = {
    "nl-nl": ("🇳🇱", "Nederland")
}

# Headers Configuration
API_HEADERS = {
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
