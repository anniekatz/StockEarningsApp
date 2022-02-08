"""@author Ann Katz"""
# This Scrape file is used to hold functions that
# scrape the data needed from ZACKS for Earnings dates
# and yahoo finance for prices.

# Functions defined in classes here are used in API file for calculations and organization

import pandas as pd
import requests
from json import loads

import datetime
from dateutil import parser
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests_futures.sessions import FuturesSession
from bs4 import BeautifulSoup

from tqdm import tqdm


# Throughout code, variables intended to be private will start with _

# Singleton Metaclass created to ensure only one instance of company in data
# Code for the Singleton Class based on common StackOverflow implementation
class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


# Class to Grab Current S&P tickers and names from Wikipedia table
# Classes and variables that start with _ are used for privacy
class CurrentSPXCompanies(metaclass=Singleton):
    _wiki_source = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'

    def __init__(self):

        _WIKI_ERROR = "Error parsing Wikipedia's table: Please check Wiki page for changes in column headers."

        # The first table in the Wikipedia page lists updated company symbols and names
        try:
            table = pd.read_html(self._wiki_source)[0]
            col0 = table.columns[0]
            col1 = table.columns[1]

        # Message for exception based on a Wikipedia error
        except Exception:
            raise Exception(_WIKI_ERROR)

        # Checks if column headers in Wikipedia are still the same
        if (col0.rstrip() != "Symbol" or
                col1.rstrip() != "Security"):
            raise Exception(_WIKI_ERROR)

        # Add the tickers and names with a zip function to pair the corresponding data into
        # two lists
        symbol_name_zip = zip(
            table['Symbol'].to_list(), table['Security'].to_list())

        # This will sort the separate lists into tuples of tickers and names (strings)
        # Alphabetical Order
        sorted_symbol_name_zip = sorted(symbol_name_zip, key=lambda _: _[0])
        self.companies = [{
            "symbol": _[0],
            "name": _[1],
        } for _ in sorted_symbol_name_zip]


# Class to Scrape Earnings Dates
class EarningsDates(metaclass=Singleton):
    # Ensure Eastern Time Zone with pytz
    _EASTERN_TZ = pytz.timezone('US/Eastern')
    # Constant Request Header for web scraping
    _REQUEST_HEADER_UA = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/90.0.4430.85 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    TIMEOUT = 300

    # Using a ThreadPoolExecutor and Futures to allow multiple tasks to run at once
    def __init__(self):
        self._pool = ThreadPoolExecutor(max_workers=8)
        self._session = FuturesSession()

    # Use a fuzzy parser to match string with date and time
    # This will help our datetime objects and program understanding
    def _fuzzy_date(self, filename):
        return self._EASTERN_TZ.localize(parser.parse(filename, fuzzy=True))

    # ZACKS website stores earnings dates data in a script tag in the page
    # Function to parse dates from that script tag and return dates offset by earnings time
    # The earnings time is very important as it directly correlated with the next market day price change
    def earnings_by_symbol(self, symbol):
        symbol = symbol.upper()
        earnings_url = "https://www.zacks.com/stock/research/%s/earnings-announcements"
        content = requests.get(
            earnings_url % symbol, headers=self._REQUEST_HEADER_UA, timeout=(5, 27)).content
        # Use request headers to prevent error
        soup = BeautifulSoup(content, 'html.parser')
        # BeautifulSoup package used to scrape HTML data
        scripts = soup.find_all('script')
        table_scripts = [
            _ for _ in scripts if _.string and "earnings_announcements_earnings_table" in _.string]
        # Using len to ensure data exists
        if len(table_scripts) > 0:
            js = table_scripts[0].string
            obj = loads(js[js.find('{'): js.rfind('}') + 1])
            earnings_announcements_table = obj["earnings_announcements_earnings_table"]
            dates = map(lambda _: self._fuzzy_date(_[0]), earnings_announcements_table)
            offsets = map(lambda _: datetime.timedelta(days=1) if _[
                                                                      6] == "After Close" else None,
                          earnings_announcements_table)
            return [d + o if o else d for d, o in zip(dates, offsets)]

    # Get Earnings Dates and add to dictionary
    def earnings(self, symbols):
        # Will be using futures in many scraping classes to allow code to execute simultaneously
        futures = []
        for symbol in symbols:
            future = self._pool.submit(self.earnings_by_symbol, symbol)
            future.symbol = symbol
            futures.append(future)

        dates_dict = {}
        # Create console progress bar
        progress_bar = tqdm(total=len(futures))
        _PROGRESS_ERROR = "Error creating progress bar"

        try:
            for future in as_completed(futures, timeout=self.TIMEOUT):

                # Update console progress bar
                progress_bar.set_description(future.symbol)
                progress_bar.update()
                # Update dates as progress continues
                dates = future.result()
                symbol = future.symbol
                if isinstance(dates, list) and len(dates) > 0:
                    dates_dict[symbol] = dates
        except Exception:
            print(_PROGRESS_ERROR)
        return dates_dict

    # Function to scrape ZACKS for next upcoming earnings date
    def next_earnings_by_symbol(self, symbol):
        _URL = 'https://www.zacks.com/stock/quote/%s/detailed-estimates'
        _ZACKS_ERROR = 'Unable to get next earnings date for %s. Please check URL.'
        try:
            r = requests.get(_URL % symbol, headers=self._REQUEST_HEADER_UA)
            next_earnings_table = pd.read_html(
                r.content, match="Next Report Date", index_col=0, parse_dates=True)
            # Error for no data
            if len(next_earnings_table) == 0:
                raise Exception(_ZACKS_ERROR % symbol)
            # Read values
            date_string = next_earnings_table[0].loc['Next Report Date'].values[0]
            # Use fuzzy parser to grab datetime data effectively
            date = self._EASTERN_TZ.localize(
                parser.parse(date_string, fuzzy=True))
            return [date]
        except Exception:
            pass
        return []

    # Function to append next earnings to dates_dict
    def next_earnings(self, symbols):
        futures = []
        for symbol in symbols:
            future = self._pool.submit(self.next_earnings_by_symbol, symbol)
            future.symbol = symbol
            futures.append(future)

        dates_dict = {}
        # Progress bar creation
        progress_bar = tqdm(total=len(futures))
        try:
            for future in as_completed(futures, self.TIMEOUT):

                # Update console progress bar
                progress_bar.set_description(future.symbol)
                progress_bar.update()
                # Append upcoming earnings dates to dict
                dates = future.result()
                symbol = future.symbol
                if isinstance(dates, list) and len(dates) > 0:
                    dates_dict[symbol] = dates
        except Exception:
            pass
        return dates_dict
