"""TradingView screener client for NSE stocks.

Talks to TradingView's public screener endpoint (scanner.tradingview.com), the
same one the TradingView website and connector use. It is unofficial: no key,
no SLA, delayed data, and it can change or rate-limit without notice.

Offline mode, for demos and for environments that cannot reach TradingView:
set NSE_SCANNER_OFFLINE to one or more saved screener results (JSON with a
"data" list, separated by os.pathsep) and optionally NSE_SCANNER_OFFLINE_REGIME
to a JSON object {"NSE:CNX500": {"close": ..., "sma50": ..., ...}, ...}.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

SCAN_URL = "https://scanner.tradingview.com/{market}/scan"
NEWS_URL = "https://news-headlines.tradingview.com/v2/headlines?client=web&lang=en&streaming=false&symbol={symbol}"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
    "User-Agent": "Mozilla/5.0 (nse-scanner)",
}
TIMEOUT = 30
MIN_GAP = 1.5          # seconds between screener requests from this server
RETRY_WAITS = (2, 5, 10)  # back-off before each retry when TradingView says "too many requests"
MAX_RETRY_WAIT = 15    # never honour a longer Retry-After than this inside one request
_lock = threading.Lock()
_last_call = [0.0]

# Raw TradingView column names; norm_key() turns them into the keys score.py reads.
COLUMNS = [
    "name", "description", "sector", "indexes",
    "close", "change", "high", "relative_volume_10d_calc", "average_volume_30d_calc",
    "High.1M", "High.3M", "price_52_week_high", "SMA20", "SMA50", "SMA200",
    "RSI", "MACD.macd", "MACD.signal", "ATR", "Perf.3M", "Perf.6M",
    "market_cap_basic", "price_earnings_ttm", "peg_ratio", "return_on_equity_fq",
    "return_on_invested_capital_ttm", "net_margin_ttm",
    "earnings_per_share_diluted_yoy_growth_ttm", "total_revenue_yoy_growth_ttm",
    "debt_to_equity_fq", "free_cash_flow_ttm", "net_income_ttm",
]
REGIME_COLUMNS = ["description", "close", "change", "SMA50", "SMA200", "RSI"]
REGIME_TICKERS = ["NSE:CNX500", "NSE:NIFTY"]

# Largest-first page ranges needed to cover each index.
PAGES = {
    "NIFTY": [(0, 300)],
    "CNX100": [(0, 300)],
    "CNX200": [(0, 500)],
    "NIFTYMIDCAP150": [(0, 500), (500, 900)],
    "CNX500": [(0, 500), (500, 900)],
    "NIFTYSMLCAP250": [(0, 500), (500, 900), (900, 1400)],
    "ALL": [(0, 500), (500, 900)],
}


class TradingViewError(RuntimeError):
    pass


class RateLimited(TradingViewError):
    """TradingView kept answering 429 Too Many Requests after our retries."""


def norm_key(k):
    return k.lower().replace(".", "_")


def rows_from_scan(payload, columns):
    """Turn the screener's {"data": [{"s": sym, "d": [values]}]} into dicts."""
    rows = []
    for item in payload.get("data") or []:
        values = item.get("d") or []
        row = {norm_key(c): (values[i] if i < len(values) else None) for i, c in enumerate(columns)}
        row["symbol"] = item.get("s")
        rows.append(row)
    return rows


def _retry_after(err, default):
    try:
        return min(max(float(err.headers.get("Retry-After")), 1.0), MAX_RETRY_WAIT)
    except (TypeError, ValueError, AttributeError):
        return default


def _post(url, body):
    """POST to the screener, one request at a time, retrying 429 / 503 with back-off."""
    data = json.dumps(body).encode()
    with _lock:
        for attempt in range(len(RETRY_WAITS) + 1):
            gap = MIN_GAP - (time.monotonic() - _last_call[0])
            if gap > 0:
                time.sleep(gap)
            _last_call[0] = time.monotonic()
            req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code not in (429, 503):
                    raise TradingViewError("TradingView screener request failed: HTTP %s %s" % (e.code, e.reason)) from e
                if attempt == len(RETRY_WAITS):
                    raise RateLimited("TradingView is limiting requests from this server (HTTP %s)" % e.code) from e
                time.sleep(_retry_after(e, RETRY_WAITS[attempt]))
            except Exception as e:  # network or JSON errors mean "no data"
                raise TradingViewError("TradingView screener request failed: %s" % e) from e


def offline_files():
    raw = os.environ.get("NSE_SCANNER_OFFLINE", "").strip()
    return [p for p in raw.split(os.pathsep) if p] if raw else []


def is_offline():
    return bool(offline_files())


def fetch_stocks(universe):
    """Rows for the NSE stocks needed to cover `universe`, largest first."""
    files = offline_files()
    if files:
        rows = []
        for path in files:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            for r in doc.get("data", []) if isinstance(doc, dict) else doc:
                rows.append({norm_key(k): v for k, v in r.items()})
        return rows
    rows = []
    for start, end in PAGES.get(universe, PAGES["CNX500"]):
        body = {
            "markets": ["india"],
            "filter": [{"left": "exchange", "operation": "equal", "right": "NSE"}],
            "options": {"lang": "en"},
            "columns": COLUMNS,
            "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
            "range": [start, end],
        }
        rows += rows_from_scan(_post(SCAN_URL.format(market="india"), body), COLUMNS)
    return rows


def fetch_regime():
    """{ticker: {close, change, sma50, sma200, rsi, description}} for the index tickers."""
    if is_offline():
        path = os.environ.get("NSE_SCANNER_OFFLINE_REGIME", "").strip()
        if not path:
            return {}
        with open(path, encoding="utf-8") as f:
            return {t: {norm_key(k): v for k, v in d.items()} for t, d in json.load(f).items()}
    body = {"symbols": {"tickers": REGIME_TICKERS}, "columns": REGIME_COLUMNS}
    rows = rows_from_scan(_post(SCAN_URL.format(market="india"), body), REGIME_COLUMNS)
    return {r.pop("symbol"): r for r in rows}


def fetch_news(symbol, limit=8):
    """Latest headlines for one symbol; [] when offline or unavailable."""
    if is_offline():
        return []
    req = urllib.request.Request(NEWS_URL.format(symbol=symbol), headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            doc = json.loads(resp.read().decode())
    except Exception:
        return []
    items = doc.get("items", doc) if isinstance(doc, dict) else doc
    out = []
    for it in (items or [])[:limit]:
        out.append({
            "title": it.get("title"),
            "published": it.get("published"),
            "source": (it.get("provider") or {}).get("name") if isinstance(it.get("provider"), dict) else it.get("source"),
            "url": "https://www.tradingview.com" + it["storyPath"] if it.get("storyPath") else it.get("link"),
        })
    return out


class TTLCache:
    def __init__(self, seconds):
        self.seconds = seconds
        self._store = {}

    def get(self, key):
        hit = self._store.get(key)
        if hit and time.time() - hit[0] < self.seconds:
            return hit
        return None

    def last(self, key):
        """The newest value however old, or None: a fallback when a refresh fails."""
        return self._store.get(key)

    def put(self, key, value):
        self._store[key] = (time.time(), value)
        return self._store[key]
