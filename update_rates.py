import os
import json
import requests
from datetime import datetime, timezone


# ============================================================
# CONFIG
# ============================================================

OUTPUT_FOLDER = "v2/currencies"
REQUEST_TIMEOUT = 15

# --- FIAT SOURCES (priority order) ---
# 1) moneyconvert  ~ every 5 min
MONEYCONVERT_URL = "https://cdn.moneyconvert.net/api/latest.json"

# 2) exchangerate.fun  ~ hourly
EXCHANGERATE_FUN_URL = "https://api.exchangerate.fun/latest"

# 3) Fawaz (last fallback only – daily)
FAWAZ_URL = (
    "https://cdn.jsdelivr.net/npm/"
    "@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
)
FAWAZ_BACKUP_URL = "https://latest.currency-api.pages.dev/v1/currencies/usd.json"

# --- CRYPTO ---
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
BINANCE_URL = "https://api.binance.com/api/v3/ticker/price"

CRYPTO_MAPPING = {
    "bitcoin": "btc",
    "ethereum": "eth",
    "solana": "sol",
    "tether": "usdt",
    "binancecoin": "bnb",
    "ripple": "xrp",
    "cardano": "ada",
    "dogecoin": "doge",
    "tron": "trx",
    "chainlink": "link",
}

BINANCE_MAPPING = {
    "BTCUSDT": "btc",
    "ETHUSDT": "eth",
    "SOLUSDT": "sol",
    "BNBUSDT": "bnb",
    "XRPUSDT": "xrp",
    "ADAUSDT": "ada",
    "DOGEUSDT": "doge",
    "TRXUSDT": "trx",
    "LINKUSDT": "link",
}


session = requests.Session()
session.headers.update({
    "User-Agent": "Tayyab-V2-Currency-Updater/3.0",
    "Accept": "application/json",
})


# ============================================================
# FIAT SOURCES
# ============================================================

def _normalize_usd_rates(rates_dict):
    """USD base rates dict → lowercase keys, positive floats only."""
    result = {"usd": 1.0}
    if not isinstance(rates_dict, dict):
        return result

    for currency, rate in rates_dict.items():
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            continue
        if rate > 0:
            result[str(currency).lower()] = rate

    return result


def fetch_fiat_moneyconvert():
    print("Fetching Fiat from moneyconvert.net...")
    r = session.get(MONEYCONVERT_URL, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    # Expected: { "base": "USD", "rates": { "EUR": 0.92, ... } }
    rates = data.get("rates")
    if not rates:
        raise ValueError("moneyconvert: empty rates")

    result = _normalize_usd_rates(rates)
    if len(result) < 10:
        raise ValueError("moneyconvert: too few currencies")
    return result, "moneyconvert.net"


def fetch_fiat_exchangerate_fun():
    print("Fetching Fiat from exchangerate.fun...")
    r = session.get(EXCHANGERATE_FUN_URL, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    rates = data.get("rates")
    if not rates:
        raise ValueError("exchangerate.fun: empty rates")

    result = _normalize_usd_rates(rates)
    if len(result) < 10:
        raise ValueError("exchangerate.fun: too few currencies")
    return result, "exchangerate.fun"


def fetch_fiat_fawaz():
    print("Fetching Fiat from Fawaz (fallback)...")
    for url in (FAWAZ_URL, FAWAZ_BACKUP_URL):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            rates = data.get("usd")
            if not rates:
                continue
            result = _normalize_usd_rates(rates)
            if len(result) >= 10:
                return result, "fawazahmed0/currency-api"
        except Exception as e:
            print(f"  Fawaz URL failed: {e}")
    raise ValueError("Fawaz both endpoints failed")


def fetch_fiat_data():
    """Try sources in order. Return (rates_dict, source_name) or (None, None)."""
    sources = [
        fetch_fiat_moneyconvert,
        fetch_fiat_exchangerate_fun,
        fetch_fiat_fawaz,
    ]
    for fn in sources:
        try:
            rates, source = fn()
            print(f"  OK → {source}: {len(rates)} currencies")
            return rates, source
        except Exception as e:
            print(f"  Failed: {e}")
    return None, None


# ============================================================
# CRYPTO
# ============================================================

def fetch_crypto_coingecko():
    print("Fetching Crypto from CoinGecko...")
    params = {
        "ids": ",".join(CRYPTO_MAPPING.keys()),
        "vs_currencies": "usd",
    }
    r = session.get(COINGECKO_URL, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    result = {"usdt": 1.0}
    for gecko_id, short in CRYPTO_MAPPING.items():
        coin = data.get(gecko_id)
        if not isinstance(coin, dict):
            continue
        try:
            usd_price = float(coin.get("usd"))
        except (TypeError, ValueError):
            continue
        if usd_price > 0:
            # Store as: how many units of crypto = 1 USD
            result[short] = round(1.0 / usd_price, 12)

    if len(result) <= 1:
        raise ValueError("CoinGecko: no usable crypto")
    return result, "coingecko"


def fetch_crypto_binance():
    print("Fetching Crypto from Binance...")
    result = {"usdt": 1.0}
    ok = 0
    for symbol, short in BINANCE_MAPPING.items():
        try:
            r = session.get(
                BINANCE_URL,
                params={"symbol": symbol},
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            price = float(r.json().get("price"))
            if price > 0:
                result[short] = round(1.0 / price, 12)
                ok += 1
        except Exception as e:
            print(f"  Binance {symbol} failed: {e}")

    if ok == 0:
        raise ValueError("Binance: no usable crypto")
    return result, "binance"


def fetch_crypto_data():
    for fn in (fetch_crypto_coingecko, fetch_crypto_binance):
        try:
            rates, source = fn()
            print(f"  OK → {source}: {len(rates)} currencies")
            return rates, source
        except Exception as e:
            print(f"  Failed: {e}")
    return {}, "none"


# ============================================================
# HELPERS
# ============================================================

def validate_rates(rates):
    clean = {}
    if not isinstance(rates, dict):
        return clean
    for currency, rate in rates.items():
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            continue
        if rate > 0:
            clean[str(currency).lower()] = rate
    clean["usd"] = 1.0
    return clean


def write_json_safely(filepath, data):
    temp = filepath + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
    os.replace(temp, filepath)


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("TAYYAB V3 CURRENCY RATE UPDATER")
    print("Multi-source | More frequent than daily-only APIs")
    print("=" * 60)

    # ---- FIAT ----
    fiat_rates, fiat_source = fetch_fiat_data()
    if not fiat_rates:
        print("\nCRITICAL: All fiat sources failed. Existing files NOT changed.\n")
        return

    fiat_rates = validate_rates(fiat_rates)

    # ---- CRYPTO ----
    crypto_rates, crypto_source = fetch_crypto_data()
    crypto_rates = validate_rates(crypto_rates)

    # ---- COMBINE ----
    # Crypto keys overwrite same keys from fiat if present
    all_rates = {**fiat_rates, **crypto_rates}

    now = datetime.now(timezone.utc)
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%Y-%m-%d %H:%M UTC")

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    generated = 0
    for base_currency, base_rate in all_rates.items():
        if base_rate <= 0:
            continue

        converted = {}
        for target, target_rate in all_rates.items():
            if target_rate <= 0:
                continue
            converted[target] = round(target_rate / base_rate, 12)

        api_response = {
            "date": current_date,
            "last_updated": current_time,
            "sources": {
                "fiat": fiat_source,
                "crypto": crypto_source,
            },
            base_currency: converted,
        }

        filepath = os.path.join(OUTPUT_FOLDER, f"{base_currency}.json")
        write_json_safely(filepath, api_response)
        generated += 1

    print()
    print("=" * 60)
    print("UPDATE COMPLETED")
    print("=" * 60)
    print(f"Fiat source       : {fiat_source}")
    print(f"Crypto source     : {crypto_source}")
    print(f"Fiat currencies   : {len(fiat_rates)}")
    print(f"Crypto currencies : {len(crypto_rates)}")
    print(f"Total             : {len(all_rates)}")
    print(f"JSON files        : {generated}")
    print(f"Updated           : {current_time}")
    print("=" * 60)


if __name__ == "__main__":
    main()
