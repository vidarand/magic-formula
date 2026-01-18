#!/usr/bin/env python3
"""
Stock Data Schema Definition

This schema defines the standard structure for stock data objects.
All scripts should follow this schema to maintain consistency.

The most complete data source is: data/current_stocks.json (from fetch_stocks_smart.py)
"""

from typing import Optional, Union
from datetime import datetime

# Type aliases
StockValue = Union[int, float, str, None]  # Can be number, "N/A", or None


class StockSchema:
    """
    Standard schema for stock data objects - streamlined for Magic Formula.

    All stock data dictionaries should follow this structure.
    Missing or unavailable fields should be set to "N/A" (string), not None or empty.
    """

    # Required fields (always present)
    ticker: str  # Stock ticker symbol (e.g., "AZN", "ABB")
    name: str  # Company name (e.g., "AstraZeneca PLC")
    yfinance_ticker: str  # Yahoo Finance ticker with suffix (e.g., "AZN.ST")
    last_updated: str  # ISO format timestamp (e.g., "2026-01-16T18:41:59.602852")
    error: Optional[str]  # Error message if fetch failed, None if successful

    # Basic price data
    price: StockValue  # Current price (float) or "N/A"
    change: StockValue  # Price change from previous close (float) or "N/A"
    change_percent: StockValue  # Percentage change (float) or "N/A"
    currency: str  # Currency code (e.g., "SEK", "USD", "NOK")

    # Market data
    market_cap: StockValue  # Market capitalization (int/float) or "N/A"
    volume: StockValue  # Current volume (int) or "N/A"

    # Descriptive/Classification fields
    sector: (
        str  # Sector name or "N/A" (needed to filter Financial Services/Real Estate)
    )
    industry: str  # Industry name or "N/A"
    country: str  # Country name or "N/A"
    market: str  # Market/exchange identifier (e.g., "se_market", "us_market") or "N/A"
    description: str  # Company description/business summary or "N/A"
    market_cap_category: str  # Market cap classification: "Large-cap", "Mid-cap", "Small-cap", "Micro-cap", or "N/A"

    # Interesting metrics
    pe_ratio: StockValue  # P/E ratio (float) or "N/A"
    dividend_yield: StockValue  # Dividend yield (float, as decimal) or "N/A"

    # Magic Formula required fields
    enterprise_value: StockValue  # Enterprise value (int/float) or "N/A"
    ebit: StockValue  # Earnings Before Interest and Taxes (int/float) or "N/A"
    ebit_period: (
        StockValue  # Fiscal period for EBIT data (YYYY-MM-DD or fiscal year) or "N/A"
    )
    total_assets: (
        StockValue  # Total Assets (for Magic Formula calculation) (int/float) or "N/A"
    )
    current_assets: StockValue  # Current Assets (for Working Capital calculation) (int/float) or "N/A"
    current_liabilities: StockValue  # Total Current Liabilities (int/float) or "N/A"
    net_fixed_assets: (
        StockValue  # Net Fixed Assets / PP&E (for ROC calculation) (int/float) or "N/A"
    )
    balance_sheet_period: StockValue  # Fiscal period for balance sheet data (YYYY-MM-DD or fiscal year) or "N/A"
    quarterly_balance_sheet: StockValue  # Last 4 quarters of balance sheet data: list of {period, current_assets, current_liabilities, net_fixed_assets} dicts or "N/A"

    # Calculated Magic Formula score (lower is better, "N/A" if cannot be calculated)
    magic_formula_score: StockValue  # Combined rank score (int/float) or "N/A" - default (excludes financial/investment companies)
    magic_formula_score_100m: StockValue  # Market cap >= 100M SEK
    magic_formula_score_500m: StockValue  # Market cap >= 500M SEK
    magic_formula_score_1b: StockValue  # Market cap >= 1B SEK
    magic_formula_score_5b: StockValue  # Market cap >= 5B SEK
    # Earnings Yield and Return on Capital ranks for each score variant
    ey_rank: StockValue  # Earnings Yield rank (1 = best) for default score
    roc_rank: StockValue  # Return on Capital rank (1 = best) for default score
    earnings_yield: StockValue  # Earnings Yield as percentage (EBIT/EV * 100)
    return_on_capital: (
        StockValue  # Return on Capital as percentage (EBIT/Invested Capital * 100)
    )
    ey_rank_100m: StockValue  # Earnings Yield rank for score_100m variant
    roc_rank_100m: StockValue  # Return on Capital rank for score_100m variant
    ey_rank_500m: StockValue  # Earnings Yield rank for score_500m variant
    roc_rank_500m: StockValue  # Return on Capital rank for score_500m variant
    ey_rank_1b: StockValue  # Earnings Yield rank for score_1b variant
    roc_rank_1b: StockValue  # Return on Capital rank for score_1b variant
    ey_rank_5b: StockValue  # Earnings Yield rank for score_5b variant
    roc_rank_5b: StockValue  # Return on Capital rank for score_5b variant
    magic_formula_reason: str  # Always present: "Beräknad" if valid, or reason why N/A
    magic_formula_ebit_periods: StockValue  # Periods used for EBIT calculation (e.g., "2024-Q1 to 2024-Q4" for TTM, or annual period)
    magic_formula_balance_sheet_period: StockValue  # Period used for balance sheet data (quarterly date or annual period)
    magic_formula_uses_ttm: Optional[
        bool
    ]  # Whether TTM (Trailing Twelve Months) was used for calculation (None if not calculated)
    exclusion_reason: Optional[
        str
    ]  # Reason for exclusion from ranking (financial/investment companies), None if not excluded
    default_excluded: bool  # Boolean flag: True if excluded by default (financial/investment/real estate), False otherwise


# Schema definition as a dictionary for validation
STOCK_SCHEMA = {
    # Required fields
    "ticker": str,
    "name": str,
    "yfinance_ticker": str,
    "last_updated": str,
    "error": (str, type(None)),
    # Basic price data
    "price": (int, float, str),
    "change": (int, float, str),
    "change_percent": (int, float, str),
    "currency": str,
    # Market data
    "market_cap": (int, float, str),
    "volume": (int, str),
    # Descriptive/Classification
    "sector": str,
    "industry": str,
    "country": str,
    "market": str,
    "description": str,
    "market_cap_category": str,
    # Interesting metrics
    "pe_ratio": (int, float, str),
    "dividend_yield": (int, float, str),
    # Magic Formula required fields
    "enterprise_value": (int, float, str),
    "ebit": (int, float, str),
    "ebit_period": (
        int,
        float,
        str,
    ),  # Fiscal period for EBIT (YYYY-MM-DD or fiscal year)
    "total_assets": (int, float, str),
    "current_assets": (int, float, str),
    "current_liabilities": (int, float, str),
    "net_fixed_assets": (int, float, str),
    "balance_sheet_period": (
        int,
        float,
        str,
    ),  # Fiscal period for balance sheet (YYYY-MM-DD or fiscal year)
    "quarterly_balance_sheet": (
        int,
        float,
        str,
    ),  # Last 4 quarters of balance sheet data
    "magic_formula_score": (int, float, str),
    "magic_formula_score_100m": (int, float, str),
    "magic_formula_score_500m": (int, float, str),
    "magic_formula_score_1b": (int, float, str),
    "magic_formula_score_5b": (int, float, str),
    "ey_rank": (int, float, str),
    "roc_rank": (int, float, str),
    "earnings_yield": (int, float, str),
    "return_on_capital": (int, float, str),
    "ey_rank_100m": (int, float, str),
    "roc_rank_100m": (int, float, str),
    "ey_rank_500m": (int, float, str),
    "roc_rank_500m": (int, float, str),
    "ey_rank_1b": (int, float, str),
    "roc_rank_1b": (int, float, str),
    "ey_rank_5b": (int, float, str),
    "roc_rank_5b": (int, float, str),
    "magic_formula_reason": str,
    "exclusion_reason": (str, type(None)),
    "default_excluded": bool,
}


def create_empty_stock(ticker: str, name: str, yfinance_ticker: str) -> dict:
    """
    Create an empty stock object following the schema.
    All fields are set to "N/A" except required fields.
    """
    return {
        "ticker": ticker,
        "name": name,
        "yfinance_ticker": yfinance_ticker,
        "last_updated": datetime.now().isoformat(),
        "error": None,
        # Basic price data
        "price": "N/A",
        "change": "N/A",
        "change_percent": "N/A",
        "currency": "SEK",
        # Market data
        "market_cap": "N/A",
        "volume": "N/A",
        # Descriptive/Classification
        "sector": "N/A",
        "industry": "N/A",
        "country": "Sweden",
        "market": "N/A",
        "description": "N/A",
        "market_cap_category": "N/A",
        # Interesting metrics
        "pe_ratio": "N/A",
        "dividend_yield": "N/A",
        # Magic Formula required fields
        "enterprise_value": "N/A",
        "ebit": "N/A",
        "ebit_period": "N/A",  # Fiscal period for EBIT data (YYYY-MM-DD or fiscal year)
        "quarterly_ebit": "N/A",  # Last 4 quarters of EBIT data: list of {period: date, ebit: value} or "N/A"
        "total_assets": "N/A",
        "current_assets": "N/A",
        "current_liabilities": "N/A",
        "net_fixed_assets": "N/A",
        "balance_sheet_period": "N/A",  # Fiscal period for balance sheet data (YYYY-MM-DD or fiscal year)
        "quarterly_balance_sheet": "N/A",  # Last 4 quarters: list of {period, current_assets, current_liabilities, net_fixed_assets} or "N/A"
        "magic_formula_score": "N/A",
        "magic_formula_score_100m": "N/A",
        "magic_formula_score_500m": "N/A",
        "magic_formula_score_1b": "N/A",
        "magic_formula_score_5b": "N/A",
        "ey_rank": "N/A",
        "roc_rank": "N/A",
        "earnings_yield": "N/A",
        "return_on_capital": "N/A",
        "ey_rank_100m": "N/A",
        "roc_rank_100m": "N/A",
        "ey_rank_500m": "N/A",
        "roc_rank_500m": "N/A",
        "ey_rank_1b": "N/A",
        "roc_rank_1b": "N/A",
        "ey_rank_5b": "N/A",
        "roc_rank_5b": "N/A",
        "magic_formula_reason": "Ej beräknad",
        "magic_formula_ebit_periods": "N/A",  # Periods used for EBIT calculation
        "magic_formula_balance_sheet_period": "N/A",  # Period used for balance sheet
        "magic_formula_uses_ttm": None,  # Whether TTM was used (None if not calculated, True/False if calculated)
        "exclusion_reason": None,
        "default_excluded": False,
    }


def validate_stock(stock: dict) -> tuple[bool, list[str]]:
    """
    Validate a stock object against the schema.

    Returns:
        (is_valid, errors): Tuple of validation result and list of error messages
    """
    errors = []

    # Check required fields
    required_fields = ["ticker", "name", "yfinance_ticker", "last_updated", "error"]
    for field in required_fields:
        if field not in stock:
            errors.append(f"Missing required field: {field}")

    # Check field types (basic validation)
    for field, expected_types in STOCK_SCHEMA.items():
        if field in stock:
            value = stock[field]
            if value is not None and value != "N/A":
                if not isinstance(value, expected_types):
                    errors.append(
                        f"Field '{field}' has wrong type: {type(value).__name__}, "
                        f"expected one of {[t.__name__ for t in expected_types if isinstance(t, type)]}"
                    )

    return len(errors) == 0, errors


def normalize_stock(stock: dict) -> dict:
    """
    Normalize a stock object to match the schema.
    Fills in missing fields with "N/A" defaults.
    """
    normalized = create_empty_stock(
        stock.get("ticker", "UNKNOWN"),
        stock.get("name", "Unknown Company"),
        stock.get("yfinance_ticker", "UNKNOWN.ST"),
    )

    # Copy all existing fields
    normalized.update(stock)

    # Ensure error is None if not set or empty
    if normalized.get("error") == "":
        normalized["error"] = None

    # Ensure last_updated is set
    if "last_updated" not in normalized or not normalized["last_updated"]:
        normalized["last_updated"] = datetime.now().isoformat()

    return normalized


# Field categories for documentation
FIELD_CATEGORIES = {
    "required": ["ticker", "name", "yfinance_ticker", "last_updated", "error"],
    "price": ["price", "change", "change_percent", "currency"],
    "market": ["market_cap", "volume"],
    "descriptive": [
        "sector",
        "industry",
        "country",
        "market",
        "description",
        "market_cap_category",
    ],
    "metrics": ["pe_ratio", "dividend_yield"],
    "magic_formula": [
        "enterprise_value",
        "ebit",
        "total_assets",
        "current_assets",
        "current_liabilities",
        "net_fixed_assets",
        "magic_formula_score",
        "magic_formula_score_100m",
        "magic_formula_score_500m",
        "magic_formula_score_1b",
        "magic_formula_score_5b",
        "ey_rank",
        "roc_rank",
        "earnings_yield",
        "return_on_capital",
        "ey_rank_100m",
        "roc_rank_100m",
        "ey_rank_500m",
        "roc_rank_500m",
        "ey_rank_1b",
        "roc_rank_1b",
        "ey_rank_5b",
        "roc_rank_5b",
        "magic_formula_reason",
    ],
}


if __name__ == "__main__":
    # Example usage
    print("Stock Data Schema")
    print("=" * 60)
    print(f"Total fields: {len(STOCK_SCHEMA)}")
    print(f"Required fields: {len(FIELD_CATEGORIES['required'])}")
    print("\nField categories:")
    for category, fields in FIELD_CATEGORIES.items():
        print(f"  {category}: {len(fields)} fields")

    # Test create_empty_stock
    print("\n" + "=" * 60)
    print("Example empty stock:")
    example = create_empty_stock("TEST", "Test Company", "TEST.ST")
    print(f"  Ticker: {example['ticker']}")
    print(f"  Fields: {len(example)}")

    # Test validation
    print("\n" + "=" * 60)
    print("Validation test:")
    valid_stock = {
        "ticker": "TEST",
        "name": "Test",
        "yfinance_ticker": "TEST.ST",
        "last_updated": datetime.now().isoformat(),
        "error": None,
        "price": 100.0,
    }
    is_valid, errors = validate_stock(valid_stock)
    print(f"  Valid: {is_valid}")
    if errors:
        print(f"  Errors: {errors}")
