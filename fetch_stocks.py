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
    """Load ticker list from JSON file, filtering out B shares that have corresponding A shares."""
    if not STOCKS_JSON.exists():
        print(f"Error: {STOCKS_JSON} not found!")
        return []

    with open(STOCKS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    # First pass: build a set of all A share tickers (without the .A suffix for comparison)
    a_share_base_tickers = set()
    for stock_info in data:
        ticker = stock_info.get("ticker", "")
        # Extract base ticker (e.g., "INVE" from "INVE.A")
        if ".A" in ticker.upper():
            base_ticker = ticker.upper().split(".A")[0]
            a_share_base_tickers.add(base_ticker)
    
    # Second pass: filter B shares - only exclude B shares that have a corresponding A share
    filtered_data = []
    b_shares_removed = 0
    b_shares_included = 0
    
    for stock_info in data:
        ticker = stock_info.get("ticker", "")
        
        # Check if this is a B share
        if ".B" in ticker.upper():
            # Extract base ticker (e.g., "INVE" from "INVE.B")
            base_ticker = ticker.upper().split(".B")[0]
            
            # If there's a corresponding A share, exclude this B share
            if base_ticker in a_share_base_tickers:
                b_shares_removed += 1
                continue
            else:
                # No A share exists, include this B share
                filtered_data.append(stock_info)
                b_shares_included += 1
        else:
            # Not a B share, include it
            filtered_data.append(stock_info)

    if b_shares_removed > 0:
        print(f"  Filtered out {b_shares_removed} B shares (have corresponding A shares)")
    if b_shares_included > 0:
        print(f"  Included {b_shares_included} B shares (no corresponding A shares)")

    return filtered_data


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


def remove_b_shares(current_data: Dict) -> Dict:
    """
    Remove B shares from database that have corresponding A shares.
    Keep B shares that don't have A shares (e.g., Betsson only has B shares).
    """
    # First, find all A share base tickers
    a_share_base_tickers = set()
    for ticker in current_data.keys():
        if ".A" in ticker.upper():
            base_ticker = ticker.upper().split(".A")[0]
            a_share_base_tickers.add(base_ticker)
    
    # Find and remove B shares that have corresponding A shares
    b_shares_to_remove = []
    for ticker in current_data.keys():
        if ".B" in ticker.upper():
            base_ticker = ticker.upper().split(".B")[0]
            # If there's a corresponding A share, remove this B share
            if base_ticker in a_share_base_tickers:
                b_shares_to_remove.append(ticker)

    # Remove B shares
    removed_count = 0
    for ticker in b_shares_to_remove:
        if ticker in current_data:
            del current_data[ticker]
            removed_count += 1
        # Also remove from history if it exists
        # (history cleanup will be done separately)

    if removed_count > 0:
        print(f"  Removed {removed_count} B shares from database")

    return current_data


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
    Only adds stocks that have a valid Magic Formula score (not "N/A").
    """
    # Only add to history if stock has a valid Magic Formula score
    magic_score = stock_data.get("magic_formula_score", "N/A")
    if magic_score == "N/A" or magic_score is None:
        return  # Skip stocks without Magic Formula scores
    
    # Check if it's a valid number (not "N/A" string)
    try:
        float(magic_score)
    except (ValueError, TypeError):
        return  # Skip if not a valid number
    
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
        "ebit_period": stock_data.get("ebit_period", "N/A"),  # Fiscal period for EBIT
        "quarterly_ebit": stock_data.get("quarterly_ebit", "N/A"),  # Last 4 quarters of EBIT
        "enterprise_value": stock_data.get("enterprise_value"),
        "total_assets": stock_data.get("total_assets"),
        "current_liabilities": stock_data.get("current_liabilities"),
        "current_assets": stock_data.get("current_assets"),
        "net_fixed_assets": stock_data.get("net_fixed_assets"),
        "balance_sheet_period": stock_data.get("balance_sheet_period", "N/A"),  # Fiscal period for balance sheet
        "quarterly_balance_sheet": stock_data.get("quarterly_balance_sheet", "N/A"),  # Last 4 quarters of balance sheet
        "magic_formula_score": stock_data.get("magic_formula_score"),
        "magic_formula_score_100m": stock_data.get("magic_formula_score_100m"),
        "magic_formula_score_500m": stock_data.get("magic_formula_score_500m"),
        "magic_formula_score_1b": stock_data.get("magic_formula_score_1b"),
        "magic_formula_score_5b": stock_data.get("magic_formula_score_5b"),
        "ey_rank": stock_data.get("ey_rank"),
        "roc_rank": stock_data.get("roc_rank"),
        "ey_rank_100m": stock_data.get("ey_rank_100m"),
        "roc_rank_100m": stock_data.get("roc_rank_100m"),
        "ey_rank_500m": stock_data.get("ey_rank_500m"),
        "roc_rank_500m": stock_data.get("roc_rank_500m"),
        "ey_rank_1b": stock_data.get("ey_rank_1b"),
        "roc_rank_1b": stock_data.get("roc_rank_1b"),
        "ey_rank_5b": stock_data.get("ey_rank_5b"),
        "roc_rank_5b": stock_data.get("roc_rank_5b"),
        "magic_formula_ebit_periods": stock_data.get("magic_formula_ebit_periods", "N/A"),  # Periods used for EBIT calculation
        "magic_formula_balance_sheet_period": stock_data.get("magic_formula_balance_sheet_period", "N/A"),  # Period used for balance sheet
        "magic_formula_uses_ttm": stock_data.get("magic_formula_uses_ttm", False),  # Whether TTM was used
        "sector": stock_data.get("sector"),  # Needed for exclusion logic
        "industry": stock_data.get("industry"),  # Needed for exclusion logic
        "exclusion_reason": stock_data.get("exclusion_reason"),  # Needed for filtering
    }

    # Store by date (overwrites if same day)
    history[ticker][date_str] = history_entry


def _normalize_dividend_yield(dividend_yield) -> Union[float, str]:
    """
    Normalize dividend yield to always be a decimal (0.0255 for 2.55%).
    yfinance sometimes returns it as a decimal (0.0255) and sometimes as a percentage (2.55).
    """
    if dividend_yield == "N/A" or dividend_yield is None:
        return "N/A"
    
    try:
        dy = float(dividend_yield)
        # If value is > 1, it's likely already in percentage form, so divide by 100
        # If value is <= 1, it's likely already in decimal form
        if dy > 1.0:
            return dy / 100.0
        return dy
    except (ValueError, TypeError):
        return "N/A"


def update_history_with_calculated_scores(current_data: Dict, history: Dict):
    """
    Add or update history entries with calculated Magic Formula scores.
    Only adds stocks that have a valid Magic Formula score (not "N/A").
    This is called after scores are calculated to ensure history has the correct values.
    """
    today = datetime.now().date().isoformat()
    updated_count = 0
    added_count = 0
    
    for ticker, stock_data in current_data.items():
        # Only add/update stocks with valid Magic Formula scores
        magic_score = stock_data.get("magic_formula_score", "N/A")
        if magic_score == "N/A" or magic_score is None:
            continue  # Skip stocks without Magic Formula scores
        
        # Check if it's a valid number (not "N/A" string)
        try:
            float(magic_score)
        except (ValueError, TypeError):
            continue  # Skip if not a valid number
        
        # Initialize history entry for this ticker if needed
        if ticker not in history:
            history[ticker] = {}
        
        # Add or update today's entry
        if today not in history[ticker]:
            # Create new history entry using add_to_history function
            add_to_history(ticker, stock_data, history)
            added_count += 1
        else:
            # Update existing entry with calculated scores
            history[ticker][today]["magic_formula_score"] = stock_data.get("magic_formula_score", "N/A")
            history[ticker][today]["magic_formula_score_100m"] = stock_data.get("magic_formula_score_100m", "N/A")
            history[ticker][today]["magic_formula_score_500m"] = stock_data.get("magic_formula_score_500m", "N/A")
            history[ticker][today]["magic_formula_score_1b"] = stock_data.get("magic_formula_score_1b", "N/A")
            history[ticker][today]["magic_formula_score_5b"] = stock_data.get("magic_formula_score_5b", "N/A")
            history[ticker][today]["ey_rank"] = stock_data.get("ey_rank", "N/A")
            history[ticker][today]["roc_rank"] = stock_data.get("roc_rank", "N/A")
            history[ticker][today]["ey_rank_100m"] = stock_data.get("ey_rank_100m", "N/A")
            history[ticker][today]["roc_rank_100m"] = stock_data.get("roc_rank_100m", "N/A")
            history[ticker][today]["ey_rank_500m"] = stock_data.get("ey_rank_500m", "N/A")
            history[ticker][today]["roc_rank_500m"] = stock_data.get("roc_rank_500m", "N/A")
            history[ticker][today]["ey_rank_1b"] = stock_data.get("ey_rank_1b", "N/A")
            history[ticker][today]["roc_rank_1b"] = stock_data.get("roc_rank_1b", "N/A")
            history[ticker][today]["ey_rank_5b"] = stock_data.get("ey_rank_5b", "N/A")
            history[ticker][today]["roc_rank_5b"] = stock_data.get("roc_rank_5b", "N/A")
            history[ticker][today]["magic_formula_ebit_periods"] = stock_data.get("magic_formula_ebit_periods", "N/A")
            history[ticker][today]["magic_formula_balance_sheet_period"] = stock_data.get("magic_formula_balance_sheet_period", "N/A")
            history[ticker][today]["magic_formula_uses_ttm"] = stock_data.get("magic_formula_uses_ttm", False)
            updated_count += 1
    
    if added_count > 0:
        print(f"  Added {added_count} new stocks to history (with valid Magic Formula scores)")
    if updated_count > 0:
        print(f"  Updated {updated_count} existing history entries with calculated scores")
    
    return updated_count + added_count


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
        # Note: yfinance.financials returns ANNUAL income statements (not quarterly)
        # The columns are dates (most recent first), and .iloc[0] gets the most recent annual period
        # This is typically the last completed fiscal year from the company's annual report (10-K equivalent)
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        
        # Also get quarterly data for the last 4 quarters
        quarterly_financials = stock.quarterly_financials
        quarterly_balance_sheet = stock.quarterly_balance_sheet

        # Get EBIT - try multiple possible index names
        # EBIT comes from the income statement (profit & loss statement)
        # Source: Most recent annual income statement (typically last completed fiscal year)
        ebit = "N/A"
        ebit_period = "N/A"  # Track which fiscal period EBIT is from
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
                        # .iloc[0] gets the first column = most recent annual period
                        ebit_value = financials.loc[ebit_name].iloc[0]
                        if pd.notna(ebit_value) and isinstance(
                            ebit_value, (int, float)
                        ):
                            ebit = float(ebit_value)
                            # Extract the period (date) from the column
                            period_col = financials.columns[0]
                            if isinstance(period_col, (pd.Timestamp, datetime)):
                                ebit_period = period_col.strftime("%Y-%m-%d")
                            elif isinstance(period_col, str):
                                ebit_period = period_col
                            else:
                                ebit_period = str(period_col)
                            break
                    except:
                        continue

        # If EBIT still not found, try from info dict
        if ebit == "N/A":
            ebit = info.get("ebit", info.get("operatingIncome", "N/A"))
            if ebit != "N/A" and isinstance(ebit, (int, float)):
                ebit = float(ebit)
                # Try to get period from info if available
                ebit_period = info.get("mostRecentQuarter", info.get("fiscalYearEnd", "N/A"))
                if ebit_period != "N/A":
                    # Format the period if it's a date
                    try:
                        if isinstance(ebit_period, (int, float)):
                            # Might be a timestamp
                            ebit_period = datetime.fromtimestamp(ebit_period).strftime("%Y-%m-%d")
                        elif isinstance(ebit_period, str) and len(ebit_period) > 4:
                            # Try to parse and format
                            ebit_period = ebit_period[:10] if len(ebit_period) >= 10 else ebit_period
                    except:
                        pass
            else:
                ebit = "N/A"

        # Extract quarterly EBIT data (last 4 quarters)
        quarterly_ebit_data = []  # List of {period: date, ebit: value} dicts
        if not quarterly_financials.empty:
            for ebit_name in ebit_names:
                if ebit_name in quarterly_financials.index:
                    try:
                        # Get up to 4 most recent quarters (columns are most recent first)
                        for i in range(min(4, len(quarterly_financials.columns))):
                            period_col = quarterly_financials.columns[i]
                            ebit_val = quarterly_financials.loc[ebit_name].iloc[i]
                            
                            if pd.notna(ebit_val) and isinstance(ebit_val, (int, float)):
                                # Format the period
                                if isinstance(period_col, (pd.Timestamp, datetime)):
                                    period_str = period_col.strftime("%Y-%m-%d")
                                elif isinstance(period_col, str):
                                    period_str = period_col
                                else:
                                    period_str = str(period_col)
                                
                                quarterly_ebit_data.append({
                                    "period": period_str,
                                    "ebit": float(ebit_val)
                                })
                        break  # Found the EBIT field, no need to try other names
                    except:
                        continue

        # Extract quarterly balance sheet data (last 4 quarters) for Magic Formula
        quarterly_balance_sheet_data = []  # List of {period, current_assets, current_liabilities, net_fixed_assets} dicts
        if not quarterly_balance_sheet.empty:
            # Get up to 4 most recent quarters (columns are most recent first)
            # Note: yfinance may not always have the absolute latest quarter immediately after reporting
            num_quarters_to_get = min(4, len(quarterly_balance_sheet.columns))
            for i in range(num_quarters_to_get):
                period_col = quarterly_balance_sheet.columns[i]
                
                # Format the period
                if isinstance(period_col, (pd.Timestamp, datetime)):
                    period_str = period_col.strftime("%Y-%m-%d")
                elif isinstance(period_col, str):
                    period_str = period_col
                else:
                    period_str = str(period_col)
                
                quarter_data = {"period": period_str}
                
                # Extract Current Assets
                current_asset_names = [
                    "Total Current Assets",
                    "Current Assets",
                    "CurrentAssets",
                    "TotalCurrentAssets",
                ]
                for asset_name in current_asset_names:
                    if asset_name in quarterly_balance_sheet.index:
                        try:
                            # Access by column name (period_col) instead of iloc for clarity
                            val = quarterly_balance_sheet.loc[asset_name, period_col]
                            if pd.notna(val) and isinstance(val, (int, float)):
                                quarter_data["current_assets"] = float(val)
                                break
                        except:
                            continue
                
                # Extract Current Liabilities
                liability_names = [
                    "Total Current Liabilities",
                    "Current Liabilities",
                    "CurrentLiabilities",
                    "TotalCurrentLiabilities",
                ]
                for liability_name in liability_names:
                    if liability_name in quarterly_balance_sheet.index:
                        try:
                            # Access by column name (period_col) instead of iloc for clarity
                            val = quarterly_balance_sheet.loc[liability_name, period_col]
                            if pd.notna(val) and isinstance(val, (int, float)):
                                quarter_data["current_liabilities"] = float(val)
                                break
                        except:
                            continue
                
                # Extract Net Fixed Assets / PP&E
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
                    if fixed_name in quarterly_balance_sheet.index:
                        try:
                            # Access by column name (period_col) instead of iloc for clarity
                            val = quarterly_balance_sheet.loc[fixed_name, period_col]
                            if pd.notna(val) and isinstance(val, (int, float)):
                                quarter_data["net_fixed_assets"] = float(val)
                                break
                        except:
                            continue
                
                # Only add if we got at least one value
                if len(quarter_data) > 1:  # More than just "period"
                    quarterly_balance_sheet_data.append(quarter_data)

        # Get balance sheet data for Magic Formula - try multiple possible index names
        total_assets = "N/A"
        current_assets = "N/A"
        current_liabilities = "N/A"
        net_fixed_assets = "N/A"
        balance_sheet_period = "N/A"  # Track which fiscal period balance sheet data is from

        if not balance_sheet.empty:
            # Extract the period from the first column (most recent)
            try:
                period_col = balance_sheet.columns[0]
                if isinstance(period_col, (pd.Timestamp, datetime)):
                    balance_sheet_period = period_col.strftime("%Y-%m-%d")
                elif isinstance(period_col, str):
                    balance_sheet_period = period_col
                else:
                    balance_sheet_period = str(period_col)
            except:
                balance_sheet_period = "N/A"
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
                "market_cap_category": (
                    get_market_cap_category(market_cap)
                    if isinstance(market_cap, (int, float))
                    else "N/A"
                ),
                "market": info.get("market", "N/A"),
                # Interesting metrics
                "pe_ratio": info.get("trailingPE", info.get("forwardPE", "N/A")),
                "dividend_yield": _normalize_dividend_yield(info.get("dividendYield", "N/A")),
                # Magic Formula required fields (stored as-is, no conversion)
                "enterprise_value": enterprise_value,
                "ebit": ebit_value,
                "ebit_period": ebit_period,  # Fiscal period for EBIT data (YYYY-MM-DD or fiscal year)
                "quarterly_ebit": quarterly_ebit_data if quarterly_ebit_data else "N/A",  # Last 4 quarters of EBIT data
                "total_assets": total_assets_value,
                "current_assets": current_assets_value,
                "current_liabilities": current_liabilities_value,
                "net_fixed_assets": net_fixed_assets_value,
                "balance_sheet_period": balance_sheet_period,  # Fiscal period for balance sheet data (YYYY-MM-DD or fiscal year)
                "quarterly_balance_sheet": quarterly_balance_sheet_data if quarterly_balance_sheet_data else "N/A",  # Last 4 quarters of balance sheet data
                "last_updated": datetime.now().isoformat(),
                "error": None,
                # Magic Formula fields (will be calculated later)
                "magic_formula_score": "N/A",
                "magic_formula_reason": "Ej beräknad",
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
    # Note: yf.Tickers() is lazy - it doesn't fetch until you access .info
    # This can hang if there are network issues, so we'll add progress output
    tickers = None
    try:
        ticker_string = " ".join(normalized_tickers)
        print(
            f"    Creating Tickers object for: {', '.join(normalized_tickers[:3])}{'...' if len(normalized_tickers) > 3 else ''}"
        )
        tickers = yf.Tickers(ticker_string)
        # Access one ticker to trigger initial fetch and check if it works
        if normalized_tickers:
            test_ticker_key = normalized_tickers[0]
            print(f"    Testing fetch with {test_ticker_key}...")
            test_ticker = tickers.tickers.get(test_ticker_key)
            if test_ticker:
                # Try to access info with a quick check
                try:
                    _ = test_ticker.info
                    print(f"    ✓ Batch fetch initialized successfully")
                except Exception as e:
                    print(f"    ⚠️  Initial fetch test failed: {str(e)[:100]}")
                    # Continue anyway - might work for other tickers
    except Exception as e:
        # If batch fetch fails, fall back to individual fetches
        print(f"  ⚠️  Batch fetch initialization failed: {str(e)[:100]}")
        print(f"  Falling back to individual fetches...")
        result = {}
        for stock_info in batch_stocks:
            ticker = stock_info["ticker"]
            name = stock_info["name"]
            stock_data = fetch_single_stock_with_fallback(ticker, name)
            result[ticker] = stock_data
        return result

    # Process each ticker from the batch with timeout protection
    result = {}
    for i, normalized_ticker in enumerate(normalized_tickers, 1):
        original_ticker, name = ticker_map[normalized_ticker]
        print(
            f"    [{i}/{len(normalized_tickers)}] {original_ticker}...",
            end=" ",
            flush=True,
        )
        stock_data = create_empty_stock(original_ticker, name, normalized_ticker)

        try:
            stock = tickers.tickers.get(normalized_ticker)
            # Quick check - if ticker doesn't exist in the batch, try fallback
            if not stock:
                print("(fallback)", flush=True)
                stock_data = fetch_single_stock_with_fallback(original_ticker, name)
                result[original_ticker] = stock_data
                continue

            # Access info with timeout protection using threading
            import threading

            info = None
            info_error = None

            def fetch_info():
                nonlocal info, info_error
                try:
                    info = stock.info
                except Exception as e:
                    info_error = e

            # Start fetch in a thread
            fetch_thread = threading.Thread(target=fetch_info, daemon=True)
            fetch_thread.start()
            fetch_thread.join(timeout=13)  # 13 second timeout per ticker

            if fetch_thread.is_alive():
                # Timeout occurred
                print("(timeout)", flush=True)
                stock_data = fetch_single_stock_with_fallback(original_ticker, name)
                result[original_ticker] = stock_data
                continue

            if info_error:
                raise info_error

            # Check if we got valid data
            if not info or len(info) < 3:
                print("(invalid)", flush=True)
                stock_data = fetch_single_stock_with_fallback(original_ticker, name)
                result[original_ticker] = stock_data
                continue

            # Use the extracted data function
            stock_data = fetch_stock_data_from_ticker(
                original_ticker, name, normalized_ticker, stock
            )
            print("✓", flush=True)

        except Exception as e:
            print(f"✗", flush=True)
            # If batch fetch failed, try fallback alternatives
            stock_data = fetch_single_stock_with_fallback(original_ticker, name)
            if stock_data.get("error"):
                # All alternatives failed, use the error from fallback
                stock_data["error"] = (
                    f"Batch fetch error: {str(e)[:100]}. {stock_data.get('error', '')}"
                )

        result[original_ticker] = stock_data

    return result


def main():
    """Main function."""
    import signal

    # Global flag for graceful shutdown
    shutdown_requested = False

    def signal_handler(sig, frame):
        nonlocal shutdown_requested
        print("\n\n⚠️  Interrupt received. Saving progress and exiting...")
        shutdown_requested = True

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

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
    print("Press Ctrl+C to save progress and exit gracefully")

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

    # Process in smaller batches - yfinance is slow because it makes individual requests
    # Smaller batches help identify problematic tickers faster
    batch_size = 3
    total_batches = (len(to_update) + batch_size - 1) // batch_size

    updated_count = 0
    for batch_num in range(total_batches):
        # Check for shutdown request
        if shutdown_requested:
            print("\n⚠️  Shutdown requested. Saving progress...")
            break

        batch_start = batch_num * batch_size
        batch_end = min(batch_start + batch_size, len(to_update))
        batch = to_update[batch_start:batch_end]

        print(f"\n{'=' * 60}")
        print(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch)} stocks)")
        print(f"{'=' * 60}")

        # Fetch all tickers in batch at once
        print(f"\nFetching batch of {len(batch)} tickers...")
        try:
            batch_results = fetch_batch_stock_data(batch)
        except KeyboardInterrupt:
            print("\n⚠️  Interrupted during batch fetch. Saving progress...")
            shutdown_requested = True
            break

        # Process results and collect fetched stocks for Magic Formula calculation
        fetched_stocks_for_calculation = []
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
                # Add to list for Magic Formula calculation
                fetched_stocks_for_calculation.append(stock_data)
                
                # Note: History is added after Magic Formula calculation
                # Only stocks with valid Magic Formula scores will be added to history
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
                # If there's an error, only update if we don't have old data
                # or if the old data also had an error (to track retry attempts)
                if ticker not in current_data or current_data[ticker].get("error"):
                    current_data[ticker] = stock_data
                    # Still calculate for error stocks (they'll get "Error fetching data" reason)
                    fetched_stocks_for_calculation.append(stock_data)
                print(f"✗ Error: {stock_data['error'][:50]}")

        # Rate limiting between batches (reduced from 0.5s to 0.2s for better performance)
        # 0.2s is usually sufficient to avoid rate limits with batch size of 10
        if batch_num < total_batches - 1:
            time.sleep(0.2)

        # Note: Magic Formula calculation is done in calculate_magic_formula.py
        # We just save the raw data here

        # Save after each batch to preserve progress
        print(f"\nSaving progress after batch {batch_num + 1}...")
        save_current_data(current_data)
        save_history(history)
        print(f"✓ Saved progress ({updated_count} stocks updated so far)")

        # Check for shutdown after each batch
        if shutdown_requested:
            break

    # Save final state if interrupted
    if shutdown_requested:
        print("\n" + "=" * 60)
        print("Saving final state before exit...")
        print("=" * 60)
        save_current_data(current_data)
        save_history(history)
        print(f"✓ Saved {len(current_data)} stocks")
        print(f"✓ Exiting gracefully")
        return

    # Remove all B shares from database
    print("\n" + "=" * 60)
    print("Removing B shares from database...")
    print("=" * 60)
    current_data = remove_b_shares(current_data)
    print(f"✓ Current data after removing B shares: {len(current_data)} stocks")

    # Also remove B shares from history
    b_tickers_in_history = [t for t in history.keys() if ".B" in t.upper()]
    for ticker in b_tickers_in_history:
        del history[ticker]
    if b_tickers_in_history:
        print(f"  Removed {len(b_tickers_in_history)} B shares from history")

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

    # Recalculate all Magic Formula score variants
    print("\n" + "=" * 60)
    print("Recalculating all Magic Formula score variants...")
    print("=" * 60)
    try:
        from calculate_magic_formula import recalculate_all_scores

        recalculate_all_scores()
        
        # Reload current_data to get the calculated scores
        from calculate_magic_formula import load_current_data as load_calculated_data
        
        # Update history with calculated scores
        print("\nUpdating history with calculated scores...")
        current_data_with_scores = load_calculated_data()
        updated_count = update_history_with_calculated_scores(current_data_with_scores, history)
        if updated_count > 0:
            save_history(history)
            print(f"✓ Updated {updated_count} history entries with calculated scores")
    except Exception as e:
        print(f"⚠️  Warning: Failed to recalculate score variants: {e}")
        print("  Continuing with basic Magic Formula scores only...")

    print("\nDone! Run 'python3 generate_html.py' to update stocks.html")


if __name__ == "__main__":
    main()
