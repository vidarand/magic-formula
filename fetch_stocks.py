#!/usr/bin/env python3
"""
Fetch stock data and maintain history.
Updates stocks that need updating and tracks last_updated timestamps.
"""

import json
import yfinance as yf
import pandas as pd
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union
from schema import create_empty_stock, normalize_stock

# Type alias for stock values
StockValue = Union[int, float, str, None]

# Cache for exchange rates to avoid repeated API calls

# File paths
STOCKS_JSON = Path("stockholm_stocks.json")
CURRENT_DATA = Path("data/current_stocks.json")
HISTORY_DATA = Path("data/stock_history.json")


def load_tickers() -> list:
    """Load ticker list from JSON file."""
    if not STOCKS_JSON.exists():
        print(f"Error: {STOCKS_JSON} not found!")
        return []

    with open(STOCKS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def load_current_data() -> Dict:
    """Load current stock data."""
    if CURRENT_DATA.exists():
        with open(CURRENT_DATA, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_current_data(data: Dict):
    """Save current stock data."""
    CURRENT_DATA.parent.mkdir(exist_ok=True)
    with open(CURRENT_DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_history() -> Dict:
    """
    Load historical stock data.
    Converts old format (list of entries) to new format (dict by date) if needed.
    """
    if HISTORY_DATA.exists():
        try:
            with open(HISTORY_DATA, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    return {}
                history = json.loads(content)

                # Convert old format (list) to new format (dict by date)
                converted = False
                for ticker, entries in history.items():
                    if isinstance(entries, list):
                        # Old format: list of entries
                        converted = True
                        new_entries = {}
                        for entry in entries:
                            # Extract date from timestamp
                            timestamp = entry.get("timestamp", "")
                            if isinstance(timestamp, str):
                                date_str = timestamp.split("T")[0]
                            else:
                                continue

                            # Only keep Magic Formula fields
                            new_entry = {
                                "date": date_str,
                                "price": entry.get("price"),
                                "market_cap": entry.get("market_cap"),
                                "ebit": entry.get("ebit"),
                                "enterprise_value": entry.get("enterprise_value"),
                                "total_assets": entry.get("total_assets"),
                                "current_liabilities": entry.get("current_liabilities"),
                                "current_assets": entry.get("current_assets"),
                                "net_fixed_assets": entry.get("net_fixed_assets"),
                                "magic_formula_score": entry.get("magic_formula_score"),
                            }
                            # Keep only the latest entry per day
                            if date_str not in new_entries:
                                new_entries[date_str] = new_entry

                        history[ticker] = new_entries

                if converted:
                    # Save converted format
                    save_history(history)
                    print("   Converted history to new format (one entry per day)")

                return history
        except json.JSONDecodeError as e:
            print(
                f"⚠️  Warning: History file is corrupted (line {e.lineno}, col {e.colno}). Starting fresh."
            )
            # Backup corrupted file
            backup_path = HISTORY_DATA.with_suffix(".json.backup")
            try:
                if backup_path.exists():
                    backup_path.unlink()
                HISTORY_DATA.rename(backup_path)
                print(f"   Corrupted file backed up to {backup_path}")
            except Exception:
                pass  # If backup fails, just continue
            return {}
        except Exception as e:
            print(f"⚠️  Warning: Error loading history file: {e}. Starting fresh.")
            return {}
    return {}


def save_history(history: Dict):
    """Save historical stock data."""
    HISTORY_DATA.parent.mkdir(exist_ok=True)
    with open(HISTORY_DATA, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def calculate_magic_formula_scores(stocks):
    """
    Calculate Magic Formula scores for all stocks.
    Returns stocks with magic_formula_score added.
    Also adds magic_formula_reason to explain why score is N/A if applicable.
    """
    # Filter out stocks with errors or missing data
    valid_stocks = []
    for stock in stocks:
        if stock.get("error"):
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Error fetching data"
            continue

        # Only calculate Magic Formula for stocks in SEK
        currency = stock.get("currency", "N/A")
        if currency != "SEK" and currency != "N/A":
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = f"Currency is {currency}, only SEK stocks are calculated"
            continue

        ebit = stock.get("ebit", "N/A")
        ev = stock.get("enterprise_value", "N/A")
        net_fixed_assets = stock.get("net_fixed_assets", "N/A")
        current_assets = stock.get("current_assets", "N/A")
        current_liabilities = stock.get("current_liabilities", "N/A")

        # Skip if required fields are missing
        if ebit == "N/A" or ebit is None:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Missing EBIT"
            continue
        if ev == "N/A" or ev is None:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Missing Enterprise Value"
            continue
        if net_fixed_assets == "N/A" or net_fixed_assets is None:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Missing Net Fixed Assets"
            continue
        if current_assets == "N/A" or current_assets is None:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Missing Current Assets"
            continue
        if current_liabilities == "N/A" or current_liabilities is None:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Missing Current Liabilities"
            continue

        try:
            ebit_val = float(ebit)
            ev_val = float(ev)
            net_fixed_assets_val = float(net_fixed_assets)
            current_assets_val = float(current_assets)
            liab_val = float(current_liabilities)

            # Calculate Earnings Yield
            ey = ebit_val / ev_val if ev_val > 0 else 0

            # Calculate Return on Capital using: EBIT / (Net Fixed Assets + Net Working Capital)
            # where Net Working Capital = Current Assets - Current Liabilities
            net_working_capital = current_assets_val - liab_val
            invested_capital = net_fixed_assets_val + net_working_capital
            roc = ebit_val / invested_capital if invested_capital > 0 else 0

            if ey > 0 and roc > 0:
                valid_stocks.append({"stock": stock, "ey": ey, "roc": roc})
            else:
                stock["magic_formula_score"] = "N/A"
                if ebit_val < 0:
                    stock["magic_formula_reason"] = "Negative EBIT (losses)"
                elif ey <= 0:
                    stock["magic_formula_reason"] = "Negative/zero Earnings Yield"
                elif roc <= 0:
                    stock["magic_formula_reason"] = "Negative/zero Return on Capital"
                else:
                    stock["magic_formula_reason"] = "Cannot calculate"
        except (ValueError, ZeroDivisionError) as e:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = f"Calculation error: {str(e)[:30]}"

    # Rank by Earnings Yield (higher is better, so rank 1 is best)
    valid_stocks.sort(key=lambda x: x["ey"], reverse=True)
    for idx, item in enumerate(valid_stocks):
        item["ey_rank"] = idx + 1

    # Rank by Return on Capital (higher is better, so rank 1 is best)
    valid_stocks.sort(key=lambda x: x["roc"], reverse=True)
    for idx, item in enumerate(valid_stocks):
        item["roc_rank"] = idx + 1

    # Calculate combined score (lower is better)
    for item in valid_stocks:
        magic_score = item["ey_rank"] + item["roc_rank"]
        item["stock"]["magic_formula_score"] = magic_score
        item["stock"]["magic_formula_reason"] = None  # Clear reason for valid scores

    return stocks


def get_exchange_rate_to_sek(currency: str) -> float:
    """
    Get exchange rate from given currency to SEK.
    Returns 1.0 if currency is SEK or if conversion fails.
    Caches rates to avoid repeated API calls.
    """
    if currency == "SEK" or currency == "N/A" or not currency:
        return 1.0

    # Check cache first
    cache_key = f"{currency}_SEK"
    if cache_key in _exchange_rate_cache:
        return _exchange_rate_cache[cache_key]

    try:
        # Try to get exchange rate from yfinance
        # Format: EURSEK=X, USDSEK=X, NOKSEK=X, etc.
        if currency == "EUR":
            ticker = yf.Ticker("EURSEK=X")
        elif currency == "USD":
            ticker = yf.Ticker("USDSEK=X")
        elif currency == "NOK":
            ticker = yf.Ticker("NOKSEK=X")
        elif currency == "DKK":
            ticker = yf.Ticker("DKKSEK=X")
        elif currency == "GBP":
            ticker = yf.Ticker("GBPSEK=X")
        elif currency == "CHF":
            ticker = yf.Ticker("CHFSEK=X")
        else:
            # Unknown currency, default to 1.0
            print(f"Warning: Unknown currency {currency}, assuming 1.0 SEK")
            _exchange_rate_cache[cache_key] = 1.0
            return 1.0

        info = ticker.info
        if info and "regularMarketPrice" in info:
            rate = float(info["regularMarketPrice"])
            _exchange_rate_cache[cache_key] = rate
            return rate
        else:
            # Try getting from history
            hist = ticker.history(period="1d")
            if not hist.empty:
                rate = float(hist["Close"].iloc[-1])
                _exchange_rate_cache[cache_key] = rate
                return rate
    except Exception as e:
        print(f"Warning: Could not get exchange rate for {currency}: {e}")

    # Default to 1.0 if conversion fails
    _exchange_rate_cache[cache_key] = 1.0
    return 1.0


def convert_to_sek(value: StockValue, currency: str) -> StockValue:
    """
    Convert a financial value to SEK.
    Returns the value unchanged if it's "N/A" or not a number.
    """
    if value == "N/A" or value is None:
        return value

    if not isinstance(value, (int, float)):
        return value

    if currency == "SEK" or currency == "N/A" or not currency:
        return value

    rate = get_exchange_rate_to_sek(currency)
    return float(value) * rate


def get_market_cap_category(market_cap: StockValue) -> str:
    """
    Classify market cap into categories.
    Thresholds (in SEK, approximate):
    - Large-cap: ≥ 100 billion SEK (~$10B)
    - Mid-cap: 15 billion to 100 billion SEK (~$1.5B-$10B)
    - Small-cap: 1 billion to 15 billion SEK (~$100M-$1.5B)
    - Micro-cap: < 1 billion SEK (~$100M)
    """
    if market_cap == "N/A" or market_cap is None:
        return "N/A"

    if not isinstance(market_cap, (int, float)):
        return "N/A"

    # Convert to billions for comparison (thresholds in billions)
    cap_billions = market_cap / 1e9

    if cap_billions >= 100:
        return "Large-cap"
    elif cap_billions >= 15:
        return "Mid-cap"
    elif cap_billions >= 1:
        return "Small-cap"
    else:
        return "Micro-cap"


def normalize_ticker(ticker: str) -> str:
    """Normalize ticker for yfinance.

    Yahoo Finance uses dashes for share classes and special suffixes:
    - STAR.A -> STAR-A.ST (not STAR.A.ST)
    - STAR.B -> STAR-B.ST (not STAR.B.ST)
    - ARION.SDB -> ARION-SDB.ST (not ARION.SDB)
    - SAMPO.SDB -> SAMPO-SDB.ST
    """
    # Special suffixes that need to be converted to dash + .ST
    special_suffixes = [".SDB", ".STAM", ".PREF"]

    # Check if ticker ends with a special suffix that needs conversion
    for suffix in special_suffixes:
        if ticker.endswith(suffix):
            # Convert: ARION.SDB -> ARION-SDB.ST
            base = ticker[: -len(suffix)]  # Remove suffix
            return f"{base}-{suffix[1:]}.ST"  # suffix[1:] removes the dot

    # .SE and .SEK should be converted to .ST for Yahoo Finance
    # Yahoo Finance typically uses .ST for Stockholm exchange
    if ticker.endswith(".SE"):
        return ticker[:-3] + ".ST"
    if ticker.endswith(".SEK"):
        return ticker[:-4] + ".ST"

    # Handle Helsinki listings (e.g., NDA-HE, NOKIA-HE)
    # For Helsinki exchange, use .HE suffix instead of .ST
    if ticker.endswith("-HE"):
        base = ticker[:-3]  # Remove -HE
        return f"{base}.HE"  # NDA-HE -> NDA.HE

    if ticker.endswith(".ST"):
        # Already has .ST suffix, but check if it has share class with dot
        # e.g., "STAR.A.ST" -> "STAR-A.ST"
        if "." in ticker[:-3]:  # Check if there's a dot before .ST
            base = ticker[:-3]  # Remove .ST
            if "." in base:
                # Replace dot with dash for share class
                base = base.replace(".", "-", 1)  # Replace first dot with dash
                return f"{base}.ST"
        return ticker

    # Check if ticker has share class (e.g., "STAR.A", "STAR.B")
    if "." in ticker:
        # Replace dot with dash for share class
        base = ticker.replace(".", "-", 1)  # Replace first dot with dash
        return f"{base}.ST"

    return f"{ticker}.ST"


def get_ticker_alternatives(ticker: str) -> list:
    """Get alternative ticker formats to try if primary format fails.

    Returns a list of ticker formats to try in order.
    """
    alternatives = []
    base_ticker = ticker

    # Remove any existing suffix to get base
    for suffix in [".ST", ".SE", ".SEK", ".OL", ".HE", ".CO"]:
        if base_ticker.endswith(suffix):
            base_ticker = base_ticker[: -len(suffix)]
            break

    # Primary format (from normalize_ticker)
    alternatives.append(normalize_ticker(ticker))

    # Try Oslo exchange (.OL) for Norwegian companies
    # Common Norwegian tickers that might be on Oslo
    norwegian_tickers = [
        "KOGO",
        "FROO",
        "DNBO",
        "HAUTOO",
        "BWEO",
        "KCCO",
        "MEDIO",
        "ENVIPO",
        "NORSEO",
        "CAPSLO",
        "CAVENO",
        "LIFEO",
    ]
    if base_ticker in norwegian_tickers:
        alternatives.append(f"{base_ticker}.OL")

    # Try Helsinki exchange (.HE) for Finnish companies
    finnish_tickers = ["NOKIA", "STE", "SAMPO", "TIETOS", "NDA"]
    if base_ticker in finnish_tickers:
        alternatives.append(f"{base_ticker}.HE")

    # Handle NDA-HE specifically (Nordea Bank on Helsinki)
    if ticker == "NDA-HE" or ticker.endswith("-HE"):
        base = ticker.replace("-HE", "")
        alternatives.insert(0, f"{base}.HE")  # Try NDA.HE first

    # Try without any suffix (might be US-listed or other)
    alternatives.append(base_ticker)

    # Remove duplicates while preserving order
    seen = set()
    unique_alternatives = []
    for alt in alternatives:
        if alt not in seen:
            seen.add(alt)
            unique_alternatives.append(alt)

    return unique_alternatives


def add_to_history(ticker: str, stock_data: Dict, history: Dict):
    """
    Add current data point to history.
    Only stores one entry per stock per day.
    Only stores fields needed for Magic Formula calculation and ranking.
    """
    if ticker not in history:
        history[ticker] = {}

    # Get date from timestamp (YYYY-MM-DD format)
    try:
        timestamp_str = stock_data.get("last_updated", datetime.now().isoformat())
        if isinstance(timestamp_str, str):
            date_str = timestamp_str.split("T")[0]  # Extract date part
        else:
            date_str = datetime.now().date().isoformat()
    except:
        date_str = datetime.now().date().isoformat()

    # Only store Magic Formula relevant fields
    history_entry = {
        "date": date_str,
        "price": stock_data.get("price"),
        "market_cap": stock_data.get("market_cap"),
        "ebit": stock_data.get("ebit"),
        "enterprise_value": stock_data.get("enterprise_value"),
        "total_assets": stock_data.get("total_assets"),
        "current_liabilities": stock_data.get("current_liabilities"),
        "current_assets": stock_data.get("current_assets"),
        "net_fixed_assets": stock_data.get("net_fixed_assets"),
        "magic_formula_score": stock_data.get("magic_formula_score"),
    }

    # Store by date (overwrites if same day)
    history[ticker][date_str] = history_entry


def should_update_stock(ticker: str, current_data: Dict, force: bool = False) -> bool:
    """Determine if a stock should be updated."""
    if force:
        return True

    if ticker not in current_data:
        return True

    stock_data = current_data[ticker]

    # Always retry if there was an error
    if stock_data.get("error"):
        return True

    # Check last updated time - update if older than 1 hour
    last_updated_str = stock_data.get("last_updated")
    if last_updated_str:
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            hours_old = (datetime.now() - last_updated).total_seconds() / 3600
            if hours_old > 1:  # Update if older than 1 hour
                return True
        except:
            return True

    return False


def fetch_single_stock_with_fallback(ticker: str, name: str) -> Dict:
    """Fetch a single stock, trying alternative ticker formats if needed."""
    alternatives = get_ticker_alternatives(ticker)

    for attempt, normalized_ticker in enumerate(alternatives):
        try:
            stock = yf.Ticker(normalized_ticker)
            info = stock.info

            # Quick check if we got valid data
            if info and len(info) > 5:  # Valid info dict has many keys
                # Try to get price to confirm it's a valid ticker
                hist = stock.history(period="1d")
                if not hist.empty or info.get("regularMarketPrice"):
                    # This ticker format works, use it
                    return fetch_stock_data_from_ticker(
                        ticker, name, normalized_ticker, stock
                    )
        except Exception:
            # Try next alternative
            continue

    # All alternatives failed
    stock_data = create_empty_stock(ticker, name, alternatives[0])
    stock_data["error"] = f"No data found (tried: {', '.join(alternatives)})"
    return stock_data


def fetch_stock_data_from_ticker(
    original_ticker: str, name: str, normalized_ticker: str, stock
) -> Dict:
    """Extract stock data from a yfinance Ticker object."""
    stock_data = create_empty_stock(original_ticker, name, normalized_ticker)

    try:
        info = stock.info

        # Get current price
        hist = stock.history(period="1d")
        current_price = (
            hist["Close"].iloc[-1]
            if not hist.empty
            else info.get("regularMarketPrice", "N/A")
        )

        # Get previous close
        prev_close = info.get(
            "previousClose",
            current_price if isinstance(current_price, (int, float)) else 0,
        )

        # Calculate change
        if isinstance(current_price, (int, float)) and isinstance(
            prev_close, (int, float)
        ):
            change = current_price - prev_close
            change_percent = (change / prev_close * 100) if prev_close != 0 else 0
        else:
            change = "N/A"
            change_percent = "N/A"

        # Get financial statements for Magic Formula
        financials = stock.financials
        balance_sheet = stock.balance_sheet

        # Get EBIT - try multiple possible index names
        ebit = "N/A"
        ebit_names = [
            "Ebit",
            "EBIT",
            "Operating Income",
            "OperatingIncome",
            "EBITDA",
        ]
        if not financials.empty:
            for ebit_name in ebit_names:
                if ebit_name in financials.index:
                    try:
                        ebit_value = financials.loc[ebit_name].iloc[0]
                        if pd.notna(ebit_value) and isinstance(
                            ebit_value, (int, float)
                        ):
                            ebit = float(ebit_value)
                            break
                    except:
                        continue

        # If EBIT still not found, try from info dict
        if ebit == "N/A":
            ebit = info.get("ebit", info.get("operatingIncome", "N/A"))
            if ebit != "N/A" and isinstance(ebit, (int, float)):
                ebit = float(ebit)
            else:
                ebit = "N/A"

        # Get balance sheet data for Magic Formula - try multiple possible index names
        total_assets = "N/A"
        current_assets = "N/A"
        current_liabilities = "N/A"
        net_fixed_assets = "N/A"

        if not balance_sheet.empty:
            # Try different names for Total Assets
            total_asset_names = ["Total Assets", "TotalAssets"]
            for asset_name in total_asset_names:
                if asset_name in balance_sheet.index:
                    try:
                        assets_value = balance_sheet.loc[asset_name].iloc[0]
                        if pd.notna(assets_value) and isinstance(
                            assets_value, (int, float)
                        ):
                            total_assets = assets_value
                            break
                    except:
                        continue

            # Try different names for Current Assets
            current_asset_names = [
                "Total Current Assets",
                "Current Assets",
                "CurrentAssets",
                "TotalCurrentAssets",
            ]
            for asset_name in current_asset_names:
                if asset_name in balance_sheet.index:
                    try:
                        assets_value = balance_sheet.loc[asset_name].iloc[0]
                        if pd.notna(assets_value) and isinstance(
                            assets_value, (int, float)
                        ):
                            current_assets = assets_value
                            break
                    except:
                        continue

            # Try different names for Current Liabilities
            liability_names = [
                "Total Current Liabilities",
                "Current Liabilities",
                "CurrentLiabilities",
                "TotalCurrentLiabilities",
            ]
            for liability_name in liability_names:
                if liability_name in balance_sheet.index:
                    try:
                        liab_value = balance_sheet.loc[liability_name].iloc[0]
                        if pd.notna(liab_value) and isinstance(
                            liab_value, (int, float)
                        ):
                            current_liabilities = liab_value
                            break
                    except:
                        continue

            # Try different names for Net Fixed Assets / PP&E
            fixed_asset_names = [
                "Property Plant Equipment Net",
                "Net PPE",
                "PPE Net",
                "Property Plant And Equipment Net",
                "Net Property Plant And Equipment",
                "Fixed Assets",
                "Net Fixed Assets",
                "Property, Plant & Equipment",
            ]
            for fixed_name in fixed_asset_names:
                if fixed_name in balance_sheet.index:
                    try:
                        fixed_value = balance_sheet.loc[fixed_name].iloc[0]
                        if pd.notna(fixed_value) and isinstance(
                            fixed_value, (int, float)
                        ):
                            net_fixed_assets = fixed_value
                            break
                    except:
                        continue

        # Fallback to info dict if not found in balance sheet
        if total_assets == "N/A":
            total_assets = info.get("totalAssets", "N/A")
            if total_assets == "N/A" or not isinstance(total_assets, (int, float)):
                total_assets = "N/A"

        if current_assets == "N/A":
            current_assets = info.get(
                "totalCurrentAssets", info.get("currentAssets", "N/A")
            )
            if current_assets == "N/A" or not isinstance(current_assets, (int, float)):
                current_assets = "N/A"

        if current_liabilities == "N/A":
            current_liabilities = info.get(
                "totalCurrentLiabilities", info.get("currentLiabilities", "N/A")
            )
            if current_liabilities == "N/A" or not isinstance(
                current_liabilities, (int, float)
            ):
                current_liabilities = "N/A"

        # Get currency - store as-is, no conversion
        currency = info.get("currency", "SEK")

        # Get values - store as-is, no conversion
        market_cap = info.get("marketCap", "N/A")
        enterprise_value = info.get("enterpriseValue", "N/A")
        ebit_value = ebit if isinstance(ebit, (int, float)) else "N/A"
        total_assets_value = (
            total_assets if isinstance(total_assets, (int, float)) else "N/A"
        )
        current_assets_value = (
            current_assets if isinstance(current_assets, (int, float)) else "N/A"
        )
        current_liabilities_value = (
            current_liabilities
            if isinstance(current_liabilities, (int, float))
            else "N/A"
        )
        net_fixed_assets_value = (
            net_fixed_assets if isinstance(net_fixed_assets, (int, float)) else "N/A"
        )

        # Update stock data - only essential fields
        stock_data.update(
            {
                # Basic price data
                "price": (
                    round(current_price, 2)
                    if isinstance(current_price, (int, float))
                    else current_price
                ),
                "change": (
                    round(change, 2) if isinstance(change, (int, float)) else change
                ),
                "change_percent": (
                    round(change_percent, 2)
                    if isinstance(change_percent, (int, float))
                    else change_percent
                ),
                "currency": currency,  # Store original currency
                # Market data (stored as-is, no conversion)
                "market_cap": market_cap,
                "volume": info.get("volume", "N/A"),
                # Descriptive/Classification (needed for Magic Formula filtering)
                "sector": info.get("sector", "N/A"),
                "industry": info.get("industry", "N/A"),
                "country": info.get("country", "Sweden"),
                "description": info.get(
                    "longBusinessSummary", info.get("description", "N/A")
                ),
                "market_cap_category": get_market_cap_category(market_cap) if isinstance(market_cap, (int, float)) else "N/A",
                "market": info.get("market", "N/A"),
                # Interesting metrics
                "pe_ratio": info.get("trailingPE", info.get("forwardPE", "N/A")),
                "dividend_yield": info.get("dividendYield", "N/A"),
                # Magic Formula required fields (stored as-is, no conversion)
                "enterprise_value": enterprise_value,
                "ebit": ebit_value,
                "total_assets": total_assets_value,
                "current_assets": current_assets_value,
                "current_liabilities": current_liabilities_value,
                "net_fixed_assets": net_fixed_assets_value,
                "last_updated": datetime.now().isoformat(),
                "error": None,
            }
        )

        # Check if we got meaningful data - if all key fields are N/A, set an error
        key_fields = ["price", "market_cap", "sector"]
        all_na = all(
            stock_data.get(field) == "N/A" or stock_data.get(field) is None
            for field in key_fields
        )
        if all_na:
            stock_data["error"] = "No data available from yfinance"

    except Exception as e:
        stock_data["error"] = str(e)
        stock_data["last_updated"] = datetime.now().isoformat()

    return stock_data


def fetch_batch_stock_data(batch_stocks: list) -> Dict[str, Dict]:
    """
    Fetch stock data for multiple tickers at once using yf.Tickers.
    batch_stocks: list of dicts with 'ticker' and 'name' keys
    Returns: dict mapping ticker -> stock_data
    """
    # Normalize all tickers
    ticker_map = {}  # normalized_ticker -> (original_ticker, name)
    normalized_tickers = []

    for stock_info in batch_stocks:
        ticker = stock_info["ticker"]
        name = stock_info["name"]
        normalized = normalize_ticker(ticker)
        ticker_map[normalized] = (ticker, name)
        normalized_tickers.append(normalized)

    # Fetch all tickers at once
    try:
        tickers = yf.Tickers(" ".join(normalized_tickers))
    except Exception as e:
        # If batch fetch fails, return errors for all
        result = {}
        for stock_info in batch_stocks:
            ticker = stock_info["ticker"]
            name = stock_info["name"]
            normalized = normalize_ticker(ticker)
            stock_data = create_empty_stock(ticker, name, normalized)
            stock_data["error"] = f"Batch fetch failed: {str(e)}"
            result[ticker] = stock_data
        return result

    # Process each ticker from the batch
    result = {}
    for normalized_ticker in normalized_tickers:
        original_ticker, name = ticker_map[normalized_ticker]
        stock_data = create_empty_stock(original_ticker, name, normalized_ticker)

        try:
            stock = tickers.tickers[normalized_ticker]
            info = stock.info

            # Check if we got valid data
            if not info or len(info) < 5:
                # Try fallback alternatives
                stock_data = fetch_single_stock_with_fallback(original_ticker, name)
                result[original_ticker] = stock_data
                continue

            # Use the extracted data function
            stock_data = fetch_stock_data_from_ticker(
                original_ticker, name, normalized_ticker, stock
            )

        except Exception as e:
            # If batch fetch failed, try fallback alternatives
            stock_data = fetch_single_stock_with_fallback(original_ticker, name)
            if stock_data.get("error"):
                # All alternatives failed, use the error from fallback
                stock_data["error"] = (
                    f"Batch fetch error: {str(e)}. {stock_data.get('error', '')}"
                )

        result[original_ticker] = stock_data

    return result


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Fetch stock data and maintain history"
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force update all stocks regardless of last_updated timestamp",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Limit the number of stocks to process (processes oldest first)",
    )
    args = parser.parse_args()

    force_update = args.force
    limit = args.limit

    print("=" * 60)
    print("Stock Data Fetcher")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    tickers_list = load_tickers()
    current_data = load_current_data()
    history = load_history()

    print(f"  Tickers in list: {len(tickers_list)}")
    print(f"  Current data: {len(current_data)} stocks")
    # Count history entries (handle both old list format and new dict format)
    total_entries = 0
    for entries in history.values():
        if isinstance(entries, dict):
            total_entries += len(entries)
        elif isinstance(entries, list):
            total_entries += len(entries)
    print(f"  History entries: {total_entries} total")

    # Determine which stocks need updating
    to_update = []
    to_skip = []

    for stock_info in tickers_list:
        ticker = stock_info["ticker"]
        if should_update_stock(ticker, current_data, force_update):
            to_update.append(stock_info)
        else:
            to_skip.append(ticker)

    print(f"\n  Stocks to update: {len(to_update)}")
    print(f"  Stocks to skip (recently updated): {len(to_skip)}")

    if to_skip and not force_update:
        print(
            f"\n  Skipping: {', '.join(to_skip[:10])}{'...' if len(to_skip) > 10 else ''}"
        )

    # Sort stocks by last_updated (oldest first)
    def get_last_updated_timestamp(stock_info):
        ticker = stock_info["ticker"]
        if ticker in current_data:
            last_updated_str = current_data[ticker].get("last_updated")
            if last_updated_str and last_updated_str != "N/A":
                try:
                    return datetime.fromisoformat(last_updated_str)
                except:
                    pass
        # If no last_updated or error, treat as very old (update first)
        return datetime.min

    to_update.sort(key=get_last_updated_timestamp)

    # Apply limit if specified
    if limit and limit > 0:
        original_count = len(to_update)
        to_update = to_update[:limit]
        print(f"\n  Limiting to {limit} stocks (oldest first)")
        print(
            f"  Will process {len(to_update)} stocks (skipping {original_count - len(to_update)} others)"
        )

    # Process in batches of 5
    batch_size = 5
    total_batches = (len(to_update) + batch_size - 1) // batch_size

    updated_count = 0
    for batch_num in range(total_batches):
        batch_start = batch_num * batch_size
        batch_end = min(batch_start + batch_size, len(to_update))
        batch = to_update[batch_start:batch_end]

        print(f"\n{'=' * 60}")
        print(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch)} stocks)")
        print(f"{'=' * 60}")

        # Fetch all tickers in batch at once
        print(f"\nFetching batch of {len(batch)} tickers...")
        batch_results = fetch_batch_stock_data(batch)

        # Process results
        for i, stock_info in enumerate(batch, 1):
            ticker = stock_info["ticker"]
            stock_data = batch_results.get(ticker)

            if not stock_data:
                # Create error entry if not in results
                stock_data = create_empty_stock(
                    ticker, stock_info["name"], normalize_ticker(ticker)
                )
                stock_data["error"] = "Not returned from batch fetch"

            print(f"\n[{i}/{len(batch)}] {ticker}...", end=" ")

            # Only update current_data if fetch was successful (no error)
            # This preserves old data if the new fetch fails
            if not stock_data.get("error"):
                current_data[ticker] = stock_data
            else:
                # If there's an error, only update if we don't have old data
                # or if the old data also had an error (to track retry attempts)
                if ticker not in current_data or current_data[ticker].get("error"):
                    current_data[ticker] = stock_data

            # Add to history if successful
            if not stock_data.get("error"):
                add_to_history(ticker, stock_data, history)
                price_str = (
                    f"{stock_data['price']:.2f}"
                    if isinstance(stock_data.get("price"), (int, float))
                    else "N/A"
                )
                last_updated = stock_data.get("last_updated", "N/A")
                if last_updated != "N/A":
                    try:
                        dt = datetime.fromisoformat(last_updated)
                        last_updated = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                print(
                    f"✓ {price_str} {stock_data.get('currency', 'SEK')} (Updated: {last_updated})"
                )
                updated_count += 1
            else:
                print(f"✗ Error: {stock_data['error'][:50]}")

        # Rate limiting between batches
        if batch_num < total_batches - 1:
            time.sleep(0.5)

        # Save after each batch to preserve progress
        print(f"\nSaving progress after batch {batch_num + 1}...")
        save_current_data(current_data)
        save_history(history)
        print(f"✓ Saved progress ({updated_count} stocks updated so far)")

    # Calculate and save Magic Formula scores
    print("\n" + "=" * 60)
    print("Calculating Magic Formula scores...")
    stocks_list = list(current_data.values())
    stocks_with_scores = calculate_magic_formula_scores(stocks_list)
    # Convert back to dict
    for stock in stocks_with_scores:
        ticker = stock.get("ticker")
        if ticker:
            current_data[ticker] = stock
    print(f"✓ Calculated Magic Formula scores")

    # Save data
    print("\n" + "=" * 60)
    print("Saving data...")
    save_current_data(current_data)
    save_history(history)
    print(f"✓ Saved current data ({len(current_data)} stocks)")
    # Count history entries (handle both old list format and new dict format)
    total_entries = 0
    for entries in history.values():
        if isinstance(entries, dict):
            total_entries += len(entries)
        elif isinstance(entries, list):
            total_entries += len(entries)
    print(f"✓ Saved history ({total_entries} entries)")

    print(f"\n✓ Updated {updated_count} stocks")
    print(f"✓ Total stocks in database: {len(current_data)}")
    print("\nDone! Run 'python3 generate_html.py' to update stocks.html")


if __name__ == "__main__":
    main()
