from .base import _IEXBase
from iexfinance.utils.exceptions import (IEXSymbolError, IEXDatapointError,
                                         IEXEndpointError, IEXQueryError)

import pandas

import datetime
from dateutil.relativedelta import relativedelta

# Data provided for free by IEX
# Data is furnished in compliance with the guidelines promulgated in the IEX
# API terms of service and manual
# See https://iextrading.com/api-exhibit-a/ for additional information
# and conditions of use


class StockReader(_IEXBase):

    # Possible option values (first is default)
    _RANGE_VALUES = ['1m', '5y', '2y', '1y', 'ytd', '6m', '3m', '1d']
    _ENDPOINTS = ["chart", "quote", "book", "open-close", "previous",
                  "company", "stats", "peers", "relevant", "news",
                  "financials", "earnings", "dividends", "splits", "logo",
                  "price", "delayed-quote", "effective-spread",
                  "volume-by-venue"]
    _ALL_ENDPOINTS_STR = ",".join(_ENDPOINTS)

    def __init__(self, *args, **kwargs):
        """ Initialize the class

        Positional Arguments:
            symbolList: A nonempty list of symbols

        Keyword Arguments:
            displayPercent: boolean
            chartRange: The range to use for the chart endpoint. Must be
            contained in _CHART_RANGE_VALUES
            dividendsRange: Range to use for the dividends endpoint. Must be
            contained in _DIVIDENDS_RANGE_VALUES
            splitsRange: Range to use for the splits endpoint. Must be
            contained in _SPLITS_RANGE_VALUES
            last: Range to use for the "last" attribute of the news endpoint.
        """
        self.symbolList = list(map(lambda x: x.upper(), args[0]))
        super(StockReader, self).__init__(*args, **kwargs)
        self.displayPercent = kwargs.pop('displayPercent', False)
        self.range = kwargs.pop('range', '1m')
        self.last = kwargs.pop('last', 10)

        # Parameter checking
        if not isinstance(self.displayPercent, bool):
            raise TypeError("displayPercent must be a boolean value")
        elif self.range not in self._RANGE_VALUES:
            raise ValueError("Invalid chart range.")
        elif int(self.last) > 50 or int(self.last) < 1:
            raise ValueError(
                "Invalid news last range. Enter a value between 1 and 50.")

    @property
    def key(self):
        raise NotImplementedError

    @property
    def params(self):
        params = {
            "symbols": self.symbolList
        }
        return params

    @property
    def url(self):
        return "stock"

    # universal selectors
    def get_select_endpoints(self, endpoints=[]):
        """
        Universal selector method to obtain custom endpoints from the data
        set. Will throw a IEXEndpointError if an invalid endpoint is specified
        and an IEXQueryError if the endpoint cannot be retrieved.

        Postional arguments:
            endpointList: A string or list of strings that specifies the
            endpoints desired
        """
        if type(endpoints) is str:
            endpoints = [endpoints]
        elif not endpoints:
            raise ValueError("Please provide a valid list of endpoints")
        result = {}
        for symbol in self.symbolList:
            temp = {}
            try:
                ds = self.data_set[symbol]
            except KeyError:
                IEXSymbolError(symbol)
            for endpoint in endpoints:
                try:
                    query = ds[endpoint]
                except KeyError:
                    raise IEXEndpointError(endpoint)
                temp.update({endpoint: query})
            result.update({symbol: temp})
        return result

    def get_select_datapoints(self, endpoint, attrList=[]):
        """
        Universal selector method to obtain custom datapoints from an
        individual endpoint. If an invalid endpoint is specified, throws an
        IEXEndpointError. If an invalid datapoint is specified, throws an
        IEXDatapointError. If there are issues with the query, throws an
        IEXQueryError.

        Positional Arguments:
            endpoint: A valid endpoint (string)
            attrList: A valid list of datapoints desired from the given
             endpoint
        """
        if type(attrList) is str:
            attrList = [attrList]
        result = {}
        if not attrList:
            raise ValueError("Please give a valid attribute list")
        for symbol in self.symbolList:
            try:
                ep = self.data_set[symbol][endpoint]
            except KeyError:
                raise IEXEndpointError(endpoint)
            temp = {}
            for attr in attrList:
                try:
                    query = ep[attr]
                except KeyError:
                    raise IEXDatapointError(endpoint, attr)
                temp.update({attr: query})
            result.update({symbol: temp})
        return result

    def refresh(self):
        try:
            self.data_set = self.fetch()
            if self.key == "Share":
                self.data_set = {self.symbolList[0]: self.data_set}
            for symbol in self.symbolList:
                if set(self.data_set[symbol]) != set(self._ENDPOINTS):
                    raise IEXQueryError()
        except KeyError:
            raise IEXQueryError()


class HistoricalReader(StockReader):
    """
    A class to download historical data from the chart endpoint

    Positional Arguments:
        symbol: A symbol or list of symbols
        start: A datetime object
        end: A datetime object

    Keyword Arguments:
        outputFormat: Desired output format (json by default)
    """

    def __init__(self, symbol, start, end, **kwargs):
        if isinstance(symbol, list) and len(symbol) > 1:
            self.type = "Batch"
            self.symlist = symbol
        elif isinstance(symbol, str):
            self.type = "Share"
            self.symlist = [symbol]
        else:
            raise TypeError("Please input a symbol or list of symbols")
        self.symbols = symbol
        self.start = start
        self.end = end
        self.outputFormat = kwargs.pop("outputFormat", "json")
        super(HistoricalReader, self).__init__(self.symlist, **kwargs)

    @property
    def url(self):
        return "stock/market/batch"

    @property
    def key(self):
        return self.type

    """ Calculates the chart range from start and end. Downloads larger
    datasets (5y and 2y) when necessary, but defaults to 1y for performance
    reasons
    """
    @property
    def chart_range(self):
        delta = relativedelta(self.start, datetime.datetime.now())
        if 2 <= (delta.years * -1) <= 5:
            return "5y"
        elif 1 <= (delta.years * -1) <= 2:
            return "2y"
        elif 0 <= (delta.years * -1) < 1:
            return "1y"
        else:
            raise ValueError(
                "Invalid date specified. Must be within past 5 years.")

    @property
    def params(self):
        if self.type is "Batch":
            syms = ",".join(self.symbols)
        else:
            syms = self.symbols
        params = {
            "symbols": syms,
            "types": "chart",
            "range": self.chart_range
        }
        return params

    def fetch(self):
        response = super(HistoricalReader, self).fetch()
        for sym in self.symlist:
            if sym not in list(response):
                raise IEXSymbolError(sym)
        return self._output_format(response)

    def _output_format(self, out):
        result = {}
        if self.key is "Share":
            syms = [self.symbols]
        else:
            syms = self.symbols
        for symbol in syms:
            d = out.pop(symbol)["chart"]
            df = pandas.DataFrame(d)
            df.set_index("date", inplace=True)
            values = ["open", "high", "low", "close", "volume"]
            df = df[values]
            sstart = self.start.strftime('%Y-%m-%d')
            send = self.end.strftime('%Y-%m-%d')
            df = df.loc[sstart:send]
            result.update({symbol: df})
        if self.outputFormat is "pandas":
            if len(result) > 1:
                return result
            return result[self.symbols]
        else:
            for sym in list(result):
                result[sym] = result[sym].to_dict('index')
            return result


class Share(StockReader):
    """
    Class to handle individual shares. Inherits _IEXBase, which will conduct
    the API queries
    """

    def __init__(self, symbol, **kwargs):
        """
        Initializes the class.

        Positional arguments:
            symbol: A valid ticker symbol
        Keyword arguments:
            options: Again a pass through to the _IEXBase class, which will
            be supered here. Options checked in the parent class.
        """
        self.symbol = symbol.upper()
        self.symbolList = [self.symbol]
        super(Share, self).__init__(self.symbolList, **kwargs)
        self.refresh()

    @property
    def key(self):
        return 'Share'

    @property
    def params(self):
        return {"types": self._ALL_ENDPOINTS_STR}

    @property
    def url(self):
        return 'stock/{}/batch'.format(self.symbol)

    def refresh(self):
        super(Share, self).refresh()
        self.data_set = self.data_set[self.symbol]

    # universal selectors

    def get_select_endpoints(self, endpointList=[]):
        """
        Universal selector method to obtain custom endpoints from the data
        set. Will throw a IEXEndpointError if an invalid endpoint is specified
        and an IEXQueryError if the endpoint cannot be retrieved.

        Postional arguments:
            endpointList: A string or list of strings that specifies the
            endpoints desired
        """
        result = super(Share, self).get_select_endpoints(endpointList)
        return result[self.symbol]

    def get_select_datapoints(self, endpoint, attrList=[]):
        """
        Universal selector method to obtain custom datapoints from an
        individual endpoint. If an invalid endpoint is specified, throws an
        IEXEndpointError. If an invalid datapoint is specified, throws an
        IEXDatapointError. If there are issues with the query, throws an
        IEXQueryError.

        Positional Arguments:
            endpoint: A valid endpoint (string)
            attrList: A valid list of datapoints desired from the given
            endpoint
        """
        result = super(Share, self).get_select_endpoints(endpoint, attrList)
        return result[self.symbol]

    # endpoint methods

    def get_quote(self):
        return self.data_set["quote"]

    def get_chart(self):
        return self.data_set["chart"]

    def get_book(self):
        return self.data_set["book"]

    def get_open_close(self):
        return self.data_set["open-close"]  # fix

    def get_previous(self):
        return self.data_set["previous"]

    def get_company(self):
        return self.data_set["company"]

    def get_key_stats(self):
        return self.data_set["stats"]  # fix

    def get_peers(self):
        return self.data_set["peers"]

    def get_relevant(self):
        return self.data_set["relevant"]

    def get_news(self):
        return self.data_set["news"]

    def get_financials(self):
        return self.data_set["financials"]

    def get_earnings(self):
        return self.data_set["earnings"]

    def get_logo(self):
        return self.data_set["logo"]

    def get_price(self):
        return self.data_set["price"]

    def get_delayed_quote(self):
        return self.data_set["delayed-quote"]  # fix

    def get_effective_spread(self):
        return self.data_set["effective-spread"]  # fix

    def get_volume_by_venue(self):
        return self.data_set["volume-by-venue"]  # fix

    def get_all(self):
        return self.data_set

    def get_yesterdays_close(self):
        return self.data_set["previousClose"]

    def get_dividends(self):
        return self.data_set["dividends"]

    def get_splits(self):
        return self.data_set["splits"]

    # datapoint methods
    def get_company_name(self):
        return self.get_quote()["companyName"]

    def get_primary_exchange(self):
        return self.get_quote()["primaryExchange"]

    def get_sector(self):
        return self.get_quote()["sector"]

    def get_symbol(self):
        return self.get_quote()["symbol"]

    def get_open(self):
        return self.get_quote()["open"]

    def get_close(self):
        return self.get_quote()["close"]

    def get_years_high(self):
        return self.get_quote()["week52High"]

    def get_years_low(self):
        return self.get_quote()["week52Low"]

    def get_ytd_change(self):
        return self.get_quote()["ytdChange"]

    def get_volume(self):
        return self.get_quote()["latestVolume"]

    def get_market_cap(self):
        return self.get_quote()["marketCap"]

    def get_beta(self):
        return self.get_key_stats()["beta"]

    def get_short_interest(self):
        return self.get_key_stats()["shortInterest"]

    def get_short_ratio(self):
        return self.get_key_stats()["shortRatio"]

    def get_latest_eps(self):
        return self.get_key_stats()["latestEPS"]

    def get_shares_outstanding(self):
        return self.get_key_stats()["sharesOutstanding"]

    def get_float(self):
        return self.get_key_stats()["float"]

    def get_eps_consensus(self):
        return self.get_key_stats()["consensusEPS"]


class Batch(StockReader):
    """
    Class to handle multiple shares. Inherits _IEXBase, which will conduct
    the API queries.
    """

    def __init__(self, symbolList, **kwargs):
        """
        Initializes the class.

        Positional arguments:
            symbol: A valid ticker symbol
        Keyword arguments:
            options: Again a pass through to the _IEXBase class, which will
            be supered here. Options checked in the parent class.
        """
        super(Batch, self).__init__(symbolList, **kwargs)
        self.refresh()

    def refresh(self):
        data = self.fetch()
        for sym in self.symbolList:
            if sym not in list(data):
                raise IEXSymbolError(sym)
        self.data_set = data

    @property
    def key(self):
        return 'Batch'

    @property
    def url(self):
        return 'stock/market/batch'

    @property
    def params(self):
        params = {
            "symbols": ','.join(self.symbolList),
            "types": self._ALL_ENDPOINTS_STR
        }
        return params

    def get_all(self):
        return self.data_set

    # endpoint methods
    def get_quote(self):
        return {symbol: self.data_set[symbol]["quote"] for symbol in
                self.data_set.keys()}

    def get_book(self):
        return {symbol: self.data_set[symbol]["book"] for symbol in
                self.data_set.keys()}

    def get_chart(self):
        return {symbol: self.data_set[symbol]["chart"] for symbol in
                self.data_set.keys()}

    def get_open_close(self):
        return {symbol: self.data_set[symbol]["open-close"] for symbol in
                self.data_set.keys()}

    def get_previous(self):
        return {symbol: self.data_set[symbol]["previous"] for symbol in
                self.data_set.keys()}

    def get_company(self):
        return {symbol: self.data_set[symbol]["company"] for symbol in
                self.data_set.keys()}

    def get_key_stats(self):
        return {symbol: self.data_set[symbol]["stats"] for symbol in
                self.data_set.keys()}

    def get_peers(self):
        return {symbol: self.data_set[symbol]["peers"] for symbol in
                self.data_set.keys()}

    def get_relevant(self):
        return {symbol: self.data_set[symbol]["relevant"] for symbol in
                self.data_set.keys()}

    def get_news(self):
        return {symbol: self.data_set[symbol]["news"] for symbol in
                self.data_set.keys()}

    def get_financials(self):
        return {symbol: self.data_set[symbol]["financials"] for symbol in
                self.data_set.keys()}

    def get_earnings(self):
        return {symbol: self.data_set[symbol]["earnings"] for symbol in
                self.data_set.keys()}

    def get_dividends(self):
        return {symbol: self.data_set[symbol]["dividends"] for symbol in
                self.data_set.keys()}

    def get_splits(self):
        return {symbol: self.data_set[symbol]["splits"] for symbol in
                self.data_set.keys()}

    def get_logo(self):
        return {symbol: self.data_set[symbol]["logo"] for symbol in
                self.data_set.keys()}

    def get_price(self):
        return {symbol: self.data_set[symbol]["price"] for symbol in
                self.data_set.keys()}

    def get_delayed_quote(self):
        return {symbol: self.data_set[symbol]["delayed-quote"] for symbol in
                self.data_set.keys()}

    def get_effective_spread(self):
        return {symbol: self.data_set[symbol]["effective-spread"] for symbol
                in self.data_set.keys()}

    def get_volume_by_venue(self):
        return {symbol: self.data_set[symbol]["volume-by-venue"] for symbol
                in self.data_set.keys()}

    # datapoint methods
    def get_company_name(self):
        return {symbol: self.get_quote()[symbol]["companyName"] for symbol in
                self.data_set.keys()}

    def get_primary_exchange(self):
        return {symbol: self.get_quote()[symbol]["primaryExchange"] for symbol
                in self.data_set.keys()}

    def get_sector(self):
        return {symbol: self.get_quote()[symbol]["sector"] for symbol in
                self.data_set.keys()}

    def get_open(self):
        return {symbol: self.get_quote()[symbol]["open"] for symbol in
                self.data_set.keys()}

    def get_close(self):
        return {symbol: self.get_quote()[symbol]["close"] for symbol in
                self.data_set.keys()}

    def get_years_high(self):
        return {symbol: self.get_quote()[symbol]["week52High"] for symbol in
                self.data_set.keys()}

    def get_years_low(self):
        return {symbol: self.get_quote()[symbol]["week52Low"] for symbol in
                self.data_set.keys()}

    def get_ytd_change(self):
        return {symbol: self.get_quote()[symbol]["ytdChange"] for symbol in
                self.data_set.keys()}

    def get_volume(self):
        return {symbol: self.get_quote()[symbol]["latestVolume"] for symbol in
                self.data_set.keys()}

    def get_market_cap(self):
        return {symbol: self.get_quote()[symbol]["marketCap"]for symbol in
                self.data_set.keys()}

    def get_beta(self):
        return {symbol: self.get_key_stats()[symbol]["beta"] for symbol in
                self.data_set.keys()}

    def get_short_interest(self):
        return {symbol: self.get_key_stats()[symbol]["shortInterest"] for
                symbol in self.data_set.keys()}

    def get_short_ratio(self):
        return {symbol: self.get_key_stats()[symbol]["shortRatio"] for
                symbol in self.data_set.keys()}

    def get_latest_eps(self):
        return {symbol: self.get_key_stats()[symbol]["latestEPS"] for symbol
                in self.data_set.keys()}

    def get_shares_outstanding(self):
        return {symbol: self.get_key_stats()[symbol]["sharesOutstanding"] for
                symbol in self.data_set.keys()}

    def get_float(self):
        return {symbol: self.get_key_stats()[symbol]["float"] for symbol in
                self.data_set.keys()}

    def get_eps_consensus(self):
        return {symbol: self.get_key_stats()[symbol]["consensusEPS"] for
                symbol in self.data_set.keys()}
