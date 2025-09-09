# FTMarkets

[![PyPI version](https://badge.fury.io/py/ftgo.svg)](https://badge.fury.io/py/ftgo)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python library for fetching financial data from Financial Times Markets, including historical stock prices, ETF holdings, fund profiles, and allocation breakdowns.

## Features

- **Historical Data**: Fetch historical OHLCV data for stocks and ETFs
- **Holdings Data**: Get ETF/fund holdings, asset allocation, and sector breakdowns
- **Fund Profiles**: Access fund information, statistics, and investment details
- **Symbol Search**: Find FT Markets XIDs by ticker symbols
- **Concurrent Processing**: Fast data retrieval using multithreading
- **Pandas Integration**: Returns data as pandas DataFrames for easy analysis

## Installation

```bash
pip install ftgo
```

## Quick Start

```python
from ftgo import search_securities, get_xid, get_historical_prices, get_holdings

# Search for a security
results = search_securities('AAPL')
print(results)

# Get XID for a ticker
xid = get_xid('AAPL')

# Fetch historical data
df = get_historical_prices(xid, "01012024", "31012024")
print(df.head())

# Get ETF holdings
spy_xid = get_xid('SPY')
holdings = get_holdings(spy_xid, "top_holdings")
print(holdings)
```

## API Reference

### Search Functions

#### `search_securities(query)`

Search for securities on FT Markets.

**Parameters:**
- `query` (str): Search term for securities (ticker symbol or company name)

**Returns:** pandas.DataFrame with search results containing xid, name, symbol, asset_class, url

```python
# Search for Apple
results = search_securities('Apple')
print(results)

# Search by ticker
results = search_securities('AAPL')
```

#### `get_xid(ticker, display_mode="first")`

Get FT Markets XID for given ticker symbol.

**Parameters:**
- `ticker` (str): Ticker symbol
- `display_mode` (str): "first" to return first match XID, "all" to return all matches

**Returns:** String XID (if display_mode="first") or DataFrame (if display_mode="all")

```python
# Get XID for Apple
xid = get_xid('AAPL')
print(xid)  # Returns XID string

# Get all matches
all_results = get_xid('AAPL', display_mode='all')
print(all_results)
```

### Historical Data

#### `get_historical_prices(xid, date_from, date_to)`

Get historical price data for a security with full OHLCV data.

**Parameters:**
- `xid` (str): The FT Markets XID
- `date_from` (str): Start date in DDMMYYYY format (e.g., "01012024")
- `date_to` (str): End date in DDMMYYYY format (e.g., "31122024")

**Returns:** pandas.DataFrame with columns: date, open, high, low, close, volume

```python
xid = get_xid('AAPL')
df = get_historical_prices(xid, "01012024", "31012024")
print(df.head())
```

#### `get_multiple_historical_prices(xids, date_from, date_to)`

Get historical data for multiple securities concurrently.

**Parameters:**
- `xids` (list): List of FT Markets XIDs
- `date_from` (str): Start date in DDMMYYYY format
- `date_to` (str): End date in DDMMYYYY format

**Returns:** pandas.DataFrame with concatenated data for all securities

```python
xids = [get_xid('AAPL'), get_xid('MSFT')]
df = get_multiple_historical_prices(xids, "01012024", "31012024")
```

### Holdings Data

#### `get_holdings(xid, holdings_type="all")`

Get holdings and allocation data for ETFs and funds.

**Parameters:**
- `xid` (str): The FT Markets XID
- `holdings_type` (str): Type of holdings data:
  - `"asset_allocation"`: Asset class breakdown (stocks, bonds, cash)
  - `"sector_weights"`: Sector allocation
  - `"geographic_allocation"`: Geographic allocation
  - `"top_holdings"`: Top holdings by weight
  - `"all"`: All holdings data types as a tuple

**Returns:** pandas.DataFrame or tuple of DataFrames

```python
# Get top holdings for SPY ETF
spy_xid = get_xid('SPY')
top_holdings = get_holdings(spy_xid, "top_holdings")

# Get asset allocation
allocation = get_holdings(spy_xid, "asset_allocation")

# Get all holdings data
all_data = get_holdings(spy_xid, "all")
asset_alloc, sectors, regions, holdings = all_data
```

#### `get_fund_breakdown(xid)`

Get complete fund breakdown with all allocation data.

**Parameters:**
- `xid` (str): The FT Markets XID

**Returns:** Dictionary with all DataFrames

```python
qqq_xid = get_xid('QQQ')
breakdown = get_fund_breakdown(qqq_xid)
print(breakdown['asset_allocation'])
print(breakdown['top_holdings'])
```

### Fund Profile Data

#### `get_fund_profile(xid)`

Get profile and investment information for ETFs and funds.

**Parameters:**
- `xid` (str): The FT Markets XID

**Returns:** pandas.DataFrame with Field and Value columns

```python
xid = get_xid('SPY')
profile = get_fund_profile(xid)
print(profile)

# Filter for specific information
fees = profile[profile['Field'].str.contains('fee', case=False)]
```

#### `get_fund_stats(xid)`

Get fund profile data as a dictionary for easy access.

**Parameters:**
- `xid` (str): The FT Markets XID

**Returns:** Dictionary with all available fund fields and values

```python
xid = get_xid('QQQ')
stats = get_fund_stats(xid)

# Access any available field safely
inception = stats.get('Inception date', 'Not available')
fees = stats.get('Ongoing charge', 'Not available')
```

#### `get_available_fields(xid)`

Get list of all available profile fields for a fund.

**Parameters:**
- `xid` (str): The FT Markets XID

**Returns:** List of all field names available

```python
xid = get_xid('SPY')
fields = get_available_fields(xid)
print("Available fields:")
for field in fields:
    print(f"  - {field}")
```

#### `search_profile_field(xid, search_term)`

Search for specific fields in the fund profile data.

**Parameters:**
- `xid` (str): The FT Markets XID
- `search_term` (str): Term to search for in field names (case-insensitive)

**Returns:** pandas.DataFrame with matching fields and values

```python
xid = get_xid('SPY')
fees = search_profile_field(xid, 'fee')
inception = search_profile_field(xid, 'inception')
```

## Complete Example

```python
from ftgo import get_xid, get_historical_prices, get_holdings, get_fund_profile
import matplotlib.pyplot as plt

# Search for QQQ ETF
qqq_xid = get_xid('QQQ')

# Get 1 year of historical data
historical_data = get_historical_prices(qqq_xid, "01012023", "31122023")

# Get fund information
profile = get_fund_profile(qqq_xid)
top_holdings = get_holdings(qqq_xid, "top_holdings")
asset_allocation = get_holdings(qqq_xid, "asset_allocation")

# Plot price chart
historical_data.set_index('date')['close'].plot(title='QQQ Price History')
plt.show()

# Display fund information
print("Fund Profile:")
print(profile.head(10))

print("\nTop 10 Holdings:")
print(top_holdings.head(10))

print("\nAsset Allocation:")
print(asset_allocation)
```

## Error Handling

The library includes logging and error handling, but you should wrap calls in try-except blocks for production use:

```python
try:
    xid = get_xid('INVALID_TICKER')
    data = get_historical_prices(xid, "01012024", "31012024")
except ValueError as e:
    print(f"Error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Requirements

- Python 3.7+
- cloudscraper >= 1.2.68
- pandas >= 1.3.0
- beautifulsoup4 >= 4.11.0

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This library is for educational and research purposes.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.