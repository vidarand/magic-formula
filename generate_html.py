#!/usr/bin/env python3
"""
Script to generate HTML from stock data.
Reads from data/current_stocks.json and generates stocks.html
"""

import json
from pathlib import Path
from datetime import datetime

# Data source
STOCKS_DATA = Path("data/current_stocks.json")
HISTORY_DATA = Path("data/stock_history.json")
OUTPUT_HTML = Path("stocks.html")
HISTORY_HTML = Path("history.html")


def load_stocks_data():
    """Load stock data from JSON file."""
    if not STOCKS_DATA.exists():
        print(f"Error: {STOCKS_DATA} not found!")
        return []

    with open(STOCKS_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle both dict and list formats
    if isinstance(data, dict):
        return list(data.values())
    elif isinstance(data, list):
        return data
    else:
        return []


def format_number(num):
    """Format large numbers."""
    if num == "N/A" or num is None:
        return "N/A"
    if isinstance(num, (int, float)):
        if num >= 1e12:
            return f"{num/1e12:.2f}T"
        if num >= 1e9:
            return f"{num/1e9:.2f}B"
        if num >= 1e6:
            return f"{num/1e6:.2f}M"
        if num >= 1e3:
            return f"{num/1e3:.2f}K"
        return f"{num:,.0f}"
    return str(num)


def format_last_updated(last_updated_str):
    """Format last updated timestamp."""
    if not last_updated_str or last_updated_str == "N/A":
        return "N/A"
    try:
        dt = datetime.fromisoformat(last_updated_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return str(last_updated_str)


def format_dividend_yield(dy):
    """Format dividend yield."""
    if dy == "N/A" or dy is None:
        return "N/A"
    if isinstance(dy, (int, float)):
        return f"{dy * 100:.2f}%" if dy > 0 else "N/A"
    return str(dy)


def get_country_flag(country: str, market: str) -> str:
    """Get country flag emoji based on country or market."""
    if country == "N/A" and market == "N/A":
        return ""

    # Map countries to flags
    country_flags = {
        "Sweden": "🇸🇪",
        "Norway": "🇳🇴",
        "Denmark": "🇩🇰",
        "Finland": "🇫🇮",
        "United Kingdom": "🇬🇧",
        "United States": "🇺🇸",
        "Germany": "🇩🇪",
        "France": "🇫🇷",
        "Netherlands": "🇳🇱",
        "Switzerland": "🇨🇭",
        "Iceland": "🇮🇸",
    }

    # Check country first
    if country and country != "N/A":
        country_lower = country.lower()
        for key, flag in country_flags.items():
            if key.lower() in country_lower:
                return flag

    # Fallback to market
    if market and market != "N/A":
        market_lower = market.lower()
        if "se_" in market_lower or "stockholm" in market_lower:
            return "🇸🇪"
        elif "no_" in market_lower or "oslo" in market_lower:
            return "🇳🇴"
        elif "dk_" in market_lower or "copenhagen" in market_lower:
            return "🇩🇰"
        elif "fi_" in market_lower or "helsinki" in market_lower:
            return "🇫🇮"
        elif "uk_" in market_lower or "london" in market_lower:
            return "🇬🇧"
        elif (
            "us_" in market_lower or "nyse" in market_lower or "nasdaq" in market_lower
        ):
            return "🇺🇸"
        elif "de_" in market_lower or "xetra" in market_lower:
            return "🇩🇪"
        elif "fr_" in market_lower or "paris" in market_lower:
            return "🇫🇷"
        elif "nl_" in market_lower or "amsterdam" in market_lower:
            return "🇳🇱"
        elif "ch_" in market_lower or "zurich" in market_lower:
            return "🇨🇭"
        elif "is_" in market_lower or "iceland" in market_lower:
            return "🇮🇸"

    return ""  # No default


def _generate_exclusion_stats(stocks):
    """Generate exclusion statistics HTML."""
    exclusion_counts = {}
    for stock in stocks:
        # Use default_excluded flag if available, fallback to exclusion_reason for backwards compatibility
        if stock.get("default_excluded") or stock.get("exclusion_reason"):
            reason = stock.get("exclusion_reason") or "Exkluderad"
            exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1

    if not exclusion_counts:
        return "<div>Inga aktier exkluderade</div>"

    stats_html = []
    for reason, count in sorted(exclusion_counts.items()):
        stats_html.append(
            f"<div style='margin: 5px 0;'><strong>{reason}:</strong> {count} aktier</div>"
        )

    return "".join(stats_html)


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
            stock["magic_formula_reason"] = "Fel vid hämtning av data"
            continue

        ebit = stock.get("ebit", "N/A")
        ev = stock.get("enterprise_value", "N/A")
        total_assets = stock.get("total_assets", "N/A")
        current_liabilities = stock.get("current_liabilities", "N/A")

        # Skip if required fields are missing
        if ebit == "N/A" or ebit is None:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Saknar EBIT"
            continue
        if ev == "N/A" or ev is None:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Saknar företagsvärde"
            continue
        if total_assets == "N/A" or total_assets is None:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Saknar totala tillgångar"
            continue
        if current_liabilities == "N/A" or current_liabilities is None:
            stock["magic_formula_score"] = "N/A"
            stock["magic_formula_reason"] = "Saknar kortfristiga skulder"
            continue

        try:
            ebit_val = float(ebit)
            ev_val = float(ev)
            assets_val = float(total_assets)
            liab_val = float(current_liabilities)

            # Calculate Earnings Yield
            ey = ebit_val / ev_val if ev_val > 0 else 0

            # Calculate Return on Capital
            invested_capital = assets_val - liab_val
            roc = ebit_val / invested_capital if invested_capital > 0 else 0

            if ey > 0 and roc > 0:
                valid_stocks.append({"stock": stock, "ey": ey, "roc": roc})
            else:
                stock["magic_formula_score"] = "N/A"
                if ebit_val < 0:
                    stock["magic_formula_reason"] = "Negativ EBIT (förluster)"
                elif ey <= 0:
                    stock["magic_formula_reason"] = (
                        "Negativ/noll avkastning på intäkter"
                    )
                elif roc <= 0:
                    stock["magic_formula_reason"] = "Negativ/noll avkastning på kapital"
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

    # Calculate combined score (lower is better)
    for item in valid_stocks:
        magic_score = item["ey_rank"] + item["roc_rank"]
        item["stock"]["magic_formula_score"] = magic_score
        item["stock"]["ey_rank"] = item["ey_rank"]
        item["stock"]["roc_rank"] = item["roc_rank"]
        item["stock"]["magic_formula_reason"] = None  # Clear reason for valid scores

    # Validate consistency: ensure any stock with N/A ranks also has N/A score
    for stock in stocks:
        ey_rank = stock.get("ey_rank", "N/A")
        roc_rank = stock.get("roc_rank", "N/A")
        if ey_rank == "N/A" or roc_rank == "N/A" or ey_rank is None or roc_rank is None:
            stock["magic_formula_score"] = "N/A"

    return stocks


def generate_html(stocks):
    """Generate simple HTML table."""

    # Note: Magic Formula scores should already be calculated and saved in current_stocks.json
    # by fetch_stocks.py. We recalculate here to ensure they're up to date.
    stocks = calculate_magic_formula_scores(stocks)

    # Separate excluded companies (financial/investment) from included ones
    excluded_stocks = []
    included_stocks = []

    for stock in stocks:
        if stock.get("exclusion_reason"):
            excluded_stocks.append(stock)
        else:
            included_stocks.append(stock)

    # Sort included stocks by Magic Formula score (ascending - lower is better)
    included_stocks_sorted = sorted(
        included_stocks,
        key=lambda x: (
            x.get("magic_formula_score", 999999)
            if isinstance(x.get("magic_formula_score"), (int, float))
            else 999999
        ),
    )

    # Sort excluded stocks by market cap for display
    excluded_stocks_sorted = sorted(
        excluded_stocks,
        key=lambda x: (
            x.get("market_cap", 0)
            if isinstance(x.get("market_cap"), (int, float))
            else 0
        ),
        reverse=True,
    )

    # Combine: included first (sorted by Magic Formula), then excluded (sorted by market cap)
    stocks_sorted = included_stocks_sorted + excluded_stocks_sorted

    # Generate table rows
    rows = []
    for index, stock in enumerate(stocks_sorted):
        # Check if stock has error or all key data is missing
        has_error = stock.get("error")
        if not has_error:
            # Check if all key fields are N/A
            key_fields = ["price", "market_cap", "sector"]
            all_na = all(
                stock.get(field) == "N/A" or stock.get(field) is None
                for field in key_fields
            )
            if all_na:
                has_error = "No data available"

        if has_error:
            rows.append(
                f"""
            <tr style="background-color: #fff3cd;">
                <td class="rank">#{index + 1}</td>
                <td><strong>{stock.get('ticker', 'N/A')}</strong></td>
                <td>{stock.get('name', 'N/A')}</td>
                <td colspan="19" style="color: #856404; font-weight: 600;">
                    {has_error}
                </td>
            </tr>
            """
            )
        else:
            price = stock.get("price", "N/A")
            price_str = f"{price:.2f}" if isinstance(price, (int, float)) else "N/A"

            change = stock.get("change", "N/A")
            change_str = f"{change:+.2f}" if isinstance(change, (int, float)) else "N/A"
            change_class = ""
            if isinstance(change, (int, float)):
                change_class = (
                    "positive" if change > 0 else "negative" if change < 0 else ""
                )

            change_pct = stock.get("change_percent", "N/A")
            change_pct_str = (
                f"{change_pct:+.2f}%" if isinstance(change_pct, (int, float)) else "N/A"
            )

            rows.append(
                f"""
            <tr>
                <td class="rank">#{index + 1}</td>
                <td><strong>{stock.get('ticker', 'N/A')}</strong></td>
                <td>{stock.get('name', 'N/A')}</td>
                <td>
                    <strong>{stock.get('magic_formula_score', 'N/A')}</strong>
                    {f"<br><small style='color: #666;'>{stock.get('magic_formula_reason', '')}</small>" if stock.get('magic_formula_score') == 'N/A' and stock.get('magic_formula_reason') else ''}
                </td>
                <td>{price_str} {stock.get('currency', 'SEK')}</td>
                <td class="{change_class}">{change_str}</td>
                <td class="{change_class}">{change_pct_str}</td>
                <td>{format_number(stock.get('volume'))}</td>
                <td>{format_number(stock.get('market_cap'))}</td>
                <td>{stock.get('sector', 'N/A')}</td>
                <td>{stock.get('industry', 'N/A')}</td>
                <td>{get_country_flag(stock.get('country', 'N/A'), stock.get('market', 'N/A'))} {stock.get('country', 'N/A')}</td>
                <td>{stock.get('market_cap_category', 'N/A')}</td>
                <td>{stock.get('pe_ratio', 'N/A') if isinstance(stock.get('pe_ratio'), (int, float)) else 'N/A'}</td>
                <td>{format_dividend_yield(stock.get('dividend_yield'))}</td>
                <td>{format_number(stock.get('enterprise_value'))}</td>
                <td>{format_number(stock.get('ebit'))}</td>
                <td>{format_number(stock.get('current_assets'))}</td>
                <td>{format_number(stock.get('current_liabilities'))}</td>
                <td>{format_number(stock.get('net_fixed_assets'))}</td>
                <td style="font-size: 10px;">{format_last_updated(stock.get('last_updated'))}</td>
            </tr>
            """
            )

    table_rows = "".join(rows)

    successful = len([s for s in stocks if not s.get("error")])
    failed = len(stocks) - successful

    html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stockholmsbörsen - Alla Aktier | Magic Formula Sverige</title>
    <meta name="description" content="Aktierankingar baserat på Magic Formula-strategin för Stockholmsbörsen. Hitta undervärderade aktier med hög avkastning.">
    <meta name="keywords" content="Magic Formula, aktier, Stockholmsbörsen, investering, värdering">
    <meta name="author" content="Magic Formula Sverige">
    <meta property="og:title" content="Stockholmsbörsen - Magic Formula Rankingar">
    <meta property="og:description" content="Aktierankingar baserat på Magic Formula-strategin">
    <meta property="og:type" content="website">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            padding: 0;
            margin: 0;
            background: #f8f9fa;
            min-height: 100vh;
        }}
        .page-wrapper {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 16px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f0f0f0;
        }}
        .nav-links {{
            display: flex;
            gap: 15px;
        }}
        .nav-links a {{
            color: #495057;
            text-decoration: none;
            font-weight: 600;
            padding: 8px 16px;
            border-radius: 8px;
            transition: all 0.2s;
        }}
        .nav-links a:hover {{
            background: #f0f0f0;
            transform: translateY(-1px);
        }}
        h1 {{
            margin: 0 0 10px 0;
            color: #333;
            font-size: 2.2em;
            font-weight: 700;
        }}
        .subtitle {{
            color: #666;
            font-size: 0.95em;
            margin: 5px 0;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            margin-top: 10px;
        }}
        .stat {{
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        .stat strong {{
            color: #212529;
            font-size: 1.2em;
        }}
        .table-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow-x: auto;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            font-size: 12px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background: #212529;
            color: white;
            position: sticky;
            top: 0;
            font-weight: 600;
            padding: 12px 8px;
            z-index: 10;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .positive {{
            color: #28a745;
            font-weight: 600;
        }}
        .negative {{
            color: #dc3545;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            color: #666;
            font-size: 12px;
        }}
        th {{
            cursor: pointer;
            user-select: none;
            position: relative;
            padding-right: 20px;
        }}
        th:hover {{
            background-color: #e9ecef;
        }}
        th.sort-asc::after {{
            content: ' ▲';
            font-size: 10px;
            color: #495057;
        }}
        th.sort-desc::after {{
            content: ' ▼';
            font-size: 10px;
            color: #495057;
        }}
        .stat-group {{
            margin-bottom: 10px;
        }}
        .stat-group strong {{
            color: #495057;
        }}
        .reason-list {{
            margin-left: 20px;
            margin-top: 5px;
            font-size: 14px;
        }}
        .reason-item {{
            margin: 3px 0;
        }}
        button {{
            transition: all 0.2s ease;
        }}
        button:hover {{
            transform: translateY(-2px);
        }}
        input[type="range"] {{
            -webkit-appearance: none;
            appearance: none;
            height: 6px;
            background: #ddd;
            border-radius: 3px;
            outline: none;
        }}
        input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            appearance: none;
            width: 18px;
            height: 18px;
            background: #495057;
            border-radius: 50%;
            cursor: pointer;
        }}
        input[type="range"]::-moz-range-thumb {{
            width: 18px;
            height: 18px;
            background: #495057;
            border-radius: 50%;
            cursor: pointer;
            border: none;
        }}
    </style>
</head>
<body>
    <div class="page-wrapper">
    <div class="header">
        <div class="header-top">
            <div>
                <h1>Stockholmsbörsen</h1>
                <p class="subtitle">Magic Formula Aktierankingar</p>
            </div>
            <div class="nav-links">
                <a href="index.html">Hem</a>
                <a href="stocks.html" class="active">Aktuella Rankingar</a>
                <a href="history.html">Historik</a>
                <a href="faq.html">FAQ</a>
            </div>
        </div>
        <p style="margin: 5px 0; color: #666; font-size: 0.9em;">Senast uppdaterad: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <div class="stats">
            <div class="stat">Totalt antal aktier: <strong>{len(stocks)}</strong></div>
            <div class="stat">Lyckades hämta: <strong>{successful}</strong></div>
            <div class="stat">Misslyckades: <strong>{failed}</strong></div>
        </div>
        <div id="exclusionStats" style="margin-top: 20px; padding: 20px; background: #f8f9fa; border-radius: 12px; border-left: 4px solid #212529;">
            <div style="margin-bottom: 15px;">
                <h3 style="margin: 0 0 10px 0; color: #212529; font-size: 1.2em;">Inkluderade i ranking</h3>
                <div style="font-size: 16px; color: #495057;">
                    <strong id="includedCount">{len([s for s in stocks_sorted if not (s.get("default_excluded") or s.get("exclusion_reason"))])}</strong> aktier rankade efter Magic Formula
                </div>
            </div>
            <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #dee2e6;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h3 style="margin: 0; color: #212529; font-size: 1.2em;">Exkluderade från ranking</h3>
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 14px; color: #495057;">
                        <input type="checkbox" id="showExcludedToggle" style="width: 18px; height: 18px; cursor: pointer;">
                        <span>Visa exkluderade aktier</span>
                    </label>
                </div>
                <div id="exclusionReasons" style="font-size: 14px; color: #6c757d;">
                    {_generate_exclusion_stats(stocks_sorted)}
                </div>
            </div>
        </div>
        <div style="margin-top: 20px; padding: 20px; background: #212529; border-radius: 12px;">
            <div style="background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px;">
                <label style="display: block; font-weight: 600; color: #333; margin-bottom: 10px;">
                    Ranka efter Magic Formula-variant:
                </label>
                <select id="magicFormulaScoreSelect" style="padding: 10px 15px; font-size: 14px; border: 2px solid #ddd; border-radius: 6px; background: white; cursor: pointer; font-weight: 600; width: 100%; max-width: 500px;">
                    <option value="magic_formula_score">Standard (exkluderar finansiella bolag)</option>
                    <option value="magic_formula_score_100m">≥ 100M SEK börsvärde</option>
                    <option value="magic_formula_score_500m">≥ 500M SEK börsvärde</option>
                    <option value="magic_formula_score_1b">≥ 1B SEK börsvärde</option>
                    <option value="magic_formula_score_5b">≥ 5B SEK börsvärde</option>
                </select>
                <p style="margin-top: 8px; font-size: 12px; color: #666;">Välj vilken Magic Formula-variant som ska användas för ranking. Varje variant har redan börsvärdesfilter inbyggt.</p>
                <div id="filterStats" style="margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 4px; font-size: 13px; color: #495057;">
                    <strong>Visar:</strong> <span id="filteredCount">{len([s for s in stocks_sorted if not s.get("exclusion_reason")])}</span> aktier med giltig score
                </div>
            </div>
        </div>
    </div>
    
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Ordning</th>
                    <th data-sort="ticker">Ticker</th>
                    <th data-sort="name">Namn</th>
                    <th data-sort="magic_formula_score">Magic Score</th>
                    <th data-sort="ey_rank">EY Rank</th>
                    <th data-sort="roc_rank">RoC Rank</th>
                    <th>EBIT Periods</th>
                    <th>Balance Sheet Period</th>
                    <th>TTM</th>
                    <th data-sort="price">Pris</th>
                    <th data-sort="change">Förändring</th>
                    <th data-sort="change_percent">Förändring %</th>
                    <th data-sort="volume">Volym</th>
                    <th data-sort="market_cap">Börsvärde</th>
                    <th data-sort="sector">Sektor</th>
                    <th data-sort="industry">Bransch</th>
                    <th data-sort="country">Land</th>
                    <th data-sort="market_cap_category">Storlek</th>
                    <th data-sort="pe_ratio">P/E</th>
                    <th data-sort="dividend_yield">Utdelningsavkastning</th>
                    <th data-sort="enterprise_value">Företagsvärde</th>
                    <th data-sort="ebit">EBIT</th>
                    <th data-sort="current_assets">Omsättningstillgångar</th>
                    <th data-sort="current_liabilities">Kortfristiga skulder</th>
                    <th data-sort="net_fixed_assets">Nettotillgångar</th>
                    <th data-sort="last_updated">Senast uppdaterad</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>
    
    </div>
    <div class="footer" style="text-align: center; margin-top: 40px; padding: 20px; color: white; font-size: 0.9em;">
        <p>Genererad från aktiedata JSON-filer | Magic Formula Sverige</p>
        <p style="margin-top: 10px; opacity: 0.8;">Data uppdateras dagligen automatiskt</p>
    </div>
    </div>
    
    <script>
        const allStocks = {json.dumps(stocks_sorted, ensure_ascii=False)};
        let currentStocks = [...allStocks];
        let originalSort = [...allStocks];
        
        function renderTable(stocks) {{
            const tbody = document.querySelector('tbody');
            tbody.innerHTML = stocks.map((stock, index) => {{
                // Check if stock has error or all key data is missing
                let hasError = stock.error;
                if (!hasError) {{
                    const keyFields = ['price', 'market_cap', 'sector'];
                    const allNA = keyFields.every(field => 
                        stock[field] === 'N/A' || stock[field] === null || stock[field] === undefined
                    );
                    if (allNA) {{
                        hasError = 'Ingen data tillgänglig';
                    }}
                }}
                
                if (hasError) {{
                    return `<tr style="background-color: #fff3cd;">
                        <td class="rank">#${{index + 1}}</td>
                        <td><strong>${{stock.ticker || 'N/A'}}</strong></td>
                        <td>${{stock.name || 'N/A'}}</td>
                        <td colspan="20" style="color: #856404; font-weight: 600;">
                            ${{hasError}}
                        </td>
                    </tr>`;
                }}
                
                const price = stock.price;
                const priceStr = (typeof price === 'number') ? price.toFixed(2) : 'N/A';
                const change = stock.change;
                const changeStr = (typeof change === 'number') ? (change > 0 ? '+' : '') + change.toFixed(2) : 'N/A';
                const changeClass = (typeof change === 'number') ? (change > 0 ? 'positive' : change < 0 ? 'negative' : '') : '';
                const changePct = stock.change_percent;
                const changePctStr = (typeof changePct === 'number') ? (changePct > 0 ? '+' : '') + changePct.toFixed(2) + '%' : 'N/A';
                
                const getCountryFlag = (country, market) => {{
                    if ((!country || country === 'N/A') && (!market || market === 'N/A')) {{
                        return '';
                    }}
                    
                    const countryFlags = {{
                        'sweden': '🇸🇪',
                        'norway': '🇳🇴',
                        'denmark': '🇩🇰',
                        'finland': '🇫🇮',
                        'united kingdom': '🇬🇧',
                        'united states': '🇺🇸',
                        'germany': '🇩🇪',
                        'france': '🇫🇷',
                        'netherlands': '🇳🇱',
                        'switzerland': '🇨🇭',
                        'iceland': '🇮🇸',
                    }};
                    
                    // Check country first
                    if (country && country !== 'N/A') {{
                        const countryLower = country.toLowerCase();
                        for (const [key, flag] of Object.entries(countryFlags)) {{
                            if (countryLower.includes(key)) {{
                                return flag;
                            }}
                        }}
                    }}
                    
                    // Fallback to market
                    if (market && market !== 'N/A') {{
                        const marketLower = market.toLowerCase();
                        if (marketLower.includes('se_') || marketLower.includes('stockholm')) {{
                            return '🇸🇪';
                        }} else if (marketLower.includes('no_') || marketLower.includes('oslo')) {{
                            return '🇳🇴';
                        }} else if (marketLower.includes('dk_') || marketLower.includes('copenhagen')) {{
                            return '🇩🇰';
                        }} else if (marketLower.includes('fi_') || marketLower.includes('helsinki')) {{
                            return '🇫🇮';
                        }} else if (marketLower.includes('uk_') || marketLower.includes('london')) {{
                            return '🇬🇧';
                        }} else if (marketLower.includes('us_') || marketLower.includes('nyse') || marketLower.includes('nasdaq')) {{
                            return '🇺🇸';
                        }} else if (marketLower.includes('de_') || marketLower.includes('xetra')) {{
                            return '🇩🇪';
                        }} else if (marketLower.includes('fr_') || marketLower.includes('paris')) {{
                            return '🇫🇷';
                        }} else if (marketLower.includes('nl_') || marketLower.includes('amsterdam')) {{
                            return '🇳🇱';
                        }} else if (marketLower.includes('ch_') || marketLower.includes('zurich')) {{
                            return '🇨🇭';
                        }} else if (marketLower.includes('is_') || marketLower.includes('iceland')) {{
                            return '🇮🇸';
                        }}
                    }}
                    
                    return '';
                }};
                
                const formatNumber = (num) => {{
                    if (num === 'N/A' || num === null || num === undefined) return 'N/A';
                    if (typeof num === 'number') {{
                        if (num >= 1e12) return (num / 1e12).toFixed(2) + 'T';
                        if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
                        if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
                        if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
                        return num.toLocaleString('sv-SE');
                    }}
                    return num;
                }};
                
                const formatDividendYield = (dy) => {{
                    if (dy === 'N/A' || dy === null || dy === undefined) return 'N/A';
                    if (typeof dy === 'number') return (dy * 100).toFixed(2) + '%';
                    return dy;
                }};
                
                const formatLastUpdated = (lu) => {{
                    if (!lu || lu === 'N/A') return 'N/A';
                    try {{
                        const dt = new Date(lu);
                        return dt.toLocaleString('sv-SE', {{year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'}});
                    }} catch {{
                        return lu;
                    }}
                }};
                
                // Format Magic Formula score for its own column (show the selected variant)
                const magicScore = stock[currentScoreField];
                const magicScoreDisplay = magicScore !== undefined && magicScore !== null && magicScore !== 'N/A' && typeof magicScore === 'number'
                    ? `<strong style="color: #212529;">${{magicScore}}</strong>`
                    : '<span style="color: #6c757d;">N/A</span>';
                const magicReasonDisplay = magicScore === 'N/A' && stock.magic_formula_reason
                    ? `<br><small style="color: #666;">${{stock.magic_formula_reason}}</small>`
                    : '';
                
                // Format period information for separate columns
                const ebitPeriods = stock.magic_formula_ebit_periods;
                const balanceSheetPeriod = stock.magic_formula_balance_sheet_period;
                const usesTTM = stock.magic_formula_uses_ttm;
                
                // Format EBIT periods display
                let ebitPeriodsDisplay = '<span style="color: #6c757d;">N/A</span>';
                if (magicScore !== 'N/A' && typeof magicScore === 'number' && ebitPeriods && ebitPeriods !== 'N/A') {{
                    ebitPeriodsDisplay = `<span style="color: #495057; font-size: 12px;">${{ebitPeriods}}</span>`;
                }}
                
                // Format Balance Sheet period display
                let balanceSheetPeriodDisplay = '<span style="color: #6c757d;">N/A</span>';
                if (magicScore !== 'N/A' && typeof magicScore === 'number' && balanceSheetPeriod && balanceSheetPeriod !== 'N/A') {{
                    balanceSheetPeriodDisplay = `<span style="color: #495057; font-size: 12px;">${{balanceSheetPeriod}}</span>`;
                }}
                
                // Format TTM indicator
                let ttmDisplay = '<span style="color: #6c757d;">-</span>';
                if (magicScore !== 'N/A' && typeof magicScore === 'number' && usesTTM) {{
                    ttmDisplay = '<span style="color: #28a745; font-weight: 600;">✓</span>';
                }} else if (magicScore !== 'N/A' && typeof magicScore === 'number') {{
                    ttmDisplay = '<span style="color: #6c757d;">Annual</span>';
                }}
                
                // Get EY and RoC ranks based on selected score variant
                const getRankField = (baseField) => {{
                    if (currentScoreField === 'magic_formula_score') return baseField;
                    if (currentScoreField === 'magic_formula_score_100m') return baseField + '_100m';
                    if (currentScoreField === 'magic_formula_score_500m') return baseField + '_500m';
                    if (currentScoreField === 'magic_formula_score_1b') return baseField + '_1b';
                    if (currentScoreField === 'magic_formula_score_5b') return baseField + '_5b';
                    return baseField;
                }};
                const eyRankField = getRankField('ey_rank');
                const rocRankField = getRankField('roc_rank');
                const eyRank = stock[eyRankField];
                const rocRank = stock[rocRankField];
                const eyRankDisplay = eyRank !== undefined && eyRank !== null && eyRank !== 'N/A' && typeof eyRank === 'number'
                    ? `<strong style="color: #212529;">${{eyRank}}</strong>`
                    : '<span style="color: #6c757d;">N/A</span>';
                const rocRankDisplay = rocRank !== undefined && rocRank !== null && rocRank !== 'N/A' && typeof rocRank === 'number'
                    ? `<strong style="color: #212529;">${{rocRank}}</strong>`
                    : '<span style="color: #6c757d;">N/A</span>';
                
                        // Check if this stock is excluded (use default_excluded flag if available)
                        const isExcluded = stock.default_excluded || stock.exclusion_reason;
                        const rowStyle = isExcluded ? 'background-color: #fff3cd; opacity: 0.8;' : '';
                        const exclusionReason = stock.exclusion_reason || 'Exkluderad';
                        const excludedLabel = isExcluded ? `<span style="color: #856404; font-size: 10px; font-weight: 600;">[EXKLUDERAD: ${{exclusionReason}}]</span>` : '';
                        
                        return `<tr style="${{rowStyle}}">
                            <td class="rank">#${{index + 1}}</td>
                            <td><strong>${{stock.ticker || 'N/A'}}</strong></td>
                            <td>${{stock.name || 'N/A'}} ${{excludedLabel}}</td>
                            <td>${{magicScoreDisplay}}${{magicReasonDisplay}}</td>
                            <td>${{eyRankDisplay}}</td>
                            <td>${{rocRankDisplay}}</td>
                            <td>${{ebitPeriodsDisplay}}</td>
                            <td>${{balanceSheetPeriodDisplay}}</td>
                            <td>${{ttmDisplay}}</td>
                    <td>${{priceStr}} ${{stock.currency || 'SEK'}}</td>
                    <td class="${{changeClass}}">${{changeStr}}</td>
                    <td class="${{changeClass}}">${{changePctStr}}</td>
                    <td>${{formatNumber(stock.volume)}}</td>
                    <td>${{formatNumber(stock.market_cap)}}</td>
                    <td>${{stock.sector || 'N/A'}}</td>
                    <td>${{stock.industry || 'N/A'}}</td>
                    <td>${{getCountryFlag(stock.country, stock.market)}} ${{stock.country || 'N/A'}}</td>
                    <td>${{stock.market_cap_category || 'N/A'}}</td>
                    <td>${{(typeof stock.pe_ratio === 'number') ? stock.pe_ratio.toFixed(2) : 'N/A'}}</td>
                    <td>${{formatDividendYield(stock.dividend_yield)}}</td>
                    <td>${{formatNumber(stock.enterprise_value)}}</td>
                    <td>${{formatNumber(stock.ebit)}}</td>
                    <td>${{formatNumber(stock.current_assets)}}</td>
                    <td>${{formatNumber(stock.current_liabilities)}}</td>
                    <td>${{formatNumber(stock.net_fixed_assets)}}</td>
                    <td style="font-size: 10px;">${{formatLastUpdated(stock.last_updated)}}</td>
                </tr>`;
            }}).join('');
        }}
        
        // Magic Formula score variant selector
        let currentScoreField = 'magic_formula_score'; // Default score field
        let showExcluded = false; // Whether to show excluded companies
        
        function updateScoreField() {{
            const select = document.getElementById('magicFormulaScoreSelect');
            if (select) {{
                currentScoreField = select.value;
                applyScoreFilter(); // Reapply filter with new score field
            }}
        }}
        
        function applyScoreFilter() {{
            // Filter stocks to only show those with valid scores for the selected variant
            // The score variants already have market cap filters built in, so we just filter by valid scores
            // Filter: only show non-excluded stocks with valid scores by default
            const filtered = originalSort.filter(s => {{
                // Exclude default_excluded companies (financial/investment companies)
                const isExcluded = !!(s.default_excluded || s.exclusion_reason);
                if (isExcluded) return false; // Don't include excluded companies in ranking
                
                const score = s[currentScoreField];
                // Show stocks with valid scores (not N/A, not null, not undefined, and is a number)
                return score !== 'N/A' && score !== null && score !== undefined && typeof score === 'number';
            }});
            
            // If showExcluded is true, also include excluded stocks (but only if they have valid scores)
            let filteredExcluded = [];
            if (showExcluded) {{
                filteredExcluded = originalSort.filter(s => {{
                    const isExcluded = !!(s.default_excluded || s.exclusion_reason);
                    if (!isExcluded) return false; // Only excluded stocks
                    const score = s[currentScoreField];
                    return score !== 'N/A' && score !== null && score !== undefined && typeof score === 'number';
                }});
            }}
            
            // Combine included and excluded (if shown)
            const allFiltered = [...filtered, ...filteredExcluded];
            
            // Update filter statistics
            document.getElementById('filteredCount').textContent = filtered.length;
            
            // Sort by selected Magic Formula score variant
            allFiltered.sort((a, b) => {{
                // Excluded stocks go to the end (use default_excluded flag if available)
                const aExcluded = !!(a.default_excluded || a.exclusion_reason);
                const bExcluded = !!(b.default_excluded || b.exclusion_reason);
                if (aExcluded && !bExcluded) return 1;
                if (!aExcluded && bExcluded) return -1;
                
                // Sort by selected Magic Formula score variant
                const aScore = a[currentScoreField];
                const bScore = b[currentScoreField];
                
                // Handle N/A values - put them at the end (shouldn't happen since we filtered, but just in case)
                if ((aScore === 'N/A' || aScore === null || aScore === undefined) && 
                    (bScore === 'N/A' || bScore === null || bScore === undefined)) {{
                    return 0;
                }}
                if (aScore === 'N/A' || aScore === null || aScore === undefined) return 1;
                if (bScore === 'N/A' || bScore === null || bScore === undefined) return -1;
                
                // Both are numbers - lower score is better
                if (typeof aScore === 'number' && typeof bScore === 'number') {{
                    return aScore - bScore;
                }}
                
                return 0;
            }});
            
            currentStocks = allFiltered;
            renderTable(currentStocks);
        }}
        
        // Initialize filter stats and exclusion stats on page load
        function initializeFilterStats() {{
            // Count included stocks (not excluded)
            // Use default_excluded flag if available, fallback to exclusion_reason for backwards compatibility
            const includedStocks = originalSort.filter(s => !(s.default_excluded || s.exclusion_reason));
            const excludedStocks = originalSort.filter(s => s.default_excluded || s.exclusion_reason);
            
            // Update inclusion stats
            document.getElementById('includedCount').textContent = includedStocks.length;
            
            // Update exclusion stats
            const exclusionReasonsDiv = document.getElementById('exclusionReasons');
            if (excludedStocks.length === 0) {{
                exclusionReasonsDiv.innerHTML = '<div>Inga aktier exkluderade</div>';
            }} else {{
                const exclusionCounts = {{}};
                excludedStocks.forEach(s => {{
                    const reason = s.exclusion_reason || 'Okänt skäl';
                    exclusionCounts[reason] = (exclusionCounts[reason] || 0) + 1;
                }});
                
                const statsHtml = Object.entries(exclusionCounts)
                    .sort((a, b) => b[1] - a[1])
                    .map(([reason, count]) => 
                        `<div style="margin: 5px 0;"><strong>${{reason}}:</strong> ${{count}} aktier</div>`
                    ).join('');
                exclusionReasonsDiv.innerHTML = statsHtml;
            }}
        }}
        
        // Preset buttons and excluded toggle
        document.addEventListener('DOMContentLoaded', function() {{
            // Magic Formula score selector
            const scoreSelect = document.getElementById('magicFormulaScoreSelect');
            if (scoreSelect) {{
                scoreSelect.addEventListener('change', updateScoreField);
            }}
            
            // Toggle for showing excluded companies
            const showExcludedToggle = document.getElementById('showExcludedToggle');
            if (showExcludedToggle) {{
                showExcludedToggle.addEventListener('change', function() {{
                    showExcluded = this.checked;
                    applyScoreFilter();
                }});
            }}
        }});
        
        
        let currentSortColumn = null;
        let currentSortDirection = null;
        
        function sortTable(column) {{
            const isAsc = currentSortColumn === column && currentSortDirection === 'asc';
            currentSortColumn = column;
            currentSortDirection = isAsc ? 'desc' : 'asc';
            
            // Clear all sort indicators
            document.querySelectorAll('th').forEach(th => {{
                th.classList.remove('sort-asc', 'sort-desc');
            }});
            
            // Add sort indicator to current column
            const header = document.querySelector(`th[data-sort="${{column}}"]`);
            if (header) {{
                header.classList.add(isAsc ? 'sort-desc' : 'sort-asc');
            }}
            
            // Sort the stocks
            currentStocks.sort((a, b) => {{
                // Excluded stocks always go to the end
                const aExcluded = !!(a.default_excluded || a.exclusion_reason);
                const bExcluded = !!(b.default_excluded || b.exclusion_reason);
                if (aExcluded && !bExcluded) return 1;
                if (!aExcluded && bExcluded) return -1;
                
                let aVal = a[column];
                let bVal = b[column];
                
                // Handle N/A values - put them at the end
                const aIsNA = aVal === 'N/A' || aVal === null || aVal === undefined;
                const bIsNA = bVal === 'N/A' || bVal === null || bVal === undefined;
                if (aIsNA && bIsNA) return 0;
                if (aIsNA) return 1; // N/A goes to end
                if (bIsNA) return -1; // N/A goes to end
                
                // Handle numbers
                if (typeof aVal === 'number' && typeof bVal === 'number') {{
                    // For Magic Formula score: lower is better (asc = ascending = lower first)
                    // For rank fields (ey_rank, roc_rank): lower is better (rank 1 is best)
                    // For other columns: normal sorting
                    if (column === 'magic_formula_score' || column.startsWith('magic_formula_score') ||
                        column === 'ey_rank' || column.startsWith('ey_rank') ||
                        column === 'roc_rank' || column.startsWith('roc_rank')) {{
                        // Lower is better, so ascending means lower first
                        return isAsc ? aVal - bVal : bVal - aVal;
                    }} else {{
                        // Normal sorting for other columns
                        return isAsc ? aVal - bVal : bVal - aVal;
                    }}
                }}
                
                // Handle strings
                if (typeof aVal === 'string' && typeof bVal === 'string') {{
                    return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
                }}
                
                // Mixed types - convert to string
                aVal = String(aVal);
                bVal = String(bVal);
                return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
            }});
            
            renderTable(currentStocks);
        }}
        
        // Add click handlers to all table headers
        document.querySelectorAll('th[data-sort]').forEach(th => {{
            th.addEventListener('click', () => {{
                const column = th.getAttribute('data-sort');
                sortTable(column);
            }});
        }});
        
        // Excluded companies are filtered out by default (showExcluded = false)
        // They can be shown by checking the toggle
        
        // Initialize filter stats first
        initializeFilterStats();
        
        // Set sort indicator on Magic Formula column
        const magicHeader = document.querySelector('th[data-sort="magic_formula_score"]');
        if (magicHeader) {{
            magicHeader.classList.add('sort-asc');
            currentSortColumn = 'magic_formula_score';
            currentSortDirection = 'asc';
        }}
        
        // Apply default score filter on page load
        // This will filter currentStocks and render the table (renderTable is called inside applyScoreFilter)
        applyScoreFilter();
    </script>
</body>
</html>
"""

    return html


def load_history_data():
    """Load historical stock data from JSON file."""
    if not HISTORY_DATA.exists():
        print(f"Warning: {HISTORY_DATA} not found!")
        return {}

    with open(HISTORY_DATA, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_history_html():
    """Generate history.html page with date picker and historical rankings."""

    history = load_history_data()

    # Extract all available dates from history
    all_dates = set()
    for ticker, dates_dict in history.items():
        if isinstance(dates_dict, dict):
            all_dates.update(dates_dict.keys())
        elif isinstance(dates_dict, list):
            # Old format - extract dates from timestamps
            for entry in dates_dict:
                if isinstance(entry, dict) and "timestamp" in entry:
                    try:
                        date_str = entry["timestamp"].split("T")[0]
                        all_dates.add(date_str)
                    except:
                        pass

    # Sort dates descending (newest first)
    sorted_dates = sorted(all_dates, reverse=True)

    html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stockholmsbörsen - Historiska Rankingar | Magic Formula Sverige</title>
    <meta name="description" content="Historiska Magic Formula-rankingar för Stockholmsbörsen. Se hur aktier rankades tidigare.">
    <meta name="keywords" content="Magic Formula, historik, aktier, Stockholmsbörsen">
    <meta name="author" content="Magic Formula Sverige">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            padding: 0;
            margin: 0;
            background: #f8f9fa;
            min-height: 100vh;
        }}
        .page-wrapper {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: white;
            padding: 30px;
            border-radius: 16px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f0f0f0;
        }}
        .nav-links {{
            display: flex;
            gap: 15px;
        }}
        .nav-links a {{
            color: #495057;
            text-decoration: none;
            font-weight: 600;
            padding: 8px 16px;
            border-radius: 8px;
            transition: all 0.2s;
        }}
        .nav-links a:hover {{
            background: #f0f0f0;
            transform: translateY(-1px);
        }}
        h1 {{
            margin: 0 0 10px 0;
            color: #333;
            font-size: 2.2em;
            font-weight: 700;
        }}
        .subtitle {{
            color: #666;
            font-size: 0.95em;
        }}
        .date-selector {{
            display: flex;
            align-items: center;
            gap: 15px;
            margin: 20px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 12px;
        }}
        .date-selector label {{
            font-weight: 600;
            color: white;
        }}
        .date-selector select {{
            padding: 12px 20px;
            font-size: 16px;
            border: 2px solid white;
            border-radius: 8px;
            background: white;
            cursor: pointer;
            font-weight: 600;
            flex: 1;
            max-width: 300px;
        }}
        .date-selector select:hover {{
            border-color: rgba(255,255,255,0.8);
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }}
        #marketCapFilter {{
            margin-top: 15px;
            background: rgba(255,255,255,0.95);
            padding: 15px;
            border-radius: 8px;
        }}
        #marketCapFilter label {{
            display: block;
            font-weight: 600;
            color: #333;
            margin-bottom: 10px;
        }}
        .filter-controls {{
            display: flex;
            gap: 15px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .filter-controls input[type="range"] {{
            flex: 1;
            min-width: 200px;
        }}
        .filter-controls input[type="number"] {{
            padding: 8px 12px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            width: 150px;
        }}
        .preset-btn {{
            margin: 0 5px;
            padding: 4px 12px;
            background: #f0f0f0;
            border: 1px solid #ddd;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }}
        .preset-btn:hover {{
            background: #e0e0e0;
        }}
        .info {{
            margin-top: 15px;
            padding: 10px;
            background: #e7f3ff;
            border-left: 4px solid #212529;
            border-radius: 4px;
        }}
        .table-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow-x: auto;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            font-size: 12px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background: #212529;
            color: white;
            position: sticky;
            top: 0;
            font-weight: 600;
            cursor: pointer;
            padding: 12px 8px;
            z-index: 10;
        }}
        th:hover {{
            background-color: #343a40;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .rank {{
            font-weight: 600;
            color: #495057;
        }}
        .loading {{
            text-align: center;
            padding: 40px;
            color: #666;
        }}
        .back-link {{
            display: inline-block;
            margin-bottom: 20px;
            color: #34495e;
            text-decoration: none;
            font-weight: 600;
        }}
        .back-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="page-wrapper">
    <div class="header">
        <div class="header-top">
            <div>
                <h1>Historiska Rankingar</h1>
                <p class="subtitle">Magic Formula för Stockholmsbörsen</p>
            </div>
            <div class="nav-links">
                <a href="index.html">Hem</a>
                <a href="stocks.html">Aktuella Rankingar</a>
                <a href="history.html" class="active">Historik</a>
                <a href="faq.html">FAQ</a>
            </div>
        </div>
        <div class="date-selector">
            <label for="dateSelect">Välj datum:</label>
            <select id="dateSelect">
                <option value="">-- Välj ett datum --</option>
                {chr(10).join(f'                <option value="{date}">{date}</option>' for date in sorted_dates)}
            </select>
        </div>
        <div id="scoreVariantSelector" style="display: none; margin-top: 15px; padding: 15px; background: rgba(255,255,255,0.95); border-radius: 8px;">
            <label style="display: block; font-weight: 600; color: #333; margin-bottom: 10px;">
                Ranka efter Magic Formula-variant:
            </label>
            <select id="magicFormulaScoreSelectHistory" style="padding: 10px 15px; font-size: 14px; border: 2px solid #ddd; border-radius: 6px; background: white; cursor: pointer; font-weight: 600; width: 100%; max-width: 500px;">
                <option value="magic_formula_score">Standard (exkluderar finansiella bolag)</option>
                <option value="magic_formula_score_100m">≥ 100M SEK börsvärde</option>
                <option value="magic_formula_score_500m">≥ 500M SEK börsvärde</option>
                <option value="magic_formula_score_1b">≥ 1B SEK börsvärde</option>
                <option value="magic_formula_score_5b">≥ 5B SEK börsvärde</option>
            </select>
            <p style="margin-top: 8px; font-size: 12px; color: #666;">Välj vilken Magic Formula-variant som ska användas för ranking. Varje variant har redan börsvärdesfilter inbyggt.</p>
        </div>
        <div class="info" id="infoDiv" style="display: none; margin-top: 15px;">
            <strong>Valt datum:</strong> <span id="selectedDate"></span><br>
            <strong>Kvalificerade aktier:</strong> <span id="eligibleCount">0</span><br>
            <strong>Totalt antal aktier med data:</strong> <span id="totalCount">0</span>
        </div>
    </div>
    
    <div class="table-container">
        <div id="loading" class="loading">Välj ett datum för att visa historiska rankingar</div>
        <table id="rankingTable" style="display: none;">
            <thead>
                <tr>
                    <th>Ordning</th>
                    <th>Ticker</th>
                    <th>Namn</th>
                    <th>Magic Score</th>
                    <th>Pris</th>
                    <th>Börsvärde</th>
                    <th>EBIT</th>
                    <th>Företagsvärde</th>
                    <th>Totala tillgångar</th>
                    <th>Kortfristiga skulder</th>
                    <th>Omsättningstillgångar</th>
                    <th>Nettotillgångar</th>
                </tr>
            </thead>
            <tbody id="rankingBody">
            </tbody>
        </table>
    </div>
    
    <script>
        const historyData = {json.dumps(history, ensure_ascii=False)};
        let stockNames = {{}};
        
        // Load stock names from current_stocks.json
        fetch('data/current_stocks.json')
            .then(response => response.json())
            .then(data => {{
                // Handle both dict and list formats
                const stocks = Array.isArray(data) ? data : Object.values(data);
                stocks.forEach(stock => {{
                    if (stock.ticker) {{
                        stockNames[stock.ticker] = stock.name || 'N/A';
                    }}
                }});
            }})
            .catch(err => {{
                console.warn('Could not load stock names:', err);
            }});
        
        function formatNumber(num) {{
            if (num === 'N/A' || num === null || num === undefined) return 'N/A';
            if (typeof num === 'number') {{
                if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
                if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
                return num.toLocaleString('sv-SE');
            }}
            return num;
        }}
        
        // Magic Formula score variant selector for history
        let currentScoreFieldHistory = 'magic_formula_score'; // Default score field
        
        function updateScoreFieldHistory() {{
            const select = document.getElementById('magicFormulaScoreSelectHistory');
            if (select) {{
                currentScoreFieldHistory = select.value;
                // Recalculate if date is selected
                const dateSelect = document.getElementById('dateSelect');
                if (dateSelect && dateSelect.value) {{
                    displayRankings(dateSelect.value);
                }}
            }}
        }}
        
        function calculateMagicFormulaForDate(dateStr) {{
            // Collect all stocks with data for this date that have valid scores for the selected variant
            const stocksForDate = [];
            
            for (const [ticker, datesDict] of Object.entries(historyData)) {{
                let dateData = null;
                
                if (typeof datesDict === 'object' && datesDict !== null) {{
                    if (datesDict[dateStr]) {{
                        dateData = datesDict[dateStr];
                    }} else if (Array.isArray(datesDict)) {{
                        // Old format - find entry with matching date
                        for (const entry of datesDict) {{
                            if (entry.timestamp && entry.timestamp.startsWith(dateStr)) {{
                                dateData = entry;
                                break;
                            }}
                        }}
                    }}
                }}
                
                if (dateData) {{
                    // Check if stock has valid score for the selected variant
                    const score = dateData[currentScoreFieldHistory];
                    if (score === 'N/A' || score === null || score === undefined || typeof score !== 'number') {{
                        continue; // Skip if no valid score for this variant
                    }}
                    
                    stocksForDate.push({{
                        ticker: ticker,
                        dateData: dateData,
                        magic_score: score
                    }});
                }}
            }}
            
            // Sort by Magic Formula score (lower is better)
            stocksForDate.sort((a, b) => a.magic_score - b.magic_score);
            
            return stocksForDate;
        }}
        
        function displayRankings(dateStr) {{
            const loading = document.getElementById('loading');
            const table = document.getElementById('rankingTable');
            const tbody = document.getElementById('rankingBody');
            const infoDiv = document.getElementById('infoDiv');
            
            if (!dateStr) {{
                loading.style.display = 'block';
                table.style.display = 'none';
                infoDiv.style.display = 'none';
                document.getElementById('scoreVariantSelector').style.display = 'none';
                return;
            }}
            
            loading.textContent = 'Beräknar rankingar...';
            loading.style.display = 'block';
            table.style.display = 'none';
            infoDiv.style.display = 'block';
            
            document.getElementById('selectedDate').textContent = dateStr;
            
            // Show score variant selector when date is selected
            document.getElementById('scoreVariantSelector').style.display = 'block';
            
            // Wait a bit for stock names to load if they haven't yet
            setTimeout(() => {{
                const rankings = calculateMagicFormulaForDate(dateStr);
                
                if (!rankings || rankings.length === 0) {{
                    tbody.innerHTML = '<tr><td colspan="13" style="text-align: center; padding: 40px; color: #666;">Inga kvalificerade aktier hittades för detta datum</td></tr>';
                    document.getElementById('eligibleCount').textContent = '0';
                    document.getElementById('totalCount').textContent = '0';
                    loading.style.display = 'none';
                    table.style.display = 'table';
                    return;
                }}
                
                document.getElementById('eligibleCount').textContent = rankings.length;
                
                // Count total stocks with data for this date
                let totalWithData = 0;
                for (const [ticker, datesDict] of Object.entries(historyData)) {{
                    if (typeof datesDict === 'object' && datesDict !== null) {{
                        if (datesDict[dateStr]) {{
                            totalWithData++;
                        }} else if (Array.isArray(datesDict)) {{
                            for (const entry of datesDict) {{
                                if (entry.timestamp && entry.timestamp.startsWith(dateStr)) {{
                                    totalWithData++;
                                    break;
                                }}
                            }}
                        }}
                    }}
                }}
                document.getElementById('totalCount').textContent = totalWithData;
                
                tbody.innerHTML = rankings.map((item, index) => {{
                    const d = item.dateData;
                    const name = stockNames[item.ticker] || 'N/A';
                    const magicScore = d[currentScoreFieldHistory];
                    const magicScoreDisplay = (magicScore !== 'N/A' && magicScore !== null && magicScore !== undefined && typeof magicScore === 'number')
                        ? `<strong style="color: #212529;">${{magicScore}}</strong>`
                        : '<span style="color: #6c757d;">N/A</span>';
                    return `<tr>
                        <td class="rank">#${{index + 1}}</td>
                        <td><strong>${{item.ticker}}</strong></td>
                        <td>${{name}}</td>
                        <td>${{magicScoreDisplay}}</td>
                        <td>${{formatNumber(d.price)}}</td>
                        <td>${{formatNumber(d.market_cap)}}</td>
                        <td>${{formatNumber(d.ebit)}}</td>
                        <td>${{formatNumber(d.enterprise_value)}}</td>
                        <td>${{formatNumber(d.total_assets)}}</td>
                        <td>${{formatNumber(d.current_liabilities)}}</td>
                        <td>${{formatNumber(d.current_assets)}}</td>
                        <td>${{formatNumber(d.net_fixed_assets)}}</td>
                    </tr>`;
                }}).join('');
                
                loading.style.display = 'none';
                table.style.display = 'table';
            }}, 100);
        }}
        
        document.getElementById('dateSelect').addEventListener('change', (e) => {{
            displayRankings(e.target.value);
        }});
        
        // Score variant selector for history
        document.addEventListener('DOMContentLoaded', function() {{
            const scoreSelect = document.getElementById('magicFormulaScoreSelectHistory');
            if (scoreSelect) {{
                scoreSelect.addEventListener('change', updateScoreFieldHistory);
            }}
        }});
    </script>
</body>
</html>
"""

    return html


def main():
    """Main function."""
    print("=" * 60)
    print("Generating HTML from Stock Data")
    print("=" * 60)

    print(f"\nLoading stock data from {STOCKS_DATA}...")
    stocks = load_stocks_data()
    print(f"✓ Loaded {len(stocks)} stocks")

    print("\nGenerating stocks.html...")
    html = generate_html(stocks)

    print(f"\nSaving to {OUTPUT_HTML}...")
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"✓ Generated {OUTPUT_HTML}")

    print("\nGenerating history.html...")
    history_html = generate_history_html()

    print(f"\nSaving to {HISTORY_HTML}...")
    HISTORY_HTML.write_text(history_html, encoding="utf-8")
    print(f"✓ Generated {HISTORY_HTML}")

    print("\n✓ All HTML files generated successfully!")
    print("\nFiles created:")
    print(f"  - index.html (landing page)")
    print(f"  - stocks.html (current rankings)")
    print(f"  - history.html (historical rankings)")
    print(f"  - faq.html (FAQ and guide)")
    print("\nDone! Open index.html in your browser.")


if __name__ == "__main__":
    main()
