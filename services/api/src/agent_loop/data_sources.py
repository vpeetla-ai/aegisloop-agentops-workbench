from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO

import httpx


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    name: str
    last: str
    change_pct: str
    volume: str
    source: str = "unknown"


@dataclass(frozen=True)
class MarketMover:
    symbol: str
    name: str
    price: str
    change_pct: str
    volume: str
    source: str


@dataclass(frozen=True)
class MarketSnapshot:
    as_of: str
    source_status: dict[str, str]
    quotes: list[MarketQuote]
    top_gainers: list[MarketMover]
    top_losers: list[MarketMover]
    most_active: list[MarketMover]


YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}

MARKETBEAT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}


def _fmt_price(value: object) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_pct(value: object) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        text = str(value)
        return text if text.endswith("%") else f"{text}%"


def _fmt_volume(value: object) -> str:
    if value in (None, "", "n/a"):
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.2f}B"
    if number >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"
    if number >= 1_000:
        return f"{number / 1_000:.1f}K"
    return str(int(number))


async def fetch_yahoo_quotes() -> tuple[list[MarketQuote], str]:
    symbols = "^GSPC,^DJI,^IXIC,^RUT,SPY,QQQ,DIA,IWM,VTI,TLT,GLD"
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}"
    try:
        async with httpx.AsyncClient(timeout=8, headers=YAHOO_HEADERS, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code == 429:
                return [], "rate_limited"
            response.raise_for_status()
        results = response.json().get("quoteResponse", {}).get("result", [])
        quotes = [
            MarketQuote(
                symbol=item.get("symbol", ""),
                name=item.get("shortName") or item.get("longName") or item.get("symbol", ""),
                last=_fmt_price(item.get("regularMarketPrice")),
                change_pct=_fmt_pct(item.get("regularMarketChangePercent")),
                volume=_fmt_volume(item.get("regularMarketVolume")),
                source="Yahoo Finance quote",
            )
            for item in results
            if item.get("symbol")
        ]
        return quotes, "live"
    except Exception as exc:
        return [], f"unavailable: {exc.__class__.__name__}"


async def fetch_yahoo_movers(scr_id: str, source_name: str) -> tuple[list[MarketMover], str]:
    url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds={scr_id}&count=10"
    try:
        async with httpx.AsyncClient(timeout=8, headers=YAHOO_HEADERS, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code == 429:
                return [], "rate_limited"
            response.raise_for_status()
        quotes = response.json()["finance"]["result"][0]["quotes"]
        movers = [
            MarketMover(
                symbol=item.get("symbol", ""),
                name=item.get("shortName") or item.get("longName") or item.get("symbol", ""),
                price=_fmt_price(item.get("regularMarketPrice")),
                change_pct=_fmt_pct(item.get("regularMarketChangePercent")),
                volume=_fmt_volume(item.get("regularMarketVolume")),
                source=source_name,
            )
            for item in quotes
            if item.get("symbol")
        ]
        return movers, "live"
    except Exception as exc:
        return [], f"unavailable: {exc.__class__.__name__}"


def parse_marketbeat_movers(html: str, source_name: str, limit: int = 10) -> list[MarketMover]:
    rows = re.findall(r"<tr>(.*?)</tr>", html, flags=re.S)
    movers: list[MarketMover] = []
    for row in rows:
        company = re.search(r'<td data-clean="([^"|]+)\|([^"]+)"', row)
        cells = re.findall(r'<td[^>]*data-clean="([^"]+)"[^>]*>', row)
        if not company or len(cells) < 3:
            continue
        symbol, name = company.group(1), company.group(2)
        if symbol == "Symbol" or not re.match(r"^[A-Z.]{1,8}$", symbol):
            continue
        price = cells[1]
        change_pct = cells[2].replace("+", "")
        volume_match = re.search(r'<td data-sort-value="([0-9.]+)">([^<]+)</td>', row)
        volume = volume_match.group(2) if volume_match else "n/a"
        signed_change = change_pct if change_pct.startswith("-") else f"+{change_pct}"
        movers.append(MarketMover(symbol, name, price, signed_change, volume, source_name))
        if len(movers) >= limit:
            break
    return movers


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.replace("&amp;", "&").replace("&#39;", "'").strip()


def _clean_money(value: str) -> str:
    value = _strip_html(value)
    match = re.search(r"\$?\s*-?\d[\d,]*(?:\.\d+)?", value)
    if not match:
        return "n/a"
    number = match.group(0).replace(" ", "")
    return number if number.startswith("$") else f"${number}"


def _clean_percent(value: str) -> str:
    value = _strip_html(value)
    match = re.search(r"[+-]?\d+(?:\.\d+)?%", value)
    return match.group(0) if match else "n/a"


def _looks_like_volume(value: str) -> bool:
    value = value.lower()
    return bool(re.search(r"\d", value) and ("million" in value or "billion" in value or "," in value or re.search(r"\d{4,}", value)))


def parse_marketbeat_active(html: str, source_name: str, limit: int = 10) -> list[MarketMover]:
    rows = re.findall(r"<tr>(.*?)</tr>", html, flags=re.S)
    movers: list[MarketMover] = []
    for row in rows:
        company = re.search(r'<td data-clean="([^"|]+)\|([^"]+)"', row)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)
        if not company or len(cells) < 3:
            continue
        symbol, name = company.group(1), company.group(2)
        if symbol == "Symbol" or not re.match(r"^[A-Z.]{1,8}$", symbol):
            continue
        text_cells = [_strip_html(cell) for cell in cells]
        price = "n/a"
        change_pct = "n/a"
        volume = "n/a"
        for cell in text_cells[1:]:
            if change_pct == "n/a" and "%" in cell:
                change_pct = _clean_percent(cell)
            if volume == "n/a" and _looks_like_volume(cell) and "$" not in cell and "%" not in cell:
                volume = cell
        # MarketBeat's most-active table can mix delayed/fair-value and dollar-volume fields.
        # Keep the volume ranking, but do not label a scraped money field as a live quote.
        price = "n/a"
        if price == "n/a" and change_pct == "n/a" and volume == "n/a":
            continue
        movers.append(MarketMover(symbol, name, price, change_pct, volume, source_name))
        if len(movers) >= limit:
            break
    return movers


async def fetch_marketbeat_movers(kind: str) -> tuple[list[MarketMover], str]:
    slug = "biggest-percentage-gainers" if kind == "gainers" else "biggest-percentage-decliners"
    url = f"https://www.marketbeat.com/market-data/{slug}/"
    try:
        async with httpx.AsyncClient(timeout=10, headers=MARKETBEAT_HEADERS, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        movers = parse_marketbeat_movers(response.text, f"MarketBeat {kind}")
        return movers, "live_public_page" if movers else "empty"
    except Exception as exc:
        return [], f"unavailable: {exc.__class__.__name__}"


async def fetch_marketbeat_active() -> tuple[list[MarketMover], str]:
    url = "https://www.marketbeat.com/market-data/most-active-stocks/"
    try:
        async with httpx.AsyncClient(timeout=10, headers=MARKETBEAT_HEADERS, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        movers = parse_marketbeat_active(response.text, "MarketBeat most active")
        return movers, "live_public_page" if movers else "empty"
    except Exception as exc:
        return [], f"unavailable: {exc.__class__.__name__}"


async def fetch_stooq_quotes() -> tuple[list[MarketQuote], str]:
    url = "https://stooq.com/q/l/?s=spy.us,qqq.us,dia.us,iwm.us,tlt.us,gld.us&f=sd2t2ohlcv&h&e=csv"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(url)
            response.raise_for_status()
        rows = list(csv.DictReader(StringIO(response.text)))
        quotes = []
        names = {
            "SPY.US": "S&P 500 ETF",
            "QQQ.US": "Nasdaq 100 ETF",
            "DIA.US": "Dow ETF",
            "IWM.US": "Russell 2000 ETF",
            "TLT.US": "20Y Treasury ETF",
            "GLD.US": "Gold ETF",
        }
        for row in rows:
            symbol = row.get("Symbol", "")
            close = float(row.get("Close") or 0)
            open_price = float(row.get("Open") or close or 1)
            change_pct = ((close - open_price) / open_price) * 100 if open_price else 0
            quotes.append(
                MarketQuote(
                    symbol=symbol,
                    name=names.get(symbol, symbol),
                    last=f"{close:.2f}",
                    change_pct=f"{change_pct:+.2f}%",
                    volume=row.get("Volume", "n/a"),
                    source="Stooq quote fallback",
                )
            )
        return quotes, "live_fallback"
    except Exception as exc:
        return [], f"unavailable: {exc.__class__.__name__}"


async def fetch_market_quotes() -> list[MarketQuote]:
    quotes, yahoo_status = await fetch_yahoo_quotes()
    if quotes:
        return quotes
    stooq_quotes, _ = await fetch_stooq_quotes()
    return stooq_quotes or [
            MarketQuote("SPY", "S&P 500 proxy", "n/a", "mixed", "n/a"),
            MarketQuote("QQQ", "Nasdaq 100 proxy", "n/a", "mixed", "n/a"),
            MarketQuote("TLT", "Treasury duration proxy", "n/a", "watch", "n/a"),
        ]


async def fetch_market_snapshot() -> MarketSnapshot:
    source_status: dict[str, str] = {
        "Bloomberg": "not_configured: licensed API required",
        "Charles Schwab": "not_configured: OAuth brokerage API required",
        "Google Finance": "not_configured: no stable official public API",
    }
    quotes, source_status["Yahoo Finance quotes"] = await fetch_yahoo_quotes()
    if not quotes:
        quotes, source_status["Stooq quotes"] = await fetch_stooq_quotes()
    if not quotes:
        quotes = [
            MarketQuote("SPY", "S&P 500 proxy", "n/a", "mixed", "n/a"),
            MarketQuote("QQQ", "Nasdaq 100 proxy", "n/a", "mixed", "n/a"),
            MarketQuote("TLT", "Treasury duration proxy", "n/a", "watch", "n/a"),
        ]
        source_status["Quote fallback"] = "deterministic"

    gainers, source_status["Yahoo Finance day_gainers"] = await fetch_yahoo_movers("day_gainers", "Yahoo Finance day_gainers")
    if not gainers:
        gainers, source_status["MarketBeat percentage gainers"] = await fetch_marketbeat_movers("gainers")

    losers, source_status["Yahoo Finance day_losers"] = await fetch_yahoo_movers("day_losers", "Yahoo Finance day_losers")
    if not losers:
        losers, source_status["MarketBeat percentage decliners"] = await fetch_marketbeat_movers("losers")

    active, source_status["Yahoo Finance most_actives"] = await fetch_yahoo_movers("most_actives", "Yahoo Finance most_actives")
    if not active:
        active, source_status["MarketBeat most active"] = await fetch_marketbeat_active()

    return MarketSnapshot(
        as_of=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source_status=source_status,
        quotes=quotes,
        top_gainers=gainers,
        top_losers=losers,
        most_active=active,
    )


async def fetch_rss_titles(url: str, limit: int = 8) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        root = ET.fromstring(response.text)
        titles = []
        for item in root.findall(".//item"):
            title = item.findtext("title")
            if title:
                titles.append(re.sub(r"\s+", " ", title).strip())
            if len(titles) >= limit:
                break
        return titles
    except Exception:
        return []


async def fetch_market_headlines() -> list[str]:
    headlines = await fetch_rss_titles("https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC,%5EIXIC,%5EDJI&region=US&lang=en-US")
    return headlines or [
        "Market breadth, rates, megacap technology, and earnings revisions remain the key watch items.",
        "Investors are balancing growth expectations against valuation and rate sensitivity.",
    ]


async def fetch_ai_trends() -> list[str]:
    arxiv = await fetch_rss_titles("https://export.arxiv.org/rss/cs.AI", limit=6)
    hf = await fetch_rss_titles("https://huggingface.co/papers/rss", limit=6)
    trends = arxiv + [title for title in hf if title not in arxiv]
    return trends[:10] or [
        "Agentic workflows are moving from demos to governed production systems.",
        "Evaluation, observability, and tool permissions are becoming central AI architecture topics.",
        "Small language models, local inference, and routing are rising in enterprise AI discussions.",
        f"Content radar fallback generated on {datetime.now(timezone.utc).date().isoformat()} because live trend feeds were unavailable.",
    ]
