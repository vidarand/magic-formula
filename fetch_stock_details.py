#!/usr/bin/env python3
"""Fetch detailed data for multiple stocks and save to JSON for inspection."""

import yfinance as yf
import json
from datetime import datetime
import sys

# Stocks to fetch - will be passed as arguments or use defaults
if len(sys.argv) > 1:
    tickers = sys.argv[1:]
else:
    # Default: fetch from stocks_to_fetch.json if it exists
    # Fallback to some example stocks
    tickers = ["ERIC-B.ST", "SANION.ST", "BETS-B.ST", "TRUE-B.ST"]

print(f"Fetching detailed data for {len(tickers)} stocks...")
print("=" * 80)

all_data = {}

for ticker in tickers:
    print(f"\nFetching {ticker}...")
    try:
        stock = yf.Ticker(ticker)

        # Get all available data
        data = {
            "ticker": ticker,
            "fetched_at": datetime.now().isoformat(),
            "info": stock.info,
        }

        # Get financials data
        if not stock.financials.empty:
            data["financials"] = {}
            for idx in stock.financials.index:
                data["financials"][str(idx)] = {}
                for col in stock.financials.columns:
                    val = stock.financials.loc[idx, col]
                    if hasattr(val, "item"):
                        try:
                            val = val.item()
                        except:
                            val = float(val) if not str(val) == "nan" else None
                    if str(val) == "nan":
                        val = None
                    data["financials"][str(idx)][str(col)] = val

        if not stock.quarterly_financials.empty:
            data["quarterly_financials"] = {}
            for idx in stock.quarterly_financials.index:
                data["quarterly_financials"][str(idx)] = {}
                for col in stock.quarterly_financials.columns:
                    val = stock.quarterly_financials.loc[idx, col]
                    if hasattr(val, "item"):
                        try:
                            val = val.item()
                        except:
                            val = float(val) if not str(val) == "nan" else None
                    if str(val) == "nan":
                        val = None
                    data["quarterly_financials"][str(idx)][str(col)] = val

        # Get balance sheet data
        if not stock.balance_sheet.empty:
            data["balance_sheet"] = {}
            for idx in stock.balance_sheet.index:
                data["balance_sheet"][str(idx)] = {}
                for col in stock.balance_sheet.columns:
                    val = stock.balance_sheet.loc[idx, col]
                    if hasattr(val, "item"):
                        try:
                            val = val.item()
                        except:
                            val = float(val) if not str(val) == "nan" else None
                    if str(val) == "nan":
                        val = None
                    data["balance_sheet"][str(idx)][str(col)] = val

        if not stock.quarterly_balance_sheet.empty:
            data["quarterly_balance_sheet"] = {}
            for idx in stock.quarterly_balance_sheet.index:
                data["quarterly_balance_sheet"][str(idx)] = {}
                for col in stock.quarterly_balance_sheet.columns:
                    val = stock.quarterly_balance_sheet.loc[idx, col]
                    if hasattr(val, "item"):
                        try:
                            val = val.item()
                        except:
                            val = float(val) if not str(val) == "nan" else None
                    if str(val) == "nan":
                        val = None
                    data["quarterly_balance_sheet"][str(idx)][str(col)] = val

        all_data[ticker] = data
        print(f"  ✓ {ticker} - Success")

    except Exception as e:
        print(f"  ✗ {ticker} - Error: {str(e)}")
        all_data[ticker] = {"error": str(e)}

# Save to JSON
output_file = "stock_details_data.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(all_data, f, indent=2, ensure_ascii=False, default=str)

print("\n" + "=" * 80)
print(f"✓ Data saved to {output_file}")
print("\nSummary:")
for ticker, data in all_data.items():
    if "error" not in data:
        print(f"  {ticker}:")
        if "quarterly_financials" in data:
            print(
                f"    - Quarterly financials: {len(data['quarterly_financials'])} rows"
            )
        if "quarterly_balance_sheet" in data:
            print(
                f"    - Quarterly balance sheet: {len(data['quarterly_balance_sheet'])} rows"
            )
        if "info" in data and "longName" in data["info"]:
            print(f"    - Name: {data['info']['longName']}")
    else:
        print(f"  {ticker}: ERROR - {data['error']}")
