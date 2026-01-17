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
    Excluded companies (financial/investment) are NOT included in the ranking calculation.

    Args:
        stocks: List of stock dictionaries
        exclude_filter: Optional function that returns True if a stock should be excluded from ranking

    Returns:
        List of stocks with magic_formula_score and magic_formula_reason added.
        Excluded stocks will have "N/A" scores and are not part of the ranking pool.
    """
    # First, separate excluded stocks from eligible stocks
    eligible_stocks = []
    excluded_stocks = []

    for stock in stocks:
        # Ensure reason field exists
        if (
            "magic_formula_reason" not in stock
            or stock.get("magic_formula_reason") is None
        ):
            stock["magic_formula_reason"] = "Ej beräknad"

        # Check if stock should be excluded
        is_excluded = False
        if exclude_filter and exclude_filter(stock):
            is_excluded = True
        elif is_financial_company(stock):
            is_excluded = True

        if is_excluded:
            # Set score to N/A and skip calculation - these are NOT in ranking pool
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Exkluderad från ranking"
            excluded_stocks.append(stock)
        else:
            eligible_stocks.append(stock)

    # Only calculate Magic Formula scores for eligible stocks (excluded ones are NOT in ranking)
    valid_stocks = []

    for stock in eligible_stocks:
        # Ensure reason field exists
        if (
            "magic_formula_reason" not in stock
            or stock.get("magic_formula_reason") is None
        ):
            stock["magic_formula_reason"] = "Ej beräknad"

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

    # Calculate combined score (lower is better) and save ranks
    for item in valid_stocks:
        magic_score = item["ey_rank"] + item["roc_rank"]
        item["stock"]["magic_formula_score"] = magic_score
        item["stock"]["ey_rank"] = item["ey_rank"]
        item["stock"]["roc_rank"] = item["roc_rank"]
        item["stock"]["magic_formula_reason"] = "Beräknad"

    # Return all stocks (eligible with scores + excluded with N/A)
    return eligible_stocks + excluded_stocks


def is_financial_company(stock: Dict) -> bool:
    """Check if a stock is a financial/investment company that should be excluded."""
    if stock.get("default_excluded") or stock.get("exclusion_reason"):
        return True

    sector = (stock.get("sector", "") or "").lower()
    industry = (stock.get("industry", "") or "").lower()
    name = (stock.get("name", "") or "").lower()
    ticker = (stock.get("ticker", "") or "").lower()

    if "financial" in sector or "financial services" in sector:
        return True
    if "real estate" in sector or "real estate" in industry:
        return True
    if any(
        keyword in name
        for keyword in [
            "investment",
            "investor",
            "holding",
            "equity",
            "ratos",
            "lundberg",
        ]
    ):
        return True
    if "ratos" in ticker or "lund" in ticker:
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
    - magic_formula_score_100m: Market cap >= 100M SEK
    - magic_formula_score_500m: Market cap >= 500M SEK
    - magic_formula_score_1b: Market cap >= 1B SEK
    - magic_formula_score_5b: Market cap >= 5B SEK

    Returns:
        List of stocks with score variants added.
        B shares are already filtered out at the source.
    """
    # Convert to list if dict
    if isinstance(stocks, dict):
        stocks = list(stocks.values())

    # B shares are already filtered out at the source (in fetch_stocks.py)
    # So we can use all stocks directly for calculation
    original_stocks = stocks
    # Create ticker map for updating scores back to original stocks
    original_ticker_map = {
        s.get("ticker"): s for s in original_stocks if s.get("ticker")
    }

    # Initialize all score fields to "N/A" for ALL stocks
    for stock in original_stocks:
        stock["magic_formula_score"] = "N/A"
        stock["magic_formula_score_100m"] = "N/A"
        stock["magic_formula_score_500m"] = "N/A"
        stock["magic_formula_score_1b"] = "N/A"
        stock["magic_formula_score_5b"] = "N/A"
        # Initialize rank fields
        stock["ey_rank"] = "N/A"
        stock["roc_rank"] = "N/A"
        stock["ey_rank_100m"] = "N/A"
        stock["roc_rank_100m"] = "N/A"
        stock["ey_rank_500m"] = "N/A"
        stock["roc_rank_500m"] = "N/A"
        stock["ey_rank_1b"] = "N/A"
        stock["roc_rank_1b"] = "N/A"
        stock["ey_rank_5b"] = "N/A"
        stock["roc_rank_5b"] = "N/A"

    # 1. Calculate default score (excludes financial/investment companies)
    print(
        "  Calculating magic_formula_score (excludes financial/investment companies)..."
    )
    stocks_default = [s.copy() for s in stocks if not is_financial_company(s)]
    stocks_default = calculate_magic_formula_for_stocks(stocks_default)
    # Copy scores and ranks to magic_formula_score in original stocks
    for stock in stocks_default:
        ticker = stock.get("ticker")
        if ticker and ticker in original_ticker_map:
            original_ticker_map[ticker]["magic_formula_score"] = stock.get(
                "magic_formula_score", "N/A"
            )
            original_ticker_map[ticker]["ey_rank"] = stock.get("ey_rank", "N/A")
            original_ticker_map[ticker]["roc_rank"] = stock.get("roc_rank", "N/A")

    # 2. Calculate for different market cap thresholds
    market_cap_thresholds = [
        (
            100_000_000,
            "magic_formula_score_100m",
            "ey_rank_100m",
            "roc_rank_100m",
            "100M SEK",
        ),
        (
            500_000_000,
            "magic_formula_score_500m",
            "ey_rank_500m",
            "roc_rank_500m",
            "500M SEK",
        ),
        (
            1_000_000_000,
            "magic_formula_score_1b",
            "ey_rank_1b",
            "roc_rank_1b",
            "1B SEK",
        ),
        (
            5_000_000_000,
            "magic_formula_score_5b",
            "ey_rank_5b",
            "roc_rank_5b",
            "5B SEK",
        ),
    ]

    for min_cap, score_field, ey_field, roc_field, label in market_cap_thresholds:
        print(f"  Calculating {score_field} (market cap >= {label})...")
        # Filter: exclude financial companies AND meet market cap threshold
        variant_filtered = [
            s.copy()
            for s in stocks
            if not is_financial_company(s) and meets_market_cap_threshold(s, min_cap)
        ]
        variant_filtered = calculate_magic_formula_for_stocks(variant_filtered)
        # Copy scores and ranks to original stocks
        for stock in variant_filtered:
            ticker = stock.get("ticker")
            if ticker and ticker in original_ticker_map:
                original_ticker_map[ticker][score_field] = stock.get(
                    "magic_formula_score", "N/A"
                )
                original_ticker_map[ticker][ey_field] = stock.get("ey_rank", "N/A")
                original_ticker_map[ticker][roc_field] = stock.get("roc_rank", "N/A")

    # Return original stocks list (with all A/B shares, but only selected ones have scores)
    return original_stocks


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

    # Calculate all score variants (this filters duplicates for calculation but returns all stocks)
    print("\nCalculating Magic Formula score variants...")
    stocks_with_scores = calculate_all_score_variants(stocks_list)

    # Update current_data dict with all stocks (including duplicates, but only selected ones have scores)
    for stock in stocks_with_scores:
        ticker = stock.get("ticker")
        if ticker:
            # Ensure all score fields exist
            if "magic_formula_score" not in stock:
                stock["magic_formula_score"] = "N/A"
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
