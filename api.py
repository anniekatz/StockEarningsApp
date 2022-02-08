"""@author Ann Katz"""
# This API takes data from scrape.py
# It organizes and calculates the data to send to gui.py
# Some update-based scraping functions takes place in here based on task
# The scraping functions in this file collect data that needs little to no manipulation,
# And other data from the scrape file is sent here to be manipulated and organized

import pickle
import pandas as pd
import requests
from os.path import exists
from json import loads

import yfinance as yf
import datetime
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests_futures.sessions import FuturesSession
from bs4 import BeautifulSoup

from tqdm import tqdm
import scrape


# Metaclass makes it easier to organize and pickle the file
# Helps coordination
class SPData(metaclass=scrape.Singleton):
    # Ensure Timezone is correct
    _EASTERN_TZ = pytz.timezone('US/Eastern')
    # Plan a timeout if scrape/program takes too long
    _TIMEOUT = 300

    def __init__(self):
        self.companies = scrape.CurrentSPXCompanies().companies

        # ThreadPoolExecutor and Futures allow for multiple tasks to run at once
        self._pool = ThreadPoolExecutor(max_workers=8)
        self._session = FuturesSession()

        # Run the earnings dates scraper from scrape file
        earnings_instance = scrape.EarningsDates()

        # use a pickle file to store data dict
        self.sp_dict = {}
        if exists('sp_dict.pickle'):
            self.sp_dict = pickle.load(open('sp_dict.pickle', 'rb'))

        # Store current S&P 500 Tickers
        current_symbols = [_['symbol'] for _ in self.companies]

        # Remove companies no longer in index
        for symbol in [_ for _ in self.sp_dict]:
            if symbol not in current_symbols:
                del self.sp_dict[symbol]

        # Update earnings for companies with earnings in the next 15 days
        # Earnings dates can change
        self.update_upcoming_earnings(15)

        # New S&P 500 companies var
        new_companies = [_ for _ in current_symbols if _ not in self.sp_dict]

        # Companies with recent earnings reports date updates
        # Add these dates to dict
        recent_earnings_companies = []
        for symbol in self.sp_dict:
            try:
                earnings_date = self.sp_dict[symbol].get('next_earnings', [])
                if len(earnings_date) > 0:
                    now = datetime.datetime.now(tz=self._EASTERN_TZ)
                    if earnings_date[0] < now:
                        recent_earnings_companies.append(symbol)
            except:
                continue

        # Updates companies that need it
        companies_to_update = [*new_companies, *recent_earnings_companies]

        # Adding Earnings Dates for new companies
        print("\n\nUpdating company earnings:\n\n")
        earnings = earnings_instance.earnings(companies_to_update)
        print("\n\nUpdating company earnings dates:\n\n")
        next_earnings_dates = earnings_instance.next_earnings(companies_to_update)
        # merge earnings dates with new_earnings dates and update sp_dict
        for symbol in new_companies:
            dates = earnings.get(symbol, [])[:10]
            table = (self.daily_prices(symbol, dates))
            self.sp_dict[symbol] = {
                'earnings': dates,
                'next_earnings': next_earnings_dates.get(symbol, []),
                'table': table,
                'avg': self.avg_price(table, 10)
            }

        futures = []
        # make sure all averages and tables are up to date
        for symbol in self.sp_dict:
            info = self.sp_dict[symbol]
            if 'earnings' in info and 'table' not in info:
                dates = info['earnings']
                future = self._pool.submit(self.daily_prices, symbol, dates)
                future.symbol = symbol
                futures.append(future)

        # Create progress bar for updating
        progress_bar = tqdm(total=len(futures))
        print("\n\nUpdating price data and averages:\n\n")
        try:
            for future in as_completed(futures, timeout=self._TIMEOUT):

                # Update console progress bar
                progress_bar.set_description(future.symbol)
                progress_bar.update()
                # Update table with results
                table = future.result()
                symbol = future.symbol
                # Use Pandas DataFrame with table data
                if isinstance(table, pd.DataFrame):
                    self.sp_dict[symbol] = {
                        **self.sp_dict[symbol],
                        'table': table,
                        'avg': self.avg_price(table, 10)
                    }
        except:
            pass

        # Get company details and update in pickle
        futures = []
        for symbol in self.sp_dict:
            # Update company details as needed
            if not 'detail' in self.sp_dict[symbol]:
                self.sp_dict[symbol]['detail'] = ''
                # Using pool with futures to help designate the simultaneous tasks
                future = self._pool.submit(
                    self.market_watch_company_detail, symbol)
                future.symbol = symbol
                # Append company details
                futures.append(future)

        print("\n\nGetting company details:\n\n")
        # Company details progress bar
        progress_bar = tqdm(total=len(futures))
        try:
            for future in as_completed(futures, timeout=self._TIMEOUT):
                # Update console progress bar
                progress_bar.set_description(future.symbol)
                progress_bar.update()
                # Getting details
                detail = future.result()
                symbol = future.symbol
                if isinstance(detail, str):
                    self.sp_dict[symbol]['detail'] = detail
        except:
            pass

        # Append info for symbols that need updating in dict
        for symbol in self.sp_dict:
            info = self.sp_dict[symbol]
            info['table']['Date'] = pd.Series(self.sp_dict[symbol]['earnings'])
            info['table'].set_index('Date')
        # Dump pickle data for s&p dict
        pickle.dump(self.sp_dict, open('sp_dict.pickle', 'wb'))

    # Decorator properties for dict to help with organization of getters and setters
    @property
    def data(self):
        return self.sp_dict

    def first_date(self):
        dates = []
        for symbol in self.sp_dict:
            dates.append(self.sp_dict[symbol]['table']['Date'].min())
        return pd.Series(dates).min()

    # Update the earnings dates for companies with earnings dates in the next days
    # Earnings dates can change within time frame, so it's good to update
    def update_upcoming_earnings(self, days):
        update_symbols = []
        for symbol in self.sp_dict:
            try:
                earnings_date = self.sp_dict[symbol].get('next_earnings', [])
                if len(earnings_date) > 0:
                    now = datetime.datetime.now(tz=self._EASTERN_TZ)
                    # appending earnings dates upon program open
                    if earnings_date[0] < now:
                        update_symbols.append(symbol)
                else:
                    update_symbols.append(symbol)
            except:
                continue

        print("\n\nUpdating upcoming earnings:\n\n")
        # Use Scrape file to get data then store in dict
        update_next_earnings = scrape.EarningsDates().next_earnings(update_symbols)
        for symbol in update_next_earnings:
            if symbol in self.sp_dict:
                self.sp_dict[symbol]['next_earnings'] = update_next_earnings[symbol]

    # For each date in dates, return the daily price change for the market day before and after date
    # Daily price change used to calculate averages
    def daily_prices(self, symbol, dates):

        # Create a data frame with Pandas to easily store data
        if len(dates) == 0:
            ret = pd.DataFrame(columns=['Date', 'Open_Pre', 'High_Pre', 'Low_Pre', 'Close_Pre', 'Volume_Pre',
                                        'Dividends_Pre', 'Stock Splits_Pre', 'Date_Pre', 'Open_Post',
                                        'High_Post', 'Low_Post', 'Close_Post', 'Volume_Post', 'Dividends_Post',
                                        'Stock Splits_Post', 'Date_Post', 'Point_Change', 'Percent_Change'])
            ret.set_index('Date')
            return ret

        # The yfinance API uses dashes and not dots in tickers
        symbol = symbol.replace('.', '-')
        ticker = yf.Ticker(symbol)

        # Make dates lists using Series as Column in Table
        if isinstance(dates, list):
            dates = pd.Series(dates)

        # Pulls extra dates in case next market day isn't the next actual day
        # Next market day may not be until after weekend or holiday
        # Check ten days out in both directions just to be sure
        min_date = pd.to_datetime(
            str(dates.min() - datetime.timedelta(days=10))).strftime('%Y-%m-%d')
        max_date = pd.to_datetime(
            str(dates.max() + datetime.timedelta(days=10))).strftime('%Y-%m-%d')

        # Price history from Yahoo Finance
        price_history = ticker.history(
            start=min_date, end=max_date, interval="1d")
        price_history.index = price_history.index.map(
            # Ensure price report times are correct
            lambda date: self._EASTERN_TZ.localize(date.to_pydatetime()))

        # The closest market day boundaries
        def date_upper_bound(
                df, date):
            return df.loc[df.loc[df.index >= date].index.min()]

        def date_lower_bound(df, date):
            return df.loc[df.loc[df.index < date.replace(
                hour=0, minute=0)].index.max()]

        # Closest market day before earnings report date
        # We use this for price change
        pre_daily = pd.DataFrame(
            [date_lower_bound(price_history, date) for date in dates])
        pre_daily['Date'] = pre_daily.index
        pre_daily = pre_daily.reset_index(drop=True)

        # Closest market day after earnings report date
        post_daily = pd.DataFrame(
            [date_upper_bound(price_history, date) for date in dates])
        post_daily['Date'] = post_daily.index
        post_daily = post_daily.reset_index(drop=True)

        # Subtracting the prices at those dates to get price changes
        daily = pre_daily.join(post_daily, lsuffix="_Pre", rsuffix="_Post")
        daily = daily.assign(
                Point_Change=lambda row: (row['Close_Post'] - row['Close_Pre']),
                Percent_Change=lambda row: ((row['Close_Post'] - row['Close_Pre']) * 100 / row['Close_Pre']))
        # Show date of earnings
        daily['Date'] = dates
        daily.set_index('Date')

        return daily

    # Avg price function used in Earnings Averages function to send to GUI
    def avg_price(self, prices, n):
        return {'point_avg': (abs(prices['Point_Change'][:n])).mean(), 'percent_avg': (abs(prices['Percent_Change'][:n])).mean()}

    # Company details from Market Watch
    def market_watch_company_detail(self, symbol):
        _MARKET_WATCH_URL = 'https://www.marketwatch.com/investing/stock/%s'
        try:
            content = requests.get(_MARKET_WATCH_URL %
                                   symbol, timeout=5).content
        except:
            return ''
        details = BeautifulSoup(content, 'html.parser').find_all(
            class_='description__text')
        # If details exist, add to class
        if len(details) > 0:
            return details[0].text
        return ''

# Company info class used by GUI
class CompanyInfo(metaclass=scrape.Singleton):
    _EASTERN_TZ = pytz.timezone('US/Eastern')

    def __init__(self):
        sp = SPData()
        self.companies = sp.companies
        self.sp_dict = sp.data

    # Averages needed for GUI
    def earnings_averages(self, symbol):
        symbol = symbol.upper()
        if symbol in self.sp_dict:
            return self.sp_dict[symbol]['avg']

    # Percent and Price changes per report
    def earnings_change(self, symbol):
        symbol = symbol.upper()
        if symbol in self.sp_dict:
            return self.sp_dict[symbol]['table'][['Date', 'Close_Pre', 'Close_Post', 'Percent_Change']].values

    # Dates of earnings reports
    def earnings_dates(self, symbol):
        symbol = symbol.upper()
        if symbol in self.sp_dict:
            return self.sp_dict[symbol]['table']['Date'].values

    # Date of upcoming earnings report
    def next_earnings_date(self, symbol):
        symbol = symbol.upper()
        if symbol in self.sp_dict:
            dates = self.sp_dict[symbol]['next_earnings']
            now = datetime.datetime.now()
            # Make sure that it is after now
            date_time = now.strftime("%Y-%m-%d")
            if len(dates) > 0:
                if date_time >= dates[0].strftime("%Y-%m-%d"):
                    next_earnings = scrape.EarningsDates().next_earnings_by_symbol(symbol)
                    self.sp_dict[symbol]['next_earnings'] = next_earnings
                    if date_time >= next_earnings[0].strftime("%Y-%m-%d"):
                        return datetime.datetime(year=2050, month=1, day=1)
                    else:
                        pickle.dump(self.sp_dict, open('sp_dict.pickle', 'wb'))
                        return next_earnings[0]
                elif dates[0].strftime("%Y-%m-%d") > date_time:
                    return dates[0]
            else:
                # Try to get the next_earnings for symbol from pickle file
                next_earnings = scrape.EarningsDates().next_earnings_by_symbol(symbol)
                if len(next_earnings) > 0 and (dates[0].strftime("%Y-%m-%d") > date_time):
                        self.sp_dict[symbol]['next_earnings'] = next_earnings
                        pickle.dump(self.sp_dict, open('sp_dict.pickle', 'wb'))
                        return next_earnings[0]
                else:
                    return datetime.datetime(year=2050, month=1, day=1)

        # An error in datetime- to update next start
        return datetime.datetime(year=1970, month=1, day=1)

    # Acquire company details
    def company_detail(self, symbol):
        symbol = symbol.upper()
        if symbol in self.sp_dict:
            return self.sp_dict[symbol]['detail']

    # Create Earnings range of dates
    def earnings_range(self, symbol):
        symbol = symbol.upper()
        if symbol in self.sp_dict:
            table = self.sp_dict[symbol]['table']
            min_date = table['Date'].min()
            max_date = table['Date'].max()
            return {'start': min_date, 'end': max_date}

    # Price history data function
    def stock_data(self, symbol, start, end=None):
        # Yahoo ticker compliance
        symbol = symbol.replace('.', '-')
        return yf.Ticker(symbol).history(start=start, end=end)

# Class to grab quote data from HTML, current price, etc.
class SPPrice:
    _BASE_URL = "http://quote-feed.zacks.com/?t=%s"
    # Use request header as best practice
    _REQUEST_HEADER = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.75 "
                      "Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }

    @staticmethod
    # Method to get price
    def prices(symbols):
        try:
            url = SPPrice._BASE_URL % ",".join(symbols)
            resp = requests.get(url, timeout=5).content
            obj = loads(resp)
            # return most recent price
            return {k: obj[k].get('last', '') for k in obj}
        except:
            pass
        return {k: '' for k in symbols}
