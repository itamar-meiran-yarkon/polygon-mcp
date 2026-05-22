#!/usr/bin/env python3
import os
import json
import ssl
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
import certifi
from mcp.server.fastmcp import FastMCP

_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

API_KEY = os.environ.get("POLYGON_API_KEY", "")
BASE_URL = "https://api.polygon.io"

mcp = FastMCP("polygon")


def _get(path: str, params: dict = None) -> dict:
    p = params or {}
    p["apiKey"] = API_KEY
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(p)}"
    with urllib.request.urlopen(url, timeout=15, context=_SSL_CTX) as r:
        return json.loads(r.read())


@mcp.tool()
def get_stock_quote(ticker: str) -> str:
    """Get the latest quote/snapshot for a stock ticker (price, bid, ask, volume, etc.)."""
    ticker = ticker.upper()
    data = _get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}")
    snap = data.get("ticker", {})
    day = snap.get("day", {})
    prev = snap.get("prevDay", {})
    lp = snap.get("lastTrade", {})
    return json.dumps({
        "ticker": ticker,
        "last_price": lp.get("p"),
        "open": day.get("o"),
        "high": day.get("h"),
        "low": day.get("l"),
        "close": day.get("c"),
        "volume": day.get("v"),
        "vwap": day.get("vw"),
        "prev_close": prev.get("c"),
        "change_pct": snap.get("todaysChangePerc"),
        "change": snap.get("todaysChange"),
    }, indent=2)


@mcp.tool()
def get_ticker_details(ticker: str) -> str:
    """Get company details for a ticker: name, description, sector, market cap, exchange, website, etc."""
    ticker = ticker.upper()
    data = _get(f"/v3/reference/tickers/{ticker}")
    r = data.get("results", {})
    return json.dumps({
        "ticker": r.get("ticker"),
        "name": r.get("name"),
        "description": r.get("description"),
        "market_cap": r.get("market_cap"),
        "employees": r.get("total_employees"),
        "exchange": r.get("primary_exchange"),
        "sector": r.get("sic_description"),
        "currency": r.get("currency_name"),
        "homepage": r.get("homepage_url"),
        "list_date": r.get("list_date"),
        "share_class_shares_outstanding": r.get("share_class_shares_outstanding"),
        "weighted_shares_outstanding": r.get("weighted_shares_outstanding"),
    }, indent=2)


@mcp.tool()
def get_historical_bars(ticker: str, from_date: str = None, to_date: str = None,
                        timespan: str = "day", multiplier: int = 1, limit: int = 30) -> str:
    """Get OHLCV bars for a ticker.

    Args:
        ticker: Stock symbol (e.g. AAPL)
        from_date: Start date YYYY-MM-DD (default: 30 days ago)
        to_date: End date YYYY-MM-DD (default: today)
        timespan: minute, hour, day, week, month, quarter, year
        multiplier: Size of the timespan (e.g. 5 for 5-minute bars)
        limit: Max number of bars to return (max 50000)
    """
    ticker = ticker.upper()
    if not to_date:
        to_date = datetime.now().strftime("%Y-%m-%d")
    if not from_date:
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    data = _get(
        f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
        {"adjusted": "true", "sort": "asc", "limit": limit}
    )
    results = data.get("results", [])
    bars = [
        {
            "date": datetime.fromtimestamp(b["t"] / 1000).strftime("%Y-%m-%d %H:%M"),
            "open": b.get("o"), "high": b.get("h"), "low": b.get("l"),
            "close": b.get("c"), "volume": b.get("v"), "vwap": b.get("vw"),
        }
        for b in results
    ]
    return json.dumps({"ticker": ticker, "count": len(bars), "bars": bars}, indent=2)


@mcp.tool()
def search_tickers(query: str, asset_class: str = "stocks", limit: int = 10) -> str:
    """Search for tickers by company name or symbol.

    Args:
        query: Company name or partial ticker
        asset_class: stocks, crypto, fx, indices, options
        limit: Number of results (max 1000)
    """
    data = _get("/v3/reference/tickers", {
        "search": query, "market": asset_class, "active": "true", "limit": limit
    })
    results = [
        {"ticker": r.get("ticker"), "name": r.get("name"),
         "market": r.get("market"), "exchange": r.get("primary_exchange"),
         "currency": r.get("currency_name")}
        for r in data.get("results", [])
    ]
    return json.dumps(results, indent=2)


@mcp.tool()
def get_market_status() -> str:
    """Check whether the US stock market is currently open or closed."""
    data = _get("/v1/marketstatus/now")
    return json.dumps({
        "market": data.get("market"),
        "server_time": data.get("serverTime"),
        "exchanges": data.get("exchanges"),
        "currencies": data.get("currencies"),
    }, indent=2)


@mcp.tool()
def get_ticker_news(ticker: str, limit: int = 10) -> str:
    """Get recent news articles for a ticker.

    Args:
        ticker: Stock symbol (e.g. TSLA)
        limit: Number of articles to return (max 1000)
    """
    ticker = ticker.upper()
    data = _get("/v2/reference/news", {"ticker": ticker, "limit": limit, "order": "desc"})
    articles = [
        {
            "title": a.get("title"),
            "published": a.get("published_utc"),
            "author": a.get("author"),
            "publisher": a.get("publisher", {}).get("name"),
            "url": a.get("article_url"),
            "tickers": a.get("tickers"),
            "summary": (a.get("description") or "")[:300],
        }
        for a in data.get("results", [])
    ]
    return json.dumps(articles, indent=2)


@mcp.tool()
def get_financials(ticker: str, limit: int = 4) -> str:
    """Get fundamental financial data (income statement, balance sheet, cash flow) for a ticker.

    Args:
        ticker: Stock symbol (e.g. MSFT)
        limit: Number of reporting periods to return
    """
    ticker = ticker.upper()
    data = _get("/vX/reference/financials", {
        "ticker": ticker, "limit": limit, "sort": "filing_date", "order": "desc"
    })
    results = []
    for r in data.get("results", []):
        fin = r.get("financials", {})
        ic = fin.get("income_statement", {})
        bs = fin.get("balance_sheet", {})
        cf = fin.get("cash_flow_statement", {})
        results.append({
            "period": r.get("fiscal_period"),
            "fiscal_year": r.get("fiscal_year"),
            "filing_date": r.get("filing_date"),
            "revenues": ic.get("revenues", {}).get("value"),
            "net_income": ic.get("net_income_loss", {}).get("value"),
            "gross_profit": ic.get("gross_profit", {}).get("value"),
            "operating_income": ic.get("operating_income_loss", {}).get("value"),
            "eps_basic": ic.get("basic_earnings_per_share", {}).get("value"),
            "total_assets": bs.get("assets", {}).get("value"),
            "total_liabilities": bs.get("liabilities", {}).get("value"),
            "equity": bs.get("equity", {}).get("value"),
            "operating_cash_flow": cf.get("net_cash_flow_from_operating_activities", {}).get("value"),
        })
    return json.dumps(results, indent=2)


@mcp.tool()
def get_options_chain(ticker: str, expiration_date: str = None,
                      contract_type: str = None, limit: int = 20) -> str:
    """Get options contracts for a ticker.

    Args:
        ticker: Underlying stock symbol (e.g. SPY)
        expiration_date: YYYY-MM-DD filter (optional)
        contract_type: 'call' or 'put' (optional)
        limit: Number of contracts to return
    """
    ticker = ticker.upper()
    params = {"underlying_ticker": ticker, "limit": limit, "sort": "expiration_date"}
    if expiration_date:
        params["expiration_date"] = expiration_date
    if contract_type:
        params["contract_type"] = contract_type
    data = _get("/v3/reference/options/contracts", params)
    results = [
        {
            "symbol": r.get("ticker"),
            "type": r.get("contract_type"),
            "strike": r.get("strike_price"),
            "expiration": r.get("expiration_date"),
            "exercise_style": r.get("exercise_style"),
            "shares_per_contract": r.get("shares_per_contract"),
        }
        for r in data.get("results", [])
    ]
    return json.dumps(results, indent=2)


@mcp.tool()
def get_crypto_quote(symbol: str) -> str:
    """Get snapshot/quote for a crypto pair (e.g. BTC-USD, ETH-USD).

    Args:
        symbol: Crypto pair like BTC-USD or BTCUSD
    """
    symbol = symbol.upper().replace("-", "")
    ticker = f"X:{symbol}"
    data = _get(f"/v2/snapshot/locale/global/markets/crypto/tickers/{ticker}")
    snap = data.get("ticker", {})
    day = snap.get("day", {})
    return json.dumps({
        "ticker": ticker,
        "last_price": snap.get("lastTrade", {}).get("p"),
        "open": day.get("o"),
        "high": day.get("h"),
        "low": day.get("l"),
        "close": day.get("c"),
        "volume": day.get("v"),
        "change_pct": snap.get("todaysChangePerc"),
    }, indent=2)


@mcp.tool()
def get_dividends(ticker: str, limit: int = 10) -> str:
    """Get dividend history for a ticker.

    Args:
        ticker: Stock symbol
        limit: Number of records
    """
    ticker = ticker.upper()
    data = _get("/v3/reference/dividends", {
        "ticker": ticker, "limit": limit, "sort": "ex_dividend_date", "order": "desc"
    })
    results = [
        {
            "ex_date": r.get("ex_dividend_date"),
            "pay_date": r.get("pay_date"),
            "record_date": r.get("record_date"),
            "cash_amount": r.get("cash_amount"),
            "frequency": r.get("frequency"),
            "type": r.get("dividend_type"),
        }
        for r in data.get("results", [])
    ]
    return json.dumps(results, indent=2)


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport in ("http", "sse"):
        port = int(os.environ.get("PORT", 8000))
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = port
        mcp.run(transport="streamable-http" if transport == "http" else "sse")
    else:
        mcp.run()
