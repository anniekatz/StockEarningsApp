# StockEarningsApp
Spring 2021 Capstone Project: S&amp;P 500 Earnings Price Data Scraper, Calculator, and Calendar

## Please see document labeled Final Report for full project report

# Project Background
* Original purpose: create a simple Windows executable interface for options traders
* Program to show upcoming earnings dates for certain companies and their past performances at certain times post-earnings reports for those who needed that data to make options trades
* It had previously taken me hours to perform the calculations and research myself, and I could not find a program that would do it for me and save me time
* The main point of the program was to fetch (the past ten) historical earnings report dates, times, and prices of S&P 500 Companies. It was to use that data to calculate the average 24-hour price(in $ and %) difference from the market day before the past ten earnings report to the corresponding market day after. The app was also to scrape and list the dates of the next upcoming earnings reports for easy viewing. 

# Requirements
* User needed to be able to:
  * Install and open executable program to view UI Home page
  * View table of S&P 500 companies on home page, with buttons to sort by upcoming earnings date, current price, and average % change in the 1 market day time frame post-earnings
  * Search for a ticker in search box or click a ticker on that list to view their company page window with: upcoming earnings date, average % change in price exactly 1 day (in market days) after earnings report date, price change in that time frame for the past ten earnings reports, and current price at time of program open
  * Navigate to help screen
* Program requirements:
  * All data, dates, prices, and calculations must be accurate and updated upon program open
  * S&P 500 Company List must remain updated

# Program Design
* Program written with Python for their various financial and data structure external libraries and functions
* Use of Tkinter Python built-in library to build GUI, widgets for search and column display/sorting
* Use of BeautifulSoup and Finance APIs to scrape necessary data
* Use of a DataFrames and other structures with Pandas and NumPy for easily storing a long list of data without iterating over a list
* Use of Zip() to store tickers and company names together immediately  as tuple without iteration
* Simultaneous task execution with Futures and ThreadPoolExecutor
* Along with Python program source code files(scrape, api, and gui), pickle file for storage, ReadMe for Help window and program/installation instructions, icons folder to store images for gui.py, requirements.txt document to easily install dependencies, and install.py to install the program as an executable with a little icon

# Were requirements met?
* All use cases were met with the exception of one I decided to change to add a new feature
  * I had planned on having the Help button available on every window, but decided to put a stock chart Tkinter widget in its place
  * These were easily testable with test matrix
  * Calculation and storage methods met accuracy and timeliness requirements after market dates/ scraper used was corrected
* The API and web-scraper accuracy
  * This was harder to test, as some stock/real-time data must be tested by human instead of unit tests or other functions
  * Time consuming but ended up saving the program
  * Yfinance ended up being inaccurate for certain prices/dates, goes to show that just because API is popular doesn’t mean it’s perfect
  * Now, after changing API and researching, every trial performed shows accuracy

# Features added outside of requirements
* Console progress bar added for those running the program in a command line or IDE
* Stock chart widget added in Company Information window to show the price changes at the past recent earnings dates
  * A visual chart can be more user-friendly and easier to quickly understand than a list of numbers
 * Install.py file and installation/dependency instructions for Windows users who want the program as an executable
 * Sort by column on main pages just by clicking the column headers
  * Lots of user-friendly options for tables, sorting, and searching in Tkinter
 * Pickle file to store dictionary of data in a simpler way

# Future/Potential Features to be added
* Need a better-looking GUI, will learn more about Tkinter or perhaps use another language/framework to create it and Python as a backend
* Create as a web app for non-Windows users, or an app with a simpler installation process
* Need to find a way to grab absolute values from unfamiliar data structures
* Add more stock features
  * Live price tracker (instead of one that updates upon company open)
  * All companies in NYSE and NASDAQ
* The tables need a more user-friendly appearance

# Resources
* APIs/Web Pages/Libraries used for project:
  * Languages and Code Tools: Python 3.9, Pycharm IDE (Developed by JetBrains)
* Web Resources: ZACKS.com, MarketWatch.com, Finance.Yahoo.com, Wikipedia.com
* Python External/Internal Libraries: Pyinstaller, Tkinter, Dateutil, Requests, Requests_Futures, YFinance, Pytz, Matplotlib, Mplfinance, BeautifulSoup4, TTKthemes, Pandas, NumPy, Datetime Future, StringGenerator
