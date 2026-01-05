from decimal import Decimal
import os
from dotenv import load_dotenv
load_dotenv()
# ---- Etherscan ----
ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY")         
ETHERSCAN_CHAIN_ID = 1          # Ethereum mainnet
ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"

ETHERSCAN_REQUESTS_PER_SEC = 4.0
ETHERSCAN_TIMEOUT_SEC = 15
ETHERSCAN_MAX_RETRIES = 5
ETHERSCAN_PAGE_SIZE = 1000

# ----- Pricing ------

# ETH fallback / demo price
ETH_USD_FALLBACK = Decimal("3000")

# Stablecoin addresses (optional). Lowercase.
STABLECOIN_ADDRESSES = {
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
    "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT 
    "0x6b175474e89094c44da98b954eedeac495271d0f",  # DAI  
}

# Fixed token prices for demo
FIXED_TOKEN_USD = {
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599":Decimal("93000"),
}