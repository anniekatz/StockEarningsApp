"""@author Ann Katz"""
# The GUI file is the file to be run.
# It takes data from the API and displays it for user
# I used tkinter and tkinter widgets to create the GUI
import tkinter
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox
from datetime import datetime
from functools import partial
from tkinter import X
from tkinter.scrolledtext import ScrolledText

import matplotlib
from ttkthemes import ThemedStyle

matplotlib.use('TkAgg')
matplotlib.rcParams['axes.unicode_minus'] = False

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
import mplfinance as mpf

from api import CompanyInfo, SPPrice


# Make date strings from date objects for GUI
def to_datestrings(dates):
    return [str(_)[:10] for _ in dates]

# quin running when window closes
def quit_me():
    root.quit()
    root.destroy()


# CUSTOM WIDGETS

# Chart for each company page
class StockChart(ttk.Frame):
    def __init__(self, parent, info, *args, **kwargs):
        self.company_info = CompanyInfo()
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        try:
            self.symbol = info['symbol']
            start = info['dates'].min()
            self.plot(self.symbol, str(start)[:10], to_datestrings(info['dates']))
        except:
            tk.Label(self, text=f"Cannot get chart for {self.symbol}").pack()

    # Use matplotlib library tk connector to plot stock data
    # Function made in tk
    def plot(self, symbol, start, dates):
        stock_data = self.company_info.stock_data(symbol, start)
        markers = ["^" if _ in dates else None for _ in to_datestrings(
            stock_data.index)]
        adp = mpf.make_addplot(
            stock_data['Open'] * 0.95, marker=markers, type="scatter", markersize=200)

        fig = mpf.plot(stock_data, type="line",
                       addplot=adp, returnfig=True)
        canvas = FigureCanvasTkAgg(fig[0], master=self)
        canvas.mpl_connect("key_press_event", key_press_handler)
        widget = canvas.get_tk_widget()
        toolbar = NavigationToolbar2Tk(canvas, self, pack_toolbar=True)
        toolbar.update()
        widget.pack()
        canvas.draw()

# Treeview with sorting for each column
class SortTreeview(ttk.Treeview):
    def __init__(self, parent, types, *args, **kwargs):
        ttk.Treeview.__init__(self, parent, *args, **kwargs)
        self.sort = types

    def heading(self, column, sort_by=None, **kwargs):
        if sort_by and not hasattr(kwargs, 'command'):
            func = getattr(self, f"_sort_by_{sort_by}", None)
            if func:
                kwargs['command'] = partial(func, column, False)
        return super().heading(column, **kwargs)

# four sorting functions defined below
    def _sort(self, column, reverse, data_type, callback):
        l = [(self.set(k, column), k) for k in self.get_children('')]
        l.sort(key=lambda t: data_type(t[0]), reverse=reverse)
        for index, (_, k) in enumerate(l):
            self.move(k, '', index)
        self.heading(column, command=partial(callback, column, not reverse))

    def _sort_by_num(self, column, reverse):
        self._sort(column, reverse, float, self._sort_by_num)

    def _sort_by_name(self, column, reverse):
        self._sort(column, reverse, str, self._sort_by_name)

    def _sort_by_date(self, column, reverse):
        def _str_to_datetime(string):
            return datetime.strptime(string, "%Y-%m-%d")

        self._sort(column, reverse, _str_to_datetime, self._sort_by_date)

# Button class
class NavButton(ttk.Frame):
    def __init__(self, parent, command=None, text=None, image=None, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.button = ttk.Button(
            self, text=text, image=image, command=command)

        self.button.pack(side=tk.TOP, fill=tk.X, expand=True)


# View from page
class CompanyDetailView:
    def __init__(self, symbol):
        self.company_info = CompanyInfo()
        changes = self.company_info.earnings_averages(symbol)
        self.info = {
            'symbol': symbol,
            'earnings_dates': self.company_info.earnings_dates(symbol),
            'next_earnings': self.company_info.next_earnings_date(symbol).strftime('%Y-%m-%d'),
            'average_point_change': (round(changes['point_avg'], 2)),
            'average_percent_change': (round(changes['percent_avg'], 2)),
            'average_percent_change_pos': True if changes['percent_avg'] > 0 else False,
            'description': self.company_info.company_detail(symbol)
        }


# Sort earnings dates in View
class InfoView:
    def format_values(self, sort, values):
        for sort, value in zip(sort, values):
            if sort == "date":
                if isinstance(value, datetime):
                    yield value.strftime("%Y-%m-%d")
                else:
                    # error datetime
                    yield datetime(year=1970, month=1, day=1)

            elif sort == "num":
                if isinstance(value, int) or isinstance(value, float):
                    yield round(value, 2)
                else:
                    try:
                        yield float(value)
                    except:
                        yield 0
            else:
                yield value


# Detailed Company Earnings Information View in Company Window
class EarningsInfoView(InfoView):
    def __init__(self, symbol):
        self.company_info = CompanyInfo()
        self.symbol = symbol
        info = {
            'text': f"{symbol} Past Earnings",
            'columns': ('Current Price', 'Earnings Date', 'Close Before', 'Close After', 'Percent Change'),
            'sort': ('num', 'date', 'num', 'num', 'num'),
            'values': {},
            'indicator': {},
        }

        # Update values in this table
        prices = SPPrice.prices([symbol])
        for index, values in enumerate(self.company_info.earnings_change(self.symbol)):
            price = prices[symbol]
            avgs = self.company_info.earnings_averages(symbol)
            next_earnings_date = self.company_info.next_earnings_date(symbol)
            info['values'][index] = tuple(
                self.format_values(info['sort'], [price, *values]))

        self.info = info

# Company Info View
class SPInfoView(InfoView):
    percent_average = "Percent Average Change"
    current_price = "Current Price"
    earnings_date = "Upcoming Earnings Date"

    def __init__(self):
        self.company_info = CompanyInfo()
        info = {
            'text': 'Current S&P 500 Companies',
            'columns': (
                'Symbol', 'Company Name', self.current_price, 'Average Change (USD)', self.percent_average,
                self.earnings_date),
            'sort': ('name', 'name', 'num', 'num', 'num', 'date'),
            'values': {}
        }

        prices = SPPrice.prices([_['symbol'] for _ in self.company_info.companies])
        for company in self.company_info.companies:
            symbol = company['symbol']
            name = company['name']
            price = prices[symbol]
            avgs = self.company_info.earnings_averages(symbol)
            next_earnings_date = self.company_info.next_earnings_date(symbol)
            info['values'][symbol] = tuple(self.format_values(info['sort'], [
                symbol, name, price, avgs['point_avg'], avgs['percent_avg'], next_earnings_date]))

        self.info = info


# InfoPane GUI Elements
class InfoPane(ttk.Frame):
    def __init__(self, parent, info, onclick=None, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.header = ttk.Label(
            self, text=info['text'], anchor=tk.CENTER, style='Heading.TLabel')

        self.list = SortTreeview(
            self, info['sort'], columns=info['columns'], show='headings')

        if onclick:
            self.list.bind("<ButtonRelease-1>", onclick(self.list))

        for index, column in enumerate(info['columns']):
            self.list.column(column, anchor=tk.CENTER, width=150)
            self.list.heading(
                column, sort_by=info['sort'][index], text=column, anchor=tk.CENTER)

        for value in info['values']:
            self.list.insert('', tk.END, values=info['values'][value])

        self.header.pack(side=tk.TOP, fill=tk.X)
        self.list.pack(fill=tk.BOTH, expand=True)


# 3 classes needed for Search

# SearchResult displays the search result in a new root level
class SearchResult(ttk.Frame):
    def __init__(self, parent, tree_meta, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)

        sort = tree_meta['sort']
        columns = tree_meta['columns']
        value_list = tree_meta['values']

        self.parent = parent
        self.tree_meta = tree_meta
        self.list = SortTreeview(self, sort, columns=columns, show='headings')
        self.list.bind("<ButtonRelease-1>", self.onClick)

        for index, column in enumerate(columns):
            self.list.column(column, anchor=tk.CENTER)
            self.list.heading(
                column, sort_by=sort[index], text=column, anchor=tk.CENTER)

        for values in value_list:
            self.list.insert('', tk.END, values=values)

        self.list.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def onClick(self, event):
        selection = self.list.selection()
        if len(selection) > 0:
            item = selection[0]
            symbol = self.list.item(item, 'values')[0]
            self.tree_meta['root'].showEarningsDetail(symbol)
            self.parent.destroy()


# Search text entry/button and search function
class SearchBox(ttk.Frame):
    def __init__(self, parent, root, tree, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.root = root
        self.tree = tree
        self.entry = ttk.Entry(self)

        try:
            self.searchIcon = tk.PhotoImage(
                file='icons/search-button-text.png')
        except:
            self.searchIcon = None

        self.button = NavButton(
            self, image=self.searchIcon, command=self.search, height=10)

        self.entry.pack(side=tk.TOP, fill=tk.X, padx=3, pady=3)
        self.button.pack(side=tk.BOTTOM, padx=4, pady=3)

    def search(self):
        # Function for search bar entry
        query = self.entry.get()
        # If search is empty, error
        if query == "":
            return tk.messagebox.showerror("Error", "No matching S&P 500 Company found")
        selections = []
        for child in self.tree.get_children():
            values = self.tree.item(child)['values']
            if any([query.lower() == str(_).lower()[:len(query)] for _ in values]):
                selections.append(values)

        if not selections:
            # If no results, error
            return tk.messagebox.showerror("Error", "No matching S&P 500 Company found")

        top = tk.Toplevel(self.root)
        tree_meta = {
            'root': self.root,
            'sort': self.tree.sort,
            'columns': self.tree['columns'],
            'values': selections,
        }

        search_results = SearchResult(top, tree_meta)
        search_results.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

# Frame wrapper for the search box
class SearchPane(ttk.Frame):
    def __init__(self, parent, root, tree, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.searchbox = SearchBox(self, root, tree)

        self.searchbox.pack(side=tk.TOP, fill=tk.X, expand=True)

# Textbox to expand if necessary
class ExpandingText(ttk.Frame):
    def __init__(self, parent, text, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.full_text = text
        self.truncated = False

        self.scrolltext = ScrolledText(self, wrap=tk.WORD)
        self.scrolltext.insert(tk.END, self.full_text)
        self.scrolltext.config(state=tk.DISABLED)
        self.scrolltext.pack()

# Frame wrapper for company detail labels
# Next Earnings Date, Average Dollar/ Percent Change and Company Summary
class CompanyDetailPane(ttk.Frame):
    def __init__(self, parent, info, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        ttk.Label(
          self, text=f"Upcoming Earnings: {info['next_earnings']}", style="Subheading.TLabel").pack(pady=2)

        average_change = ttk.Frame(self)
        ttk.Label(average_change, text="AVERAGE CHANGE 1 DAY POST-EARNINGS (ABSOLUTE VALUE)",
                  style="Subheading.TLabel").pack(pady=5)
        frame = ttk.Frame(average_change)
        ttk.Label(
            frame, text=f"Percent: {info['average_percent_change']}%", compound=tk.RIGHT,
            style="Subheading.TLabel").pack(side=tk.RIGHT, padx=1)

        ttk.Label(
            frame, text=f"In USD: ${info['average_point_change']}", compound=tk.RIGHT,
            style="Subheading.TLabel").pack(side=tk.RIGHT, padx=1)
        frame.pack(padx=2)
        ExpandingText(average_change, info['description']).pack(
            side=tk.BOTTOM, expand=True, pady=4)
        average_change.pack()


# Two Column Layout for UI
class TwoColFrame(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.left = ttk.Frame(self)
        self.right = ttk.Frame(self)

        self.left.pack(side=tk.LEFT, fill=tk.Y)
        self.right.pack(fill=tk.BOTH, expand=True)


# Three row layout used for the right column of the app
class ThreeRowFrame(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        ttk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.top = ttk.Frame(self)
        self.mid = ttk.Frame(self)
        self.bot = ttk.Frame(self)

        self.top.pack(side=tk.TOP, fill=tk.X)
        self.mid.pack(expand=False)
        self.bot.pack(side=tk.BOTTOM, fill=tk.X)


# Right column buttons and images
class BaseRightCol(ThreeRowFrame):
    def __init__(self, parent, info, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        try:
            self.exitIcon = tk.PhotoImage(file='icons/exit-icon-image.png')
            self.homeIcon = tk.PhotoImage(file='icons/home-icon-image.png')
            self.exitText = tk.PhotoImage(file='icons/exit-button-text.png')
            self.helpText = tk.PhotoImage(file='icons/help-button-text.png')
        except:
            self.exitIcon = None
            self.homeIcon = None
            self.exitText = None
            self.helpText = None

        NavButton(self.top, command=info['exit_command'], image=self.exitIcon).pack(
            side=tk.RIGHT, expand=False, padx=1, pady=1)
        NavButton(self.top, command=info['home_command'], image=self.homeIcon).pack(
            side=tk.RIGHT, expand=False, padx=1, pady=6)

        NavButton(self.bot, command=info['exit_command'], image=self.exitText).pack(
            side=tk.RIGHT, padx=20, expand=True)
        NavButton(self.bot, command=info['help_command'], image=self.helpText).pack(
            side=tk.RIGHT, padx=20, pady=20, fill=X, expand=True)


# App Main Frame
class MainApplication(ttk.Frame):
    def __init__(self, parent, views, *args, **kwargs):
        ttk.Frame.__init__(self, parent, **kwargs)
        self.views = views
        self.sp_info = views['sp'].info
        self.parent = parent
        self.root = self
        self.sortByImage = None

        sp = views['sp']
        self.sortcommands = [
            {
                'filename': 'average-text.png',
                'command': lambda list: partial(list._sort_by_num, sp.percent_average, True)
            },
            {
                'filename': 'current-text.png',
                'command': lambda list: partial(list._sort_by_num, sp.current_price, True)
            },
            {
                'filename': 'earnings-text.png',
                'command': lambda list: partial(list._sort_by_date, sp.earnings_date, False)
            },
        ]

        self.button_info = {
            'exit_command': lambda: (root.destroy(), root.quit()),
            'help_command': lambda: self.showHelpWindow(),
            'home_command': lambda: self.showSPWindow()
        }

        self.showSPWindow()
        # Show home page

    # Function defined to show the home page of the program
    def showSPWindow(self):
        mainwindow = getattr(self, 'mainwindow', None)
        if mainwindow:
            mainwindow.destroy()

        # the two column layout
        twocols = TwoColFrame(self)
        twocols.pack(fill=tk.BOTH, anchor=tk.CENTER, expand=True)
        self.mainwindow = twocols

        # left column
        infopane = InfoPane(
            twocols.left, self.sp_info, onclick=self.spOnClick)
        infopane.pack(fill=tk.BOTH, expand=True, padx=20, pady=70)

        # right column
        rightcol = BaseRightCol(twocols.right, self.button_info)

        searchpane = SearchPane(rightcol.mid, self, infopane.list)
        # sort buttons
        # prevent icon garbage collection by saving to class variable
        self.images = []

        if self.sortByImage is None:
            try:
                self.sortByImage = tk.PhotoImage(file=f'icons/sort-by-text.png')
            except:
                self.sortByImage = None

        if self.sortByImage is not None:
            ttk.Label(searchpane, image=self.sortByImage).pack(pady=2)

        for sorts in self.sortcommands:
            try:
                image = tk.PhotoImage(file=f'icons/{sorts["filename"]}')
                command = sorts['command']
                NavButton(searchpane, command=command(infopane.list), image=image).pack(pady=10)
                self.images.append(image)
            except:
                continue

        searchpane.pack(side=tk.RIGHT, expand=True)

        rightcol.pack(expand=True, pady=30, padx=15)

    # shows the Company Page for a symbol, creates a window
    def showEarningsDetail(self, symbol):
        mainwindow = getattr(self, 'mainwindow', None)
        if mainwindow:
            mainwindow.destroy()

        # main two column layout
        twocols = TwoColFrame(self)
        twocols.pack(fill=tk.BOTH, anchor=tk.CENTER, expand=True)
        self.mainwindow = twocols

        companydetail = CompanyDetailView(symbol)

        # left column
        earnings_info = EarningsInfoView(symbol)
        infopane = InfoPane(twocols.left, earnings_info.info)
        CompanyDetailPane(infopane, companydetail.info).pack()
        infopane.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # right column
        rightrows = BaseRightCol(twocols.right, self.button_info)
        StockChart(
            rightrows.mid,
            {'dates': companydetail.info['earnings_dates'], 'symbol': companydetail.info['symbol']}).pack()
        rightrows.pack(fill=tk.BOTH, pady=70, padx=20, anchor='w')

    def showHelpWindow(self):
        top = tk.Toplevel(self.root)
        with open('README.txt', encoding="utf-8") as readme:
            text = ScrolledText(top, wrap=tk.WORD)
            text.insert(tk.END, readme.read())
            text.config(state=tk.DISABLED)
            text.pack(fill=tk.BOTH, expand=True)

    def spOnClick(self, list):
        def onClick(event):
            selection = list.selection()
            if len(selection) > 0:
                item = selection[0]
                symbol = list.item(item, 'values')[0]
                self.showEarningsDetail(symbol)

        return onClick


# Running main window
if __name__ == "__main__":
    root = tk.Tk()
    root.title("S&P 500 Tracker")

    # styles
    style = ThemedStyle(root)
    style.set_theme('arc')  # imported from ttkthemes library

    text_base = {'background': 'white', 'relief': tk.SOLID, 'padding': 16}
    style.configure('Heading.TLabel', **text_base, font=('Roboto', 24, 'bold'))
    style.configure('Subheading.TLabel', **text_base,
                    font=('Roboto', 10, 'bold'))

    style.configure('TLabel', background="white")
    style.configure('TEntry', padding=10)

    style.configure("Treeview", rowheight=25, padding=8, font=('Roboto', 10))
    style.configure("Treeview.Heading", font=('Roboto', 8, 'bold'))
    style.configure("Treeview.treearea", relief=tk.SOLID,
                    font=('Roboto', 8, 'bold'))
    style.layout(
        "Treeview", [('mystyle.Treeview.treearea', {'sticky': 'nswe'})])


    # Window size
    root.geometry("1440x1024")

    spinfoview = SPInfoView()
    views = {'sp': spinfoview}

    root.protocol("WM_DELETE_WINDOW", root.quit())


    MainApplication(root, views).pack(side="top", fill="both", expand=True)
    root.mainloop()
