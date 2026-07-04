"""Nifty 100 stock → sector mapping + sector ETF benchmarks."""

from __future__ import annotations

# Nifty 100 — sector labels for rotation filter
STOCK_SECTOR: dict[str, str] = {
    "RELIANCE": "Energy", "ONGC": "Energy", "BPCL": "Energy", "NTPC": "Power", "POWERGRID": "Power",
    "COALINDIA": "Mining", "TATASTEEL": "Metal", "JSWSTEEL": "Metal", "HINDALCO": "Metal",
    "SAIL": "Metal", "JINDALSTEL": "Metal", "VEDL": "Metal", "NMDC": "Mining",
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking", "KOTAKBANK": "Banking",
    "AXISBANK": "Banking", "INDUSINDBK": "Banking", "BANKBARODA": "Banking", "PNB": "Banking",
    "CANBK": "Banking", "BAJFINANCE": "NBFC", "BAJAJFINSV": "NBFC", "CHOLAFIN": "NBFC",
    "MUTHOOTFIN": "NBFC", "RECLTD": "NBFC", "SBICARD": "NBFC", "HDFCLIFE": "Insurance",
    "SBILIFE": "Insurance", "LICI": "Insurance", "ICICIGI": "Insurance", "ICICIPRULI": "Insurance",
    "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT",
    "PERSISTENT": "IT", "OFSS": "IT", "NAUKRI": "IT",
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma", "DIVISLAB": "Pharma",
    "LUPIN": "Pharma", "AUROPHARMA": "Pharma", "BIOCON": "Pharma", "APOLLOHOSP": "Healthcare",
    "MARUTI": "Auto", "M&M": "Auto", "HEROMOTOCO": "Auto", "EICHERMOT": "Auto",
    "BAJAJ-AUTO": "Auto", "MOTHERSON": "Auto", "TATAMOTORS": "Auto",
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "TATACONSUM": "FMCG", "GODREJCP": "FMCG", "DABUR": "FMCG", "MARICO": "FMCG",
    "COLPAL": "FMCG", "VBL": "FMCG",
    "TITAN": "Consumer", "TRENT": "Consumer", "PIDILITIND": "Chemical", "SRF": "Chemical",
    "UPL": "Chemical", "PIIND": "Chemical", "BERGEPAINT": "Consumer", "ASIANPAINT": "Consumer",
    "ULTRACEMCO": "Infra", "GRASIM": "Infra", "AMBUJACEM": "Infra", "SHREECEM": "Infra",
    "LT": "Infra", "DLF": "Realty", "ADANIENT": "Conglomerate", "ADANIPORTS": "Infra",
    "ADANIGREEN": "Power", "ATGL": "Energy",
    "BHARTIARTL": "Telecom", "INDIGO": "Aviation", "IRCTC": "Travel",
    "TATACOMM": "Telecom", "INDUSTOWER": "Telecom",
    "HAVELLS": "Industrial", "SIEMENS": "Industrial", "ABB": "Industrial", "BOSCHLTD": "Auto",
    "PAGEIND": "Consumer", "HCLTECH": "IT",
}

# Sector ETF / proxy for 20-day momentum
SECTOR_ETF: dict[str, str] = {
    "Banking": "BANKBEES",
    "IT": "ITBEES",
    "Pharma": "PHARMABEES",
    "Auto": "AUTOBEES",
    "FMCG": "NIFTYBEES",
    "Energy": "NIFTYBEES",
    "Metal": "NIFTYBEES",
    "NBFC": "BANKBEES",
    "Infra": "NIFTYBEES",
    "Power": "NIFTYBEES",
    "Consumer": "NIFTYBEES",
    "Healthcare": "PHARMABEES",
    "Telecom": "NIFTYBEES",
    "Insurance": "BANKBEES",
    "Chemical": "NIFTYBEES",
    "Industrial": "NIFTYBEES",
    "Realty": "NIFTYBEES",
    "Mining": "NIFTYBEES",
    "Conglomerate": "NIFTYBEES",
    "Aviation": "NIFTYBEES",
    "Travel": "NIFTYBEES",
}


def get_sector(symbol: str) -> str:
    return STOCK_SECTOR.get(symbol.upper(), "Other")