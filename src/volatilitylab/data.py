"""Yahoo adjusted-close acquisition; raw licensed inputs stay outside Git."""
import hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import exchange_calendars as xc

def fetch(symbol, start, end, directory):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    a = int(pd.Timestamp(start, tz="UTC").timestamp())
    b = int((pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)).timestamp())
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?period1={a}&period2={b}&interval=1d"
    path = directory / f"{symbol}.json"
    if not path.exists():
        subprocess.run(["curl", "--fail", "--retry", "2", "-L", "-A", "Mozilla/5.0", url, "-o", str(path)], check=True)
        (directory / f"{symbol}.retrieved.txt").write_text(datetime.now(timezone.utc).isoformat())
    raw = path.read_bytes()
    obj = json.loads(raw)["chart"]["result"][0]
    dates = pd.to_datetime(obj["timestamp"], unit="s", utc=True).tz_convert("America/New_York").tz_localize(None).normalize()
    prices = pd.Series(obj["indicators"]["adjclose"][0]["adjclose"], index=dates, name=symbol)
    prices = prices.loc[start:end]
    if prices.index.duplicated().any() or not prices.index.is_monotonic_increasing:
        raise ValueError("Duplicate or unsorted dates")
    cal = xc.get_calendar("XNYS", start=pd.Timestamp(start)-pd.Timedelta(days=10), end=pd.Timestamp(end)+pd.Timedelta(days=10))
    sessions = cal.sessions_in_range(start, end).tz_localize(None)
    prices = prices.reindex(sessions)
    missing = prices.index[prices.isna()].strftime("%Y-%m-%d").tolist()
    if (prices.dropna() <= 0).any(): raise ValueError("Non-positive price")
    receipt = directory / f"{symbol}.retrieved.txt"
    meta = dict(symbol=symbol, url=url, retrieved_utc=receipt.read_text().strip() if receipt.exists() else "unknown cached retrieval", sha256=hashlib.sha256(raw).hexdigest(), adjustment="Yahoo adjclose: splits and distributions", first=str(prices.index[0].date()), last=str(prices.index[-1].date()), observed=int(prices.notna().sum()), missing_sessions=missing)
    return prices, meta
