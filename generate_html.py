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
    """Get country code based on country or market."""
    if country == "N/A" and market == "N/A":
        return ""

    # Map countries to codes
    country_codes = {
        "Sweden": "SE",
        "Norway": "NO",
        "Denmark": "DK",
        "Finland": "FI",
        "United Kingdom": "GB",
        "United States": "US",
        "Germany": "DE",
        "France": "FR",
        "Netherlands": "NL",
        "Switzerland": "CH",
        "Iceland": "IS",
    }

    # Check country first
    if country and country != "N/A":
        country_lower = country.lower()
        for key, code in country_codes.items():
            if key.lower() in country_lower:
                return code

    # Fallback to market
    if market and market != "N/A":
        market_lower = market.lower()
        if "se_" in market_lower or "stockholm" in market_lower:
            return "SE"
        elif "no_" in market_lower or "oslo" in market_lower:
            return "NO"
        elif "dk_" in market_lower or "copenhagen" in market_lower:
            return "DK"
        elif "fi_" in market_lower or "helsinki" in market_lower:
            return "FI"
        elif "uk_" in market_lower or "london" in market_lower:
            return "GB"
        elif (
            "us_" in market_lower or "nyse" in market_lower or "nasdaq" in market_lower
        ):
            return "US"

    return ""  # No default


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
        item["stock"]["magic_formula_reason"] = None  # Clear reason for valid scores

    return stocks


def generate_html(stocks):
    """Generate simple HTML table."""

    # Note: Magic Formula scores should already be calculated and saved in current_stocks.json
    # by fetch_stocks.py. We recalculate here to ensure they're up to date.
    stocks = calculate_magic_formula_scores(stocks)

    # Sort by market cap
    stocks_sorted = sorted(
        stocks,
        key=lambda x: (
            x.get("market_cap", 0)
            if isinstance(x.get("market_cap"), (int, float))
            else 0
        ),
        reverse=True,
    )

    # Generate table rows
    rows = []
    for stock in stocks_sorted:
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
                <td><strong>{stock.get('ticker', 'N/A')}</strong></td>
                <td>{stock.get('name', 'N/A')}</td>
                <td colspan="20" style="color: #856404; font-weight: 600;">
                    <span style="color: #e74c3c;">⚠</span> {has_error}
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
                <td><strong>{stock.get('ticker', 'N/A')}</strong></td>
                <td>{stock.get('name', 'N/A')}</td>
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
                <td>
                    <strong>{stock.get('magic_formula_score', 'N/A')}</strong>
                    {f"<br><small style='color: #666;'>{stock.get('magic_formula_reason', '')}</small>" if stock.get('magic_formula_score') == 'N/A' and stock.get('magic_formula_reason') else ''}
                </td>
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
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            padding: 0;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            color: #667eea;
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
            color: #34495e;
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            color: #667eea;
        }}
        th.sort-desc::after {{
            content: ' ▼';
            font-size: 10px;
            color: #667eea;
        }}
        #eligibilityStats {{
            margin-top: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
            display: none;
        }}
        #eligibilityStats.show {{
            display: block;
        }}
        .stat-group {{
            margin-bottom: 10px;
        }}
        .stat-group strong {{
            color: #667eea;
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
        #magicFormulaBtn:hover {{
            box-shadow: 0 6px 20px rgba(0,0,0,0.3) !important;
        }}
        #resetSortBtn:hover {{
            background: rgba(255,255,255,0.3) !important;
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
            background: #667eea;
            border-radius: 50%;
            cursor: pointer;
        }}
        input[type="range"]::-moz-range-thumb {{
            width: 18px;
            height: 18px;
            background: #667eea;
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
        <div style="margin-top: 20px; padding: 20px; background: #34495e; border-radius: 12px;">
            <div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin-bottom: 15px;">
                <button id="magicFormulaBtn" style="padding: 12px 24px; font-size: 16px; background: white; color: #2c3e50; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; box-shadow: 0 2px 8px rgba(0,0,0,0.15); transition: all 0.2s;">
                    Rangordna efter Magic Formula
                </button>
                <button id="resetSortBtn" style="padding: 12px 24px; font-size: 16px; background: transparent; color: white; border: 2px solid white; border-radius: 8px; cursor: pointer; font-weight: 500; transition: all 0.2s;">
                    Återställ sortering
                </button>
            </div>
            <div id="marketCapFilter" style="display: none; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; margin-top: 15px;">
                <label style="display: block; font-weight: 600; color: #333; margin-bottom: 10px;">
                    Filtrera efter minsta börsvärde (SEK):
                </label>
                <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
                    <input type="range" id="marketCapSlider" min="0" max="100" value="0" step="1" style="flex: 1; min-width: 200px;">
                    <input type="number" id="marketCapInput" value="0" min="0" step="100000000" style="padding: 8px 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; width: 150px;">
                    <span id="marketCapDisplay" style="font-weight: 600; color: #2c3e50; min-width: 120px;">Ingen gräns</span>
                </div>
                <div style="margin-top: 10px; font-size: 12px; color: #666;">
                    <span>Förslag: </span>
                    <button class="preset-btn" data-value="1000000000" style="margin: 0 5px; padding: 4px 12px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 12px;">1000M SEK</button>
                    <button class="preset-btn" data-value="5000000000" style="margin: 0 5px; padding: 4px 12px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 12px;">5000M SEK</button>
                    <button class="preset-btn" data-value="15000000000" style="margin: 0 5px; padding: 4px 12px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 12px;">15000M SEK</button>
                </div>
            </div>
        </div>
        <div id="eligibilityStats">
            <div class="stat-group">
                <strong>Kvalificerade för Magic Formula:</strong> <span id="eligibleCount">0</span>
            </div>
            <div class="stat-group">
                <strong>Ej kvalificerade:</strong> <span id="nonEligibleCount">0</span>
                <div class="reason-list" id="nonEligibleReasons"></div>
            </div>
        </div>
    </div>
    
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th data-sort="ticker">Ticker</th>
                    <th data-sort="name">Namn</th>
                    <th data-sort="magic_formula_score">Magic Score</th>
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
                        <td><strong>${{stock.ticker || 'N/A'}}</strong></td>
                        <td>${{stock.name || 'N/A'}}</td>
                        <td colspan="20" style="color: #856404; font-weight: 600;">
                            <span style="color: #e74c3c;">⚠</span> ${{hasError}}
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
                    
                    const countryCodes = {{
                        'sweden': 'SE',
                        'norway': 'NO',
                        'denmark': 'DK',
                        'finland': 'FI',
                        'united kingdom': 'GB',
                        'united states': 'US',
                        'germany': 'DE',
                        'france': 'FR',
                        'netherlands': 'NL',
                        'switzerland': 'CH',
                        'iceland': 'IS',
                    }};
                    
                    // Check country first
                    if (country && country !== 'N/A') {{
                        const countryLower = country.toLowerCase();
                        for (const [key, code] of Object.entries(countryCodes)) {{
                            if (countryLower.includes(key)) {{
                                return code;
                            }}
                        }}
                    }}
                    
                    // Fallback to market
                    if (market && market !== 'N/A') {{
                        const marketLower = market.toLowerCase();
                        if (marketLower.includes('se_') || marketLower.includes('stockholm')) {{
                            return 'SE';
                        }} else if (marketLower.includes('no_') || marketLower.includes('oslo')) {{
                            return 'NO';
                        }} else if (marketLower.includes('dk_') || marketLower.includes('copenhagen')) {{
                            return 'DK';
                        }} else if (marketLower.includes('fi_') || marketLower.includes('helsinki')) {{
                            return 'FI';
                        }} else if (marketLower.includes('uk_') || marketLower.includes('london')) {{
                            return 'GB';
                        }} else if (marketLower.includes('us_') || marketLower.includes('nyse') || marketLower.includes('nasdaq')) {{
                            return 'US';
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
                
                // Format Magic Formula score for display next to name
                const magicScore = stock.magic_formula_score;
                const magicScoreDisplay = magicScore !== undefined && magicScore !== null && magicScore !== 'N/A' && typeof magicScore === 'number'
                    ? `<strong style="color: #2c3e50;">${{magicScore}}</strong>`
                    : '';
                const magicReasonDisplay = magicScore === 'N/A' && stock.magic_formula_reason
                    ? `<br><small style="color: #999; font-size: 10px; margin-left: 10px;">(${{stock.magic_formula_reason}})</small>`
                    : '';
                
                return `<tr>
                    <td><strong>${{stock.ticker || 'N/A'}}</strong></td>
                    <td>${{stock.name || 'N/A'}}${{magicScoreDisplay}}${{magicReasonDisplay}}</td>
                    <td>${{priceStr}} ${{stock.currency || 'SEK'}}</td>
                    <td class="${{changeClass}}">${{changeStr}}</td>
                    <td class="${{changeClass}}">${{changePctStr}}</td>
                    <td>${{formatNumber(stock.volume)}}</td>
                    <td>${{formatNumber(stock.market_cap)}}</td>
                    <td>${{stock.sector || 'N/A'}}</td>
                    <td>${{stock.industry || 'N/A'}}</td>
                    <td>${{getCountryFlag(stock.country, stock.market) ? getCountryFlag(stock.country, stock.market) + ' ' : ''}}${{stock.country || 'N/A'}}</td>
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
        
        // Market cap filter
        let minMarketCap = 0;
        
        function updateMarketCapFilter() {{
            const slider = document.getElementById('marketCapSlider');
            const input = document.getElementById('marketCapInput');
            const display = document.getElementById('marketCapDisplay');
            
            // Sync slider and input (slider is 0-100 representing 0-100B SEK)
            const value = parseFloat(slider.value) * 1000000000; // Convert to SEK
            input.value = Math.round(value);
            minMarketCap = value;
            
            if (value === 0) {{
                display.textContent = 'Ingen gräns';
            }} else {{
                display.textContent = (value / 1000000).toFixed(0) + 'M SEK';
            }}
            
            // Recalculate if already ranked
            if (document.getElementById('eligibilityStats').classList.contains('show')) {{
                calculateMagicFormula();
            }}
        }}
        
        // Preset buttons
        document.addEventListener('DOMContentLoaded', function() {{
            document.querySelectorAll('.preset-btn').forEach(btn => {{
                btn.addEventListener('click', function() {{
                    const value = parseFloat(this.dataset.value);
                    document.getElementById('marketCapSlider').value = value / 1000000000;
                    document.getElementById('marketCapInput').value = value;
                    updateMarketCapFilter();
                }});
            }});
            
            const slider = document.getElementById('marketCapSlider');
            const input = document.getElementById('marketCapInput');
            
            if (slider) {{
                slider.addEventListener('input', updateMarketCapFilter);
            }}
            if (input) {{
                input.addEventListener('input', function() {{
                    const value = parseFloat(this.value) || 0;
                    document.getElementById('marketCapSlider').value = Math.min(100, value / 1000000000);
                    updateMarketCapFilter();
                }});
            }}
        }});
        
        function calculateMagicFormula() {{
            // Categorize all stocks
            const eligible = [];
            const nonEligible = {{
                'Fel vid hämtning av data': [],
                'Finansiella tjänster': [],
                'Fastigheter': [],
                'Saknar EBIT': [],
                'Saknar företagsvärde': [],
                'Saknar totala tillgångar': [],
                'Saknar kortfristiga skulder': [],
                'Negativ EBIT (förluster)': [],
                'Negativ/noll avkastning på intäkter': [],
                'Negativ/noll avkastning på kapital': [],
                'Kan inte beräkna': [],
                'Beräkningsfel': []
            }};
            
            allStocks.forEach(s => {{
                if (s.error) {{
                    nonEligible['Fel vid hämtning av data'].push(s);
                    return;
                }}
                
                const sector = (s.sector || '').toLowerCase();
                if (sector === 'financial services') {{
                    nonEligible['Finansiella tjänster'].push(s);
                    return;
                }}
                if (sector === 'real estate') {{
                    nonEligible['Fastigheter'].push(s);
                    return;
                }}
                
                // Check market cap filter
                const marketCap = s.market_cap;
                if (minMarketCap > 0 && (marketCap === 'N/A' || marketCap === null || marketCap === undefined || typeof marketCap !== 'number' || marketCap < minMarketCap)) {{
                    // Skip if below minimum market cap
                    return;
                }}
                
                const score = s.magic_formula_score;
                if (score !== undefined && score !== null && score !== 'N/A' && typeof score === 'number') {{
                    eligible.push(s);
                }} else {{
                    const reason = s.magic_formula_reason || 'Okänt skäl';
                    // Reason is already in Swedish from Python, but handle both for backward compatibility
                    if (nonEligible[reason]) {{
                        nonEligible[reason].push(s);
                    }} else {{
                        nonEligible['Kan inte beräkna'].push(s);
                    }}
                }}
            }});
            
            // Sort eligible by Magic Formula score (lower is better)
            eligible.sort((a, b) => a.magic_formula_score - b.magic_formula_score);
            
            // Display statistics
            const statsDiv = document.getElementById('eligibilityStats');
            document.getElementById('eligibleCount').textContent = eligible.length;
            
            let totalNonEligible = 0;
            const reasonsHtml = [];
            for (const [reason, stocks] of Object.entries(nonEligible)) {{
                if (stocks.length > 0) {{
                    totalNonEligible += stocks.length;
                    reasonsHtml.push(`<div class="reason-item"><strong>${{reason}}:</strong> ${{stocks.length}} aktier</div>`);
                }}
            }}
            document.getElementById('nonEligibleCount').textContent = totalNonEligible;
            document.getElementById('nonEligibleReasons').innerHTML = reasonsHtml.join('');
            statsDiv.classList.add('show');
            
            // Re-render table with ranked stocks
            currentStocks = eligible;
            renderTable(currentStocks);
            
            // Show market cap filter
            document.getElementById('marketCapFilter').style.display = 'block';
            
            // Update button text
            const filterText = minMarketCap > 0 ? ` (Min: ${{(minMarketCap / 1000000).toFixed(0)}}M SEK)` : '';
            document.getElementById('magicFormulaBtn').textContent = 
                `Magic Formula (Visar ${{eligible.length}} rankade aktier${{filterText}})`;
        }}
        
        function resetSort() {{
            currentStocks = [...originalSort];
            renderTable(currentStocks);
            document.getElementById('magicFormulaBtn').textContent = 'Rangordna efter Magic Formula';
            document.getElementById('eligibilityStats').classList.remove('show');
            document.getElementById('marketCapFilter').style.display = 'none';
            minMarketCap = 0;
            document.getElementById('marketCapSlider').value = 0;
            document.getElementById('marketCapInput').value = 0;
            updateMarketCapFilter();
            // Clear sort indicators
            document.querySelectorAll('th').forEach(th => {{
                th.classList.remove('sort-asc', 'sort-desc');
            }});
        }}
        
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
                let aVal = a[column];
                let bVal = b[column];
                
                // Handle N/A values
                if (aVal === 'N/A' || aVal === null || aVal === undefined) aVal = isAsc ? -Infinity : Infinity;
                if (bVal === 'N/A' || bVal === null || bVal === undefined) bVal = isAsc ? -Infinity : Infinity;
                
                // Handle numbers
                if (typeof aVal === 'number' && typeof bVal === 'number') {{
                    return isAsc ? bVal - aVal : aVal - bVal;
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
        
        document.getElementById('magicFormulaBtn').addEventListener('click', calculateMagicFormula);
        document.getElementById('resetSortBtn').addEventListener('click', resetSort);
        
        // Initial render with default sort by Magic Formula
        // Sort by Magic Formula score (ascending - lower is better)
        currentStocks.sort((a, b) => {{
            const aScore = a.magic_formula_score;
            const bScore = b.magic_formula_score;
            
            // Handle N/A values - put them at the end
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
        
        // Set sort indicator on Magic Formula column
        const magicHeader = document.querySelector('th[data-sort="magic_formula_score"]');
        if (magicHeader) {{
            magicHeader.classList.add('sort-asc');
            currentSortColumn = 'magic_formula_score';
            currentSortDirection = 'asc';
        }}
        
        renderTable(currentStocks);
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
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            padding: 0;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            color: #667eea;
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            border-left: 4px solid #667eea;
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            position: sticky;
            top: 0;
            font-weight: 600;
            cursor: pointer;
            padding: 12px 8px;
            z-index: 10;
        }}
        th:hover {{
            background-color: #34495e;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .rank {{
            font-weight: 600;
            color: #34495e;
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
        <div id="marketCapFilter" style="display: none;">
            <label>Filtrera efter minsta börsvärde (SEK):</label>
            <div class="filter-controls">
                <input type="range" id="marketCapSlider" min="0" max="100" value="0" step="1">
                <input type="number" id="marketCapInput" value="0" min="0" step="100000000">
                <span id="marketCapDisplay" style="font-weight: 600; color: #667eea; min-width: 120px;">Ingen gräns</span>
            </div>
            <div style="margin-top: 10px; font-size: 12px; color: #666;">
                <span>Förslag: </span>
                <button class="preset-btn" data-value="1000000000">1000M SEK</button>
                <button class="preset-btn" data-value="5000000000">5000M SEK</button>
                <button class="preset-btn" data-value="15000000000">15000M SEK</button>
            </div>
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
                    <th>Rank</th>
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
        
        // Market cap filter for history
        let minMarketCapHistory = 0;
        
        function updateMarketCapFilterHistory() {{
            const slider = document.getElementById('marketCapSlider');
            const input = document.getElementById('marketCapInput');
            const display = document.getElementById('marketCapDisplay');
            
            if (!slider || !input || !display) return;
            
            const value = parseFloat(slider.value) * 1000000000;
            input.value = Math.round(value);
            minMarketCapHistory = value;
            
            if (value === 0) {{
                display.textContent = 'Ingen gräns';
            }} else {{
                display.textContent = (value / 1000000).toFixed(0) + 'M SEK';
            }}
            
            // Recalculate if date is selected
            const dateSelect = document.getElementById('dateSelect');
            if (dateSelect && dateSelect.value) {{
                displayRankings(dateSelect.value);
            }}
        }}
        
        function calculateMagicFormulaForDate(dateStr) {{
            // Collect all stocks with data for this date
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
                    // Check market cap filter
                    const marketCap = dateData.market_cap;
                    if (minMarketCapHistory > 0 && (marketCap === 'N/A' || marketCap === null || marketCap === undefined || typeof marketCap !== 'number' || marketCap < minMarketCapHistory)) {{
                        continue; // Skip if below minimum market cap
                    }}
                    
                    // Check if stock is eligible for Magic Formula
                    const ebit = dateData.ebit;
                    const ev = dateData.enterprise_value;
                    const totalAssets = dateData.total_assets;
                    const currentLiabilities = dateData.current_liabilities;
                    
                    // Skip if missing required fields
                    if (ebit === 'N/A' || ebit === null || ebit === undefined) continue;
                    if (ev === 'N/A' || ev === null || ev === undefined) continue;
                    if (totalAssets === 'N/A' || totalAssets === null || totalAssets === undefined) continue;
                    if (currentLiabilities === 'N/A' || currentLiabilities === null || currentLiabilities === undefined) continue;
                    
                    // Skip if negative EBIT
                    if (typeof ebit === 'number' && ebit < 0) continue;
                    
                    // Calculate Earnings Yield
                    let ey = null;
                    if (typeof ev === 'number' && ev > 0 && typeof ebit === 'number') {{
                        ey = ebit / ev;
                        if (ey <= 0) continue;
                    }} else {{
                        continue;
                    }}
                    
                    // Calculate Return on Capital using: EBIT / (Net Fixed Assets + Net Working Capital)
                    // where Net Working Capital = Current Assets - Current Liabilities
                    const netFixedAssets = dateData.net_fixed_assets;
                    const currentAssets = dateData.current_assets;
                    
                    if (netFixedAssets === 'N/A' || netFixedAssets === null || netFixedAssets === undefined) continue;
                    if (currentAssets === 'N/A' || currentAssets === null || currentAssets === undefined) continue;
                    
                    let roc = null;
                    if (typeof netFixedAssets === 'number' && typeof currentAssets === 'number' && typeof currentLiabilities === 'number') {{
                        const netWorkingCapital = currentAssets - currentLiabilities;
                        const investedCapital = netFixedAssets + netWorkingCapital;
                        if (investedCapital > 0 && typeof ebit === 'number') {{
                            roc = ebit / investedCapital;
                            if (roc <= 0) continue;
                        }} else {{
                            continue;
                        }}
                    }} else {{
                        continue;
                    }}
                    
                    stocksForDate.push({{
                        ticker: ticker,
                        dateData: dateData,
                        ey: ey,
                        roc: roc
                    }});
                }}
            }}
            
            // Rank by Earnings Yield (higher is better)
            stocksForDate.sort((a, b) => b.ey - a.ey);
            stocksForDate.forEach((item, idx) => {{
                item.ey_rank = idx + 1;
            }});
            
            // Rank by Return on Capital (higher is better)
            stocksForDate.sort((a, b) => b.roc - a.roc);
            stocksForDate.forEach((item, idx) => {{
                item.roc_rank = idx + 1;
            }});
            
            // Calculate combined score (lower is better)
            stocksForDate.forEach(item => {{
                item.magic_score = item.ey_rank + item.roc_rank;
            }});
            
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
                document.getElementById('marketCapFilter').style.display = 'none';
                return;
            }}
            
            loading.textContent = 'Beräknar rankingar...';
            loading.style.display = 'block';
            table.style.display = 'none';
            infoDiv.style.display = 'block';
            
            document.getElementById('selectedDate').textContent = dateStr;
            
            // Show market cap filter when date is selected
            document.getElementById('marketCapFilter').style.display = 'block';
            
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
                    const magicScoreDisplay = `<strong style="color: #667eea;">${{item.magic_score}}</strong>`;
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
        
        // Market cap filter controls
        document.addEventListener('DOMContentLoaded', function() {{
            const slider = document.getElementById('marketCapSlider');
            const input = document.getElementById('marketCapInput');
            
            if (slider) {{
                slider.addEventListener('input', updateMarketCapFilterHistory);
            }}
            if (input) {{
                input.addEventListener('input', function() {{
                    const value = parseFloat(this.value) || 0;
                    if (slider) {{
                        slider.value = Math.min(100, value / 1000000000);
                    }}
                    updateMarketCapFilterHistory();
                }});
            }}
            
            // Preset buttons
            document.querySelectorAll('.preset-btn').forEach(btn => {{
                btn.addEventListener('click', function() {{
                    const value = parseFloat(this.dataset.value);
                    if (slider) slider.value = value / 1000000000;
                    if (input) input.value = value;
                    updateMarketCapFilterHistory();
                }});
            }});
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
