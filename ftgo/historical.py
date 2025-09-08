"""
Historical data fetching functionality for FTMarkets.

This module provides functions to fetch and process historical stock price data
from FT Markets with support for OHLCV data and concurrent processing.
"""

import cloudscraper
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from typing import Dict, Any, List
import logging
import concurrent.futures

# Set up logging
logger = logging.getLogger(__name__)


def fetch_historical_prices(xid: str, date_from: str, date_to: str) -> Dict[str, Any]:
    """
    Fetch historical price data from FT Markets API.
    
    Args:
        xid: The FT Markets XID
        date_from: Start date in DDMMYYYY format (e.g., "01012024")
        date_to: End date in DDMMYYYY format (e.g., "31122024")
        
    Returns:
        JSON response from the API
        
    Raises:
        requests.exceptions.HTTPError: If the API request fails
    """
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    try:
        # Convert DDMMYYYY to FT format (YYYY%2FMM%2FDD)
        start_date = datetime.strptime(date_from, "%d%m%Y")
        end_date = datetime.strptime(date_to, "%d%m%Y")
        
        start_formatted = start_date.strftime("%Y%%2F%m%%2F%d")
        end_formatted = end_date.strftime("%Y%%2F%m%%2F%d")
        
        url = f"https://markets.ft.com/data/equities/ajax/get-historical-prices?startDate={start_formatted}&endDate={end_formatted}&symbol={xid}"
        
        response = scraper.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch historical data for XID {xid}: {e}")
        raise


def html_to_dataframe(html_content: str) -> pd.DataFrame:
    """
    Convert HTML response to a pandas DataFrame.
    
    Args:
        html_content: HTML content from the FT Markets API
        
    Returns:
        pandas.DataFrame with processed historical data
        
    Note:
        Returns empty DataFrame if no data is found
    """
    if not html_content:
        logger.warning("No HTML content provided")
        return pd.DataFrame()
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        rows = soup.find_all('tr')
        
        historical_data = []
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 6:  # Ensure we have all columns including volume
                try:
                    # Extract date
                    date_cell = cells[0]
                    date_spans = date_cell.find_all('span')
                    if date_spans:
                        date_text = date_spans[0].get_text().strip()
                    else:
                        date_text = date_cell.get_text().strip()
                    
                    # Parse date
                    try:
                        date_obj = datetime.strptime(date_text, '%A, %B %d, %Y')
                    except ValueError:
                        try:
                            date_obj = datetime.strptime(date_text, '%B %d, %Y')
                        except ValueError:
                            continue
                    
                    formatted_date = date_obj.strftime('%Y-%m-%d')
                    
                    # Extract OHLC prices
                    open_price = float(cells[1].get_text().strip().replace(',', ''))
                    high_price = float(cells[2].get_text().strip().replace(',', ''))
                    low_price = float(cells[3].get_text().strip().replace(',', ''))
                    close_price = float(cells[4].get_text().strip().replace(',', ''))
                    
                    # Extract volume from 6th column
                    volume_cell = cells[5]
                    volume_spans = volume_cell.find_all('span')
                    if volume_spans:
                        # Use the first span with full number
                        volume_text = volume_spans[0].get_text().strip().replace(',', '')
                    else:
                        volume_text = volume_cell.get_text().strip().replace(',', '')
                    
                    # Convert volume to integer
                    try:
                        volume = int(float(volume_text))
                    except ValueError:
                        volume = 0
                    
                    historical_data.append({
                        'date': formatted_date,
                        'open': open_price,
                        'high': high_price,
                        'low': low_price,
                        'close': close_price,
                        'volume': volume
                    })
                    
                except (ValueError, IndexError) as e:
                    continue
        
        if historical_data:
            df = pd.DataFrame(historical_data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            return df
        
    except Exception as e:
        logger.error(f"Error processing HTML data: {e}")
    
    return pd.DataFrame()


def get_historical_prices(xid: str, date_from: str, date_to: str) -> pd.DataFrame:
    """
    Get historical price data for a security with full OHLCV data.
    
    Args:
        xid: The FT Markets XID (use get_xid to find this)
        date_from: Start date in DDMMYYYY format (e.g., "01012024")
        date_to: End date in DDMMYYYY format (e.g., "31122024")
        
    Examples:
        >>> xid = get_xid('AAPL')
        >>> df = get_historical_prices(xid, "01012024", "31012024")
    """
    if not xid:
        raise ValueError("XID cannot be empty")
    
    logger.info(f"Fetching historical data for XID {xid} from {date_from} to {date_to}")
    
    json_data = fetch_historical_prices(xid, date_from, date_to)
    
    if not json_data.get('html'):
        logger.warning("No HTML data in API response")
        return pd.DataFrame()
    
    html_content = json_data['html']
    if len(html_content) == 0:
        logger.warning("Empty HTML content in API response")
        return pd.DataFrame()
    
    df = html_to_dataframe(html_content)
    
    logger.info(f"Successfully retrieved {len(df)} data points for XID {xid}")
    return df


def get_multiple_historical_prices(
    xids: List[str], 
    date_from: str, 
    date_to: str
) -> pd.DataFrame:
    """
    Get historical data for multiple securities concurrently.
    
    Args:
        xids: List of FT Markets XIDs
        date_from: Start date in DDMMYYYY format (e.g., "01012024")
        date_to: End date in DDMMYYYY format (e.g., "31122024")
        
    Returns:
        pandas.DataFrame with data for all securities concatenated
        
    Raises:
        ValueError: If parameters are invalid
        
    Examples:
        >>> from ftmarkets import get_xid, get_multiple_historical_prices
        >>> xids = [get_xid('AAPL'), get_xid('MSFT')]
        >>> df = get_multiple_historical_prices(xids, "01012024", "31012024")
    """
    if not xids:
        raise ValueError("XIDs list cannot be empty")
    
    logger.info(f"Fetching data for {len(xids)} securities")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(get_historical_prices, xid, date_from, date_to) 
            for xid in xids
        ]
        results = []
        
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if not result.empty:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error fetching data for security: {e}")
    
    if results:
        combined_df = pd.concat(results, axis=0, ignore_index=True)
        logger.info(f"Successfully retrieved data for {len(results)} securities")
        return combined_df
    else:
        logger.warning("No data retrieved for any securities")
        return pd.DataFrame()