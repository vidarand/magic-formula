#!/usr/bin/env python3
"""Quick script to fetch Mycronic data and save to JSON for inspection."""

import yfinance as yf
import json
from datetime import datetime

# Fetch Mycronic data
ticker = 'MYCR.ST'
print(f"Fetching data for {ticker}...")
stock = yf.Ticker(ticker)

# Get all available data
data = {
    'ticker': ticker,
    'fetched_at': datetime.now().isoformat(),
    'info': stock.info,
}

# Get financials data
if not stock.financials.empty:
    data['financials'] = {}
    for idx in stock.financials.index:
        data['financials'][str(idx)] = {}
        for col in stock.financials.columns:
            val = stock.financials.loc[idx, col]
            if hasattr(val, 'item'):
                val = val.item()
            data['financials'][str(idx)][str(col)] = val

if not stock.quarterly_financials.empty:
    data['quarterly_financials'] = {}
    for idx in stock.quarterly_financials.index:
        data['quarterly_financials'][str(idx)] = {}
        for col in stock.quarterly_financials.columns:
            val = stock.quarterly_financials.loc[idx, col]
            if hasattr(val, 'item'):
                val = val.item()
            data['quarterly_financials'][str(idx)][str(col)] = val

# Get balance sheet data
if not stock.balance_sheet.empty:
    data['balance_sheet'] = {}
    for idx in stock.balance_sheet.index:
        data['balance_sheet'][str(idx)] = {}
        for col in stock.balance_sheet.columns:
            val = stock.balance_sheet.loc[idx, col]
            if hasattr(val, 'item'):
                val = val.item()
            data['balance_sheet'][str(idx)][str(col)] = val

if not stock.quarterly_balance_sheet.empty:
    data['quarterly_balance_sheet'] = {}
    for idx in stock.quarterly_balance_sheet.index:
        data['quarterly_balance_sheet'][str(idx)] = {}
        for col in stock.quarterly_balance_sheet.columns:
            val = stock.quarterly_balance_sheet.loc[idx, col]
            if hasattr(val, 'item'):
                val = val.item()
            data['quarterly_balance_sheet'][str(idx)][str(col)] = val

# Save to JSON
output_file = 'mycronic_data.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False, default=str)

print(f'\n✓ Data saved to {output_file}')
print(f'\nInfo keys: {list(data["info"].keys())[:10]}...')
if 'quarterly_financials' in data:
    print(f'\nQuarterly financials available with {len(data["quarterly_financials"])} rows')
if 'quarterly_balance_sheet' in data:
    print(f'Quarterly balance sheet available with {len(data["quarterly_balance_sheet"])} rows')
