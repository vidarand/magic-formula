#!/usr/bin/env python3
"""
Calculate Magic Formula scores with multiple variants.

This module calculates Magic Formula scores with different exclusion criteria:
- All eligible stocks (no exclusions except errors)
- Excluding financial/investment companies
- Different market cap thresholds (100M, 500M, 1B, 5B SEK)

The main score (magic_formula_score) excludes financial/investment companies by default.
Additional scores are calculated for different market cap filters.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime

# File paths
CURRENT_DATA = Path("data/current_stocks.json")


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


def calculate_magic_formula_for_stocks(
    stocks: List[Dict],
    exclude_filter: Optional[Callable[[Dict], bool]] = None,
) -> List[Dict]:
    """
    Calculate Magic Formula scores for a list of stocks.

    Args:
        stocks: List of stock dictionaries
        exclude_filter: Optional function that returns True if a stock should be excluded from ranking

    Returns:
        List of stocks with magic_formula_score and magic_formula_reason added
    """
    valid_stocks = []

    for stock in stocks:
        # Ensure reason field exists
        if (
            "magic_formula_reason" not in stock
            or stock.get("magic_formula_reason") is None
        ):
            stock["magic_formula_reason"] = "Ej beräknad"

        # Apply exclusion filter if provided
        if exclude_filter and exclude_filter(stock):
            # Stock is excluded from ranking, but we still calculate the score
            # The exclusion will be handled by the caller
            pass

        if stock.get("error"):
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Error fetching data"
            continue

        # Only calculate Magic Formula for stocks in SEK
        currency = stock.get("currency", "N/A")
        if currency != "SEK" and currency != "N/A":
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = (
                f"Currency is {currency}, only SEK stocks are calculated"
            )
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
        item["stock"]["magic_formula_reason"] = "Beräknad"

    return stocks


def is_financial_company(stock: Dict) -> bool:
    """Check if a stock is a financial/investment company that should be excluded."""
    if stock.get("default_excluded") or stock.get("exclusion_reason"):
        return True

    sector = (stock.get("sector", "") or "").lower()
    industry = (stock.get("industry", "") or "").lower()
    name = (stock.get("name", "") or "").lower()

    if "financial" in sector or "financial services" in sector:
        return True
    if "real estate" in sector or "real estate" in industry:
        return True
    if any(
        keyword in name for keyword in ["investment", "investor", "holding", "equity"]
    ):
        return True
    if "investment" in industry or "asset management" in industry.lower():
        return True

    return False


def meets_market_cap_threshold(stock: Dict, min_market_cap: float) -> bool:
    """Check if stock meets minimum market cap threshold."""
    market_cap = stock.get("market_cap", "N/A")
    if market_cap == "N/A" or market_cap is None:
        return False
    if not isinstance(market_cap, (int, float)):
        return False
    return market_cap >= min_market_cap


def calculate_all_score_variants(stocks: List[Dict]) -> List[Dict]:
    """
    Calculate all Magic Formula score variants for stocks.

    Adds the following score fields:
    - magic_formula_score: Default (excludes financial/investment companies)
    - magic_formula_score_all: All eligible stocks (no exclusions except errors)
    - magic_formula_score_100m: Market cap >= 100M SEK
    - magic_formula_score_500m: Market cap >= 500M SEK
    - magic_formula_score_1b: Market cap >= 1B SEK
    - magic_formula_score_5b: Market cap >= 5B SEK

    Returns:
        List of stocks with all score variants added
    """
    # Convert to list if dict
    if isinstance(stocks, dict):
        stocks = list(stocks.values())

    # Initialize all score fields to "N/A"
    for stock in stocks:
        stock["magic_formula_score"] = "N/A"
        stock["magic_formula_score_all"] = "N/A"
        stock["magic_formula_score_100m"] = "N/A"
        stock["magic_formula_score_500m"] = "N/A"
        stock["magic_formula_score_1b"] = "N/A"
        stock["magic_formula_score_5b"] = "N/A"

    # Create a mapping of ticker -> stock for quick lookup
    ticker_map = {s.get("ticker"): s for s in stocks if s.get("ticker")}

    # 1. Calculate for ALL eligible stocks (no exclusions except errors)
    print("  Calculating magic_formula_score_all (all eligible stocks)...")
    stocks_all = calculate_magic_formula_for_stocks([s.copy() for s in stocks])
    # Copy scores to magic_formula_score_all
    for stock in stocks_all:
        ticker = stock.get("ticker")
        if ticker and ticker in ticker_map:
            ticker_map[ticker]["magic_formula_score_all"] = stock.get(
                "magic_formula_score", "N/A"
            )

    # 2. Calculate default score (excludes financial/investment companies)
    print(
        "  Calculating magic_formula_score (excludes financial/investment companies)..."
    )
    stocks_default = [s.copy() for s in stocks if not is_financial_company(s)]
    stocks_default = calculate_magic_formula_for_stocks(stocks_default)
    # Copy scores to magic_formula_score
    for stock in stocks_default:
        ticker = stock.get("ticker")
        if ticker and ticker in ticker_map:
            ticker_map[ticker]["magic_formula_score"] = stock.get(
                "magic_formula_score", "N/A"
            )

    # 3. Calculate for different market cap thresholds
    market_cap_thresholds = [
        (100_000_000, "magic_formula_score_100m", "100M SEK"),
        (500_000_000, "magic_formula_score_500m", "500M SEK"),
        (1_000_000_000, "magic_formula_score_1b", "1B SEK"),
        (5_000_000_000, "magic_formula_score_5b", "5B SEK"),
    ]

    for min_cap, score_field, label in market_cap_thresholds:
        print(f"  Calculating {score_field} (market cap >= {label})...")
        # Filter: exclude financial companies AND meet market cap threshold
        filtered_stocks = [
            s.copy()
            for s in stocks
            if not is_financial_company(s) and meets_market_cap_threshold(s, min_cap)
        ]
        filtered_stocks = calculate_magic_formula_for_stocks(filtered_stocks)
        # Copy scores
        for stock in filtered_stocks:
            ticker = stock.get("ticker")
            if ticker and ticker in ticker_map:
                ticker_map[ticker][score_field] = stock.get(
                    "magic_formula_score", "N/A"
                )

    return stocks


def recalculate_all_scores():
    """
    Recalculate all Magic Formula scores for all stocks in current_stocks.json.
    This is the main entry point for recalculation.
    """
    print("=" * 60)
    print("Recalculating Magic Formula Scores")
    print("=" * 60)

    # Load current data
    print("\nLoading stock data...")
    current_data = load_current_data()
    if not current_data:
        print("  No stock data found!")
        return

    print(f"  Loaded {len(current_data)} stocks")

    # Convert to list
    stocks_list = list(current_data.values())

    # Calculate all score variants
    print("\nCalculating Magic Formula score variants...")
    stocks_with_scores = calculate_all_score_variants(stocks_list)

    # Update current_data dict
    for stock in stocks_with_scores:
        ticker = stock.get("ticker")
        if ticker:
            # Ensure all score fields exist
            if "magic_formula_score" not in stock:
                stock["magic_formula_score"] = "N/A"
            if "magic_formula_score_all" not in stock:
                stock["magic_formula_score_all"] = "N/A"
            if "magic_formula_score_100m" not in stock:
                stock["magic_formula_score_100m"] = "N/A"
            if "magic_formula_score_500m" not in stock:
                stock["magic_formula_score_500m"] = "N/A"
            if "magic_formula_score_1b" not in stock:
                stock["magic_formula_score_1b"] = "N/A"
            if "magic_formula_score_5b" not in stock:
                stock["magic_formula_score_5b"] = "N/A"

            # Ensure reason is always set
            if (
                "magic_formula_reason" not in stock
                or stock.get("magic_formula_reason") is None
            ):
                if stock.get("magic_formula_score") == "N/A":
                    stock["magic_formula_reason"] = "Ej beräknad"
                else:
                    stock["magic_formula_reason"] = "Beräknad"

            current_data[ticker] = stock

    # Save updated data
    print("\nSaving updated scores...")
    save_current_data(current_data)
    print(f"✓ Saved scores for {len(current_data)} stocks")

    # Print summary
    print("\n" + "=" * 60)
    print("Score Summary:")
    print("=" * 60)

    score_fields = [
        "magic_formula_score",
        "magic_formula_score_all",
        "magic_formula_score_100m",
        "magic_formula_score_500m",
        "magic_formula_score_1b",
        "magic_formula_score_5b",
    ]

    for field in score_fields:
        valid_scores = sum(
            1
            for s in stocks_with_scores
            if s.get(field) != "N/A" and s.get(field) is not None
        )
        print(f"  {field}: {valid_scores} stocks with valid scores")

    print("\n✓ Recalculation complete!")


if __name__ == "__main__":
    recalculate_all_scores()
