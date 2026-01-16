# Stockholm Stock Exchange Stock Tracker

A beautiful, responsive web page that displays real-time stock data from the Stockholm Stock Exchange (Nasdaq Stockholm) using yfinance.

## Features

- 📊 Real-time stock prices from Stockholm Stock Exchange
- 🔍 Search functionality to filter stocks by ticker or company name
- 📈 Sortable columns (price, change, volume, market cap, etc.)
- 📱 Fully responsive design that works on mobile and desktop
- 🎨 Modern, beautiful UI with gradient backgrounds
- ⚡ Fast loading with pre-generated static HTML
- 🔄 Automatic daily updates via GitHub Actions

## How It Works

This project uses a Python script to fetch stock data from yfinance and generates a static HTML page. Since GitHub Pages only hosts static files, the Python script runs via GitHub Actions to update the data daily.

## Setup

1. **Clone this repository** or use it as a template

2. **Install Python dependencies** (for local testing):
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the script locally** (optional):
   ```bash
   python fetch_stocks.py
   ```
   This will generate `index.html` with current stock data.

## GitHub Pages Deployment

1. **Push this repository to GitHub**

2. **Enable GitHub Pages**:
   - Go to your repository Settings → Pages
   - Select the source branch (usually `main` or `master`)
   - Select the `/ (root)` folder
   - Click Save

3. **Enable GitHub Actions**:
   - Go to Settings → Actions → General
   - Under "Workflow permissions", select "Read and write permissions"
   - Check "Allow GitHub Actions to create and approve pull requests"
   - Click Save

4. **Your site will be available at**:
   `https://<your-username>.github.io/<repository-name>/`

## Automatic Updates

The GitHub Actions workflow (`.github/workflows/update-stocks.yml`) will:
- Run daily at 6:00 AM UTC
- Fetch the latest stock data
- Generate a new `index.html` file
- Commit and push the changes automatically

You can also manually trigger the workflow from the Actions tab in your GitHub repository.

## Customization

### Adding More Stocks

The script automatically fetches stocks from Stockholm Stock Exchange using `pytickersymbols`. It pulls from Large Cap and Mid Cap indices:
- OMX Stockholm 30 (Large Cap)
- OMX Stockholm Mid Cap

If you want to add specific tickers manually, you can modify the `get_stockholm_tickers()` function in `fetch_stocks.py` or add them to the fallback list.

### Changing Update Schedule

Edit `.github/workflows/update-stocks.yml` and modify the cron schedule:
```yaml
- cron: '0 6 * * *'  # Daily at 6 AM UTC
```

Cron format: `minute hour day month day-of-week`

### Styling

The HTML template includes embedded CSS. You can modify the styles in the `<style>` section of the generated HTML, or extract it to a separate CSS file.

## Requirements

- Python 3.8+
- yfinance library
- GitHub account (for hosting)

## License

MIT License - feel free to use and modify as needed!

## Notes

- Stock data is fetched from yfinance, which may have rate limits
- The script includes a 0.5 second delay between requests to be respectful
- Some stocks may not be available or may return errors - these are displayed in the table
- Market data is only available during trading hours
# magic-formula
