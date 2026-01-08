from decimal import Decimal
import os
from dotenv import load_dotenv
load_dotenv()
# ---- Etherscan ----
ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY")         
ETHERSCAN_CHAIN_ID = 1          # Ethereum mainnet
ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"

ETHERSCAN_REQUESTS_PER_SEC = 2.0
ETHERSCAN_TIMEOUT_SEC = 15
ETHERSCAN_MAX_RETRIES = 5
ETHERSCAN_PAGE_SIZE = 1000
ETHERSCAN_CHECKPOINT_FILE = ".cache/etherscan_checkpoints.json"

# ---- DexScreener ----
DEXSCREENER_BASE_URL = "https://api.dexscreener.com/latest/dex"
DEXSCREENER_REQUESTS_PER_SEC = 1.0
DEXSCREENER_TIMEOUT_SEC = 15
DEXSCREENER_MAX_RETRIES = 3
DEXSCREENER_MIN_LIQUIDITY_USD = Decimal("250000")
DEXSCREENER_NEW_PAIR_HOURS = 24
DEXSCREENER_CHAIN_ID = "ethereum"

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
    "0xbb519BDa747465D8fD57a540595b391a0540e66c":Decimal("2"),
    "0xed785Af60bEd688baa8990cD5c4166221599A441":Decimal("2")
}

# ----- ML Risk Scoring -----
ML_TOKEN_MODEL_PATH = os.environ.get("ML_TOKEN_MODEL_PATH", "models/token_risk.pkl")
ML_WALLET_MODEL_PATH = os.environ.get("ML_WALLET_MODEL_PATH", "models/wallet_risk.pkl")
ML_TOKEN_HIGH_THRESHOLD = Decimal(os.environ.get("ML_TOKEN_HIGH_THRESHOLD", "0.7"))
ML_TOKEN_MEDIUM_THRESHOLD = Decimal(os.environ.get("ML_TOKEN_MEDIUM_THRESHOLD", "0.5"))
ML_WALLET_HIGH_THRESHOLD = Decimal(os.environ.get("ML_WALLET_HIGH_THRESHOLD", "0.7"))
ML_WALLET_MEDIUM_THRESHOLD = Decimal(os.environ.get("ML_WALLET_MEDIUM_THRESHOLD", "0.5"))
