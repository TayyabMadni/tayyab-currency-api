import os
import json
import requests
from datetime import datetime, timezone


# ============================================================
# CONFIG
# ============================================================

OUTPUT_FOLDER = "v2/currencies"
REQUEST_TIMEOUT = 15

# Fawaz Ahmed Currency API
FAWAZ_FIAT_URL = (
    "https://cdn.jsdelivr.net/npm/"
    "@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
)

# Backup Fawaz endpoint
FAWAZ_BACKUP_URL = (
    "https://latest.currency-api.pages.dev/v1/currencies/usd.json"
)

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
    "chainlink": "link"
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
    "LINKUSDT": "link"
}


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "Tayyab-V2-Currency-Updater/2.0",
    "Accept": "application/json"
})


# ============================================================
# FIAT - FAWAZ PRIMARY
# ============================================================

def fetch_fiat_primary():

    print("Fetching Fiat from Fawaz Ahmed API...")

    response = session.get(
        FAWAZ_FIAT_URL,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    rates = data.get("usd")

    if not isinstance(rates, dict) or not rates:
        raise ValueError(
            "Fawaz API returned empty USD rates."
        )

    result = {
        "usd": 1.0
    }

    for currency, rate in rates.items():

        try:
            rate = float(rate)
        except (TypeError, ValueError):
            continue

        if rate > 0:
            result[currency.lower()] = rate

    if len(result) < 2:
        raise ValueError(
            "Fawaz API returned insufficient currency data."
        )

    return result


# ============================================================
# FIAT - FAWAZ BACKUP
# ============================================================

def fetch_fiat_backup():

    print("Fetching Fiat from Fawaz Backup API...")

    response = session.get(
        FAWAZ_BACKUP_URL,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    rates = data.get("usd")

    if not isinstance(rates, dict) or not rates:
        raise ValueError(
            "Fawaz Backup API returned empty USD rates."
        )

    result = {
        "usd": 1.0
    }

    for currency, rate in rates.items():

        try:
            rate = float(rate)
        except (TypeError, ValueError):
            continue

        if rate > 0:
            result[currency.lower()] = rate

    if len(result) < 2:
        raise ValueError(
            "Fawaz Backup API returned insufficient data."
        )

    return result


# ============================================================
# FIAT CONTROLLER
# ============================================================

def fetch_fiat_data():

    try:

        rates = fetch_fiat_primary()

        print(
            f"Fawaz Fiat successful: {len(rates)} currencies."
        )

        return rates

    except Exception as error:

        print(
            f"Fawaz Primary failed: {error}"
        )


    try:

        rates = fetch_fiat_backup()

        print(
            f"Fawaz Backup successful: {len(rates)} currencies."
        )

        return rates

    except Exception as error:

        print(
            f"Fawaz Backup failed: {error}"
        )

    return None


# ============================================================
# CRYPTO - COINGECKO PRIMARY
# ============================================================

def fetch_crypto_coingecko():

    print("Fetching Crypto from CoinGecko...")

    crypto_ids = ",".join(
        CRYPTO_MAPPING.keys()
    )

    params = {
        "ids": crypto_ids,
        "vs_currencies": "usd"
    }

    response = session.get(
        COINGECKO_URL,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict) or not data:
        raise ValueError(
            "CoinGecko returned empty data."
        )

    result = {
        "usdt": 1.0
    }

    for gecko_id, short_name in CRYPTO_MAPPING.items():

        coin = data.get(gecko_id)

        if not isinstance(coin, dict):
            print(
                f"CoinGecko missing: {gecko_id}"
            )
            continue

        usd_price = coin.get("usd")

        try:
            usd_price = float(usd_price)
        except (TypeError, ValueError):
            continue

        if usd_price <= 0:
            continue

        result[short_name] = round(
            1.0 / usd_price,
            12
        )

    if len(result) <= 1:
        raise ValueError(
            "CoinGecko returned no usable crypto prices."
        )

    return result


# ============================================================
# CRYPTO - BINANCE BACKUP
# ============================================================

def fetch_crypto_binance():

    print("Fetching Crypto from Binance...")

    result = {
        "usdt": 1.0
    }

    successful = 0

    for symbol, short_name in BINANCE_MAPPING.items():

        try:

            response = session.get(
                BINANCE_URL,
                params={
                    "symbol": symbol
                },
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()

            data = response.json()

            price = data.get("price")

            try:
                price = float(price)
            except (TypeError, ValueError):
                continue

            if price <= 0:
                continue

            result[short_name] = round(
                1.0 / price,
                12
            )

            successful += 1

        except Exception as error:

            print(
                f"Binance failed for {symbol}: {error}"
            )

    if successful == 0:
        raise ValueError(
            "Binance returned no usable crypto prices."
        )

    return result


# ============================================================
# CRYPTO CONTROLLER
# ============================================================

def fetch_crypto_data():

    try:

        rates = fetch_crypto_coingecko()

        print(
            f"CoinGecko successful: {len(rates)} currencies."
        )

        return rates

    except Exception as error:

        print(
            f"CoinGecko failed: {error}"
        )


    try:

        rates = fetch_crypto_binance()

        print(
            f"Binance successful: {len(rates)} currencies."
        )

        return rates

    except Exception as error:

        print(
            f"Binance failed: {error}"
        )

    return {}


# ============================================================
# VALIDATE RATES
# ============================================================

def validate_rates(rates):

    if not isinstance(rates, dict):
        return {}

    clean = {}

    for currency, rate in rates.items():

        try:
            rate = float(rate)
        except (TypeError, ValueError):
            continue

        if rate <= 0:
            continue

        clean[currency.lower()] = rate

    clean["usd"] = 1.0

    return clean


# ============================================================
# SAFE JSON WRITE
# ============================================================

def write_json_safely(filepath, data):

    temp_filepath = filepath + ".tmp"

    with open(
        temp_filepath,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )

        file.write("\n")

    os.replace(
        temp_filepath,
        filepath
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("TAYYAB V2 CURRENCY RATE UPDATER")
    print("Powered by Fawaz Ahmed Currency API")
    print("=" * 60)


    # --------------------------------------------------------
    # FIAT
    # --------------------------------------------------------

    fiat_rates = fetch_fiat_data()

    if not fiat_rates:

        print()
        print("CRITICAL ERROR")
        print("Both Fawaz Fiat APIs failed.")
        print("Existing data will NOT be modified.")
        print()

        return


    fiat_rates = validate_rates(
        fiat_rates
    )


    if "usd" not in fiat_rates:

        print(
            "CRITICAL ERROR: USD rate missing."
        )

        return


    # --------------------------------------------------------
    # CRYPTO
    # --------------------------------------------------------

    crypto_rates = fetch_crypto_data()

    crypto_rates = validate_rates(
        crypto_rates
    )


    # --------------------------------------------------------
    # COMBINE
    # --------------------------------------------------------

    all_rates = {
        **fiat_rates,
        **crypto_rates
    }


    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    now = datetime.now(
        timezone.utc
    )

    current_date = now.strftime(
        "%Y-%m-%d"
    )

    current_time = now.strftime(
        "%Y-%m-%d %H:%M UTC"
    )


    # --------------------------------------------------------
    # OUTPUT DIRECTORY
    # --------------------------------------------------------

    os.makedirs(
        OUTPUT_FOLDER,
        exist_ok=True
    )


    # --------------------------------------------------------
    # GENERATE FILES
    # --------------------------------------------------------

    generated = 0

    for base_currency, base_rate in all_rates.items():

        if base_rate <= 0:
            continue


        converted_rates = {}


        for target_currency, target_rate in all_rates.items():

            if target_rate <= 0:
                continue


            converted_rates[target_currency] = round(
                target_rate / base_rate,
                12
            )


        api_response = {
            "date": current_date,
            "last_updated": current_time,
            base_currency: converted_rates
        }


        filepath = os.path.join(
            OUTPUT_FOLDER,
            f"{base_currency}.json"
        )


        write_json_safely(
            filepath,
            api_response
        )


        generated += 1


    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("UPDATE COMPLETED SUCCESSFULLY")
    print("=" * 60)

    print(
        f"Fiat currencies   : {len(fiat_rates)}"
    )

    print(
        f"Crypto currencies: {len(crypto_rates)}"
    )

    print(
        f"Total currencies  : {len(all_rates)}"
    )

    print(
        f"JSON files        : {generated}"
    )

    print(
        f"Updated           : {current_time}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
