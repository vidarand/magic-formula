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


def calculate_ttm_from_quarterly(
    quarterly_data: List[Dict], field_name: str
) -> tuple[float, str]:
    """
    Calculate Trailing Twelve Months (TTM) from quarterly data.

    Args:
        quarterly_data: List of quarterly data dicts with 'period' and field values
        field_name: Name of the field to sum (e.g., 'ebit', 'current_assets')

    Returns:
        Tuple of (TTM value, periods_used string) or (0, "N/A") if insufficient data
    """
    if (
        not quarterly_data
        or quarterly_data == "N/A"
        or not isinstance(quarterly_data, list)
    ):
        return 0, "N/A"

    # Get up to 4 most recent quarters
    quarters_to_use = quarterly_data[:4] if len(quarterly_data) >= 4 else quarterly_data

    if len(quarters_to_use) < 4:
        return 0, "N/A"  # Need 4 quarters for TTM

    ttm_value = 0.0
    periods = []

    for quarter in quarters_to_use:
        if not isinstance(quarter, dict):
            continue
        value = quarter.get(field_name)
        if value is not None and isinstance(value, (int, float)):
            ttm_value += float(value)
            period = quarter.get("period", "Unknown")
            periods.append(period)

    if ttm_value == 0 or len(periods) < 4:
        return 0, "N/A"

    # Create periods string: "2024-Q1 to 2024-Q4" or similar
    periods_str = (
        f"{periods[-1]} to {periods[0]}" if len(periods) == 4 else ", ".join(periods)
    )

    return ttm_value, periods_str


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
            # Set more specific reason based on why it's excluded
            if stock.get("default_excluded") or stock.get("exclusion_reason"):
                exclusion_reason = stock.get("exclusion_reason", "")
                if (
                    "financial" in exclusion_reason.lower()
                    or "investment" in exclusion_reason.lower()
                ):
                    stock["magic_formula_reason"] = "Exkluderad: Finansiellt bolag"
                elif "real estate" in exclusion_reason.lower():
                    stock["magic_formula_reason"] = "Exkluderad: Fastighetsbolag"
                else:
                    stock["magic_formula_reason"] = (
                        f"Exkluderad: {exclusion_reason}"
                        if exclusion_reason
                        else "Exkluderad från ranking"
                    )
            elif is_financial_company(stock):
                # Check sector/industry to give specific reason
                sector = (stock.get("sector", "") or "").lower()
                industry = (stock.get("industry", "") or "").lower()
                name = (stock.get("name", "") or "").lower()
                
                # Check for banks first (most specific)
                bank_keywords = ["bank", "banking", "banker"]
                if any(keyword in sector for keyword in bank_keywords) or \
                   any(keyword in industry for keyword in bank_keywords) or \
                   any(keyword in name for keyword in bank_keywords):
                    stock["magic_formula_reason"] = "Exkluderad: Bank"
                elif "financial" in sector or "financial services" in sector:
                    stock["magic_formula_reason"] = "Exkluderad: Finansiellt bolag"
                elif "real estate" in sector or "real estate" in industry:
                    stock["magic_formula_reason"] = "Exkluderad: Fastighetsbolag"
                elif "investment" in industry or "asset management" in industry:
                    stock["magic_formula_reason"] = "Exkluderad: Investeringsbolag"
                else:
                    stock["magic_formula_reason"] = (
                        "Exkluderad: Finansiellt/investeringsbolag"
                    )
            else:
                stock["magic_formula_reason"] = "Exkluderad från ranking"
            excluded_stocks.append(stock)
        else:
            eligible_stocks.append(stock)

    # Only calculate Magic Formula scores for eligible stocks (excluded ones are NOT in ranking)
    # We check through all stocks and only include those that have ALL required data:
    # - No errors
    # - Currency is SEK
    # - Has Enterprise Value
    # - Has quarterly EBIT data (at least 4 quarters)
    # - Can calculate positive EBIT TTM
    # - Has quarterly balance sheet data
    # - Has all required balance sheet fields (total_assets, current_liabilities, cash, short_term_debt)
    # - Invested capital is positive
    # - Earnings Yield is positive
    # - Return on Capital is positive
    # Only stocks that pass ALL checks are added to valid_stocks and ranked
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
            stock["magic_formula_reason"] = "Fel vid hämtning av data"
            continue

        # Only calculate Magic Formula for stocks in SEK
        currency = stock.get("currency", "N/A")
        if currency != "SEK" and currency != "N/A":
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = (
                f"Valuta är {currency}, endast SEK-aktier beräknas"
            )
            continue

        ev = stock.get("enterprise_value", "N/A")

        # Skip if Enterprise Value is missing (required for both TTM and annual)
        if ev == "N/A" or ev is None:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Saknar Enterprise Value"
            continue

        # ONLY use TTM (Trailing Twelve Months) from quarterly data
        # We require complete quarterly data - no fallback to annual data
        quarterly_ebit = stock.get("quarterly_ebit", "N/A")
        quarterly_balance_sheet = stock.get("quarterly_balance_sheet", "N/A")

        # Check if we have quarterly EBIT data (need at least 4 quarters)
        if (
            quarterly_ebit == "N/A"
            or not isinstance(quarterly_ebit, list)
            or len(quarterly_ebit) < 4
        ):
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = (
                "Saknar kvartalsdata för EBIT (behöver 4 kvartal)"
            )
            continue

        # Calculate EBIT TTM
        ebit_ttm, ebit_periods = calculate_ttm_from_quarterly(quarterly_ebit, "ebit")

        if ebit_ttm <= 0 or ebit_periods == "N/A":
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = (
                "Kunde inte beräkna EBIT TTM från kvartalsdata"
            )
            continue

        # Check if we have quarterly balance sheet data
        if (
            quarterly_balance_sheet == "N/A"
            or not isinstance(quarterly_balance_sheet, list)
            or len(quarterly_balance_sheet) == 0
        ):
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Saknar kvartalsdata för balansräkning"
            continue

        # Get balance sheet data from most recent quarter
        most_recent_q = quarterly_balance_sheet[0]  # First item is most recent
        if not isinstance(most_recent_q, dict):
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Ogiltig kvartalsdata för balansräkning"
            continue

        # Extract balance sheet components (Börsdata's Invested Capital definition)
        # Invested Capital = Total Assets - Cash - Current Liabilities + Short-term Debt
        total_assets_q = most_recent_q.get("total_assets")
        current_liabilities_q = most_recent_q.get("current_liabilities")
        cash_q = most_recent_q.get("cash")  # Cash to subtract from Total Assets
        short_term_debt_q = most_recent_q.get("short_term_debt")  # Short-term debt to add back
        balance_sheet_period_used = most_recent_q.get("period", "N/A")

        # Check if we have all required balance sheet data
        # IMPORTANT: No fallbacks - we need Total Assets, Current Liabilities, Cash, and Short-term Debt
        if (
            total_assets_q is None
            or current_liabilities_q is None
            or cash_q is None
            or short_term_debt_q is None
        ):
            stock["magic_formula_score"] = "N/A"
            if total_assets_q is None:
                stock["magic_formula_reason"] = (
                    "Saknar Total Assets i kvartalsdata"
                )
            elif current_liabilities_q is None:
                stock["magic_formula_reason"] = (
                    "Saknar Current Liabilities i kvartalsdata"
                )
            elif cash_q is None:
                stock["magic_formula_reason"] = (
                    "Saknar Cash i kvartalsdata"
                )
            else:
                stock["magic_formula_reason"] = (
                    "Saknar Short-term Debt i kvartalsdata"
                )
            continue

        # Convert to float values
        try:
            total_assets_val = (
                float(total_assets_q)
                if isinstance(total_assets_q, (int, float))
                else 0
            )
            current_liabilities_val = (
                float(current_liabilities_q)
                if isinstance(current_liabilities_q, (int, float))
                else 0
            )
            cash_val = float(cash_q) if isinstance(cash_q, (int, float)) else 0
            short_term_debt_val = (
                float(short_term_debt_q)
                if isinstance(short_term_debt_q, (int, float))
                else 0
            )
        except (ValueError, TypeError):
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = (
                "Ogiltiga värden i kvartalsdata för balansräkning"
            )
            continue

        # Calculate Invested Capital using Börsdata's definition:
        # Invested Capital = Total Assets - Cash - Current Liabilities + Short-term Debt
        # This includes intangible assets (important for companies like Ericsson)
        invested_capital = total_assets_val - cash_val - current_liabilities_val + short_term_debt_val

        if invested_capital <= 0:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Negativt eller noll investerat kapital"
            continue

        # Use TTM values
        ebit_val = ebit_ttm
        ebit_periods_used = ebit_periods
        use_ttm = True

        try:
            ev_val = float(ev)

            # Calculate Earnings Yield
            ey = ebit_val / ev_val if ev_val > 0 else 0

            # Validate Invested Capital is reasonable relative to EBIT
            # If Invested Capital is less than 5% of EBIT, the ROC calculation becomes unrealistic
            # (e.g., if IC = 60M and EBIT = 1.9B, ROC would be 3167%, which is meaningless)
            min_invested_capital_threshold = abs(ebit_val) * 0.05  # At least 5% of EBIT
            if invested_capital < min_invested_capital_threshold:
                stock["magic_formula_score"] = "N/A"
                stock["magic_formula_reason"] = (
                    f"Investerat kapital för litet för meningsfull beräkning "
                    f"(IC: {invested_capital/1e6:.1f}M, EBIT: {ebit_val/1e6:.1f}M)"
                )
                continue

            # Calculate Return on Capital using: EBIT / Invested Capital
            # where Invested Capital = Total Assets - Cash - Current Liabilities + Short-term Debt
            # (Börsdata's definition, includes intangible assets)
            roc = ebit_val / invested_capital if invested_capital > 0 else 0

            if ey > 0 and roc > 0:
                valid_stocks.append(
                    {
                        "stock": stock,
                        "ey": ey,
                        "roc": roc,
                        "ebit_periods_used": ebit_periods_used,
                        "balance_sheet_period_used": balance_sheet_period_used,
                        "uses_ttm": True,  # Always True now since we only use TTM
                    }
                )
            else:
                stock["magic_formula_score"] = "N/A"
                if ebit_val < 0:
                    stock["magic_formula_reason"] = "Negativ EBIT (förluster)"
                elif ey <= 0:
                    stock["magic_formula_reason"] = "Negativ/noll Earnings Yield"
                elif roc <= 0:
                    stock["magic_formula_reason"] = "Negativ/noll Return on Capital"
                else:
                    stock["magic_formula_reason"] = "Kan inte beräkna"
        except (ValueError, ZeroDivisionError) as e:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = f"Beräkningsfel: {str(e)[:30]}"

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
        # Store percentage values (convert from decimal to percentage)
        item["stock"]["earnings_yield"] = item["ey"] * 100  # Convert to percentage
        item["stock"]["return_on_capital"] = item["roc"] * 100  # Convert to percentage
        item["stock"]["magic_formula_reason"] = "Beräknad"
        # Store which periods were used for the calculation
        item["stock"]["magic_formula_ebit_periods"] = item.get(
            "ebit_periods_used", "N/A"
        )
        item["stock"]["magic_formula_balance_sheet_period"] = item.get(
            "balance_sheet_period_used", "N/A"
        )
        # Always True since we only use TTM from quarterly data
        item["stock"]["magic_formula_uses_ttm"] = True

    # Ensure all stocks have a reason set
    for stock in eligible_stocks + excluded_stocks:
        if (
            "magic_formula_reason" not in stock
            or stock.get("magic_formula_reason") is None
            or stock.get("magic_formula_reason") == ""
        ):
            if stock.get("magic_formula_score") == "N/A":
                stock["magic_formula_reason"] = "Ej beräknad"
            else:
                stock["magic_formula_reason"] = "Beräknad"

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

    # Check for financial sector/industry
    if "financial" in sector or "financial services" in sector:
        return True
    if "real estate" in sector or "real estate" in industry:
        return True
    
    # Check for banks specifically (banks have balance sheets that don't work with Magic Formula)
    bank_keywords = ["bank", "banking", "banker"]
    if any(keyword in sector for keyword in bank_keywords):
        return True
    if any(keyword in industry for keyword in bank_keywords):
        return True
    if any(keyword in name for keyword in bank_keywords):
        return True
    
    # Specific bank names/tickers to exclude
    bank_names = [
        "tf bank",
        "resurs",
        "nordea",
        "swedbank",
        "seb",
        "handelsbanken",
        "shb",
        "svenska handelsbanken",
        "skandinaviska enskilda banken",
    ]
    if any(bank_name in name for bank_name in bank_names):
        return True
    
    bank_tickers = [
        "tfbank",
        "tf-bank",
        "resurs",
        "nda",
        "swed",
        "seb",
        "shb",
        "handl",
    ]
    if any(bank_ticker in ticker for bank_ticker in bank_tickers):
        return True
    
    # Check for investment companies
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
        All stocks are included, including B shares.
    """
    # Convert to list if dict
    if isinstance(stocks, dict):
        stocks = list(stocks.values())

    # All stocks are included, including B shares
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
        stock["earnings_yield"] = "N/A"
        stock["return_on_capital"] = "N/A"
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
            original_ticker_map[ticker]["earnings_yield"] = stock.get(
                "earnings_yield", "N/A"
            )
            original_ticker_map[ticker]["return_on_capital"] = stock.get(
                "return_on_capital", "N/A"
            )
            # Copy the reason if it was set during calculation (overwrites default "Ej beräknad")
            if "magic_formula_reason" in stock:
                original_ticker_map[ticker]["magic_formula_reason"] = stock.get(
                    "magic_formula_reason"
                )
            # Copy period information (only if stock was actually calculated)
            if stock.get("magic_formula_score") != "N/A" and isinstance(
                stock.get("magic_formula_score"), (int, float)
            ):
                original_ticker_map[ticker]["magic_formula_ebit_periods"] = stock.get(
                    "magic_formula_ebit_periods", "N/A"
                )
                original_ticker_map[ticker]["magic_formula_balance_sheet_period"] = (
                    stock.get("magic_formula_balance_sheet_period", "N/A")
                )
                # Always True since we only use TTM from quarterly data
                original_ticker_map[ticker]["magic_formula_uses_ttm"] = True
            else:
                # For non-calculated stocks, set to N/A or don't set at all
                original_ticker_map[ticker]["magic_formula_ebit_periods"] = "N/A"
                original_ticker_map[ticker][
                    "magic_formula_balance_sheet_period"
                ] = "N/A"
                # Don't set magic_formula_uses_ttm for non-calculated stocks (leave as undefined/null)
                if "magic_formula_uses_ttm" in original_ticker_map[ticker]:
                    del original_ticker_map[ticker]["magic_formula_uses_ttm"]

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
                # Copy period information if stock was calculated (periods are the same for all variants)
                if stock.get("magic_formula_score") != "N/A" and isinstance(
                    stock.get("magic_formula_score"), (int, float)
                ):
                    # Always copy periods if they exist (they should exist for any calculated stock)
                    ebit_periods = stock.get("magic_formula_ebit_periods")
                    balance_sheet_period = stock.get(
                        "magic_formula_balance_sheet_period"
                    )
                    if ebit_periods and ebit_periods != "N/A":
                        original_ticker_map[ticker][
                            "magic_formula_ebit_periods"
                        ] = ebit_periods
                    if balance_sheet_period and balance_sheet_period != "N/A":
                        original_ticker_map[ticker][
                            "magic_formula_balance_sheet_period"
                        ] = balance_sheet_period
                # Note: reason is only copied for default score, not variants

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

            # Validate consistency: if ey_rank or roc_rank is N/A, score must also be N/A
            # Check default score
            ey_rank = stock.get("ey_rank", "N/A")
            roc_rank = stock.get("roc_rank", "N/A")
            if (
                ey_rank == "N/A"
                or roc_rank == "N/A"
                or ey_rank is None
                or roc_rank is None
            ):
                stock["magic_formula_score"] = "N/A"

            # Check variant scores
            score_variants = [
                ("magic_formula_score_100m", "ey_rank_100m", "roc_rank_100m"),
                ("magic_formula_score_500m", "ey_rank_500m", "roc_rank_500m"),
                ("magic_formula_score_1b", "ey_rank_1b", "roc_rank_1b"),
                ("magic_formula_score_5b", "ey_rank_5b", "roc_rank_5b"),
            ]
            for score_field, ey_field, roc_field in score_variants:
                ey_val = stock.get(ey_field, "N/A")
                roc_val = stock.get(roc_field, "N/A")
                if (
                    ey_val == "N/A"
                    or roc_val == "N/A"
                    or ey_val is None
                    or roc_val is None
                ):
                    stock[score_field] = "N/A"

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
