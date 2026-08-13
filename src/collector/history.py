"""Market change tracker - 1-day changes via Sina, weekly via local snapshots.

Strategy:
- 1-day:   Sina real-time prev_close comparison (always works)
- Weekly:  Compare against saved snapshot from 5+ days ago
- On each run, save today's data to data/snapshots/ for future comparisons
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Config ──
SNAPSHOT_DIR = Path(__file__).resolve().parents[3] / "data" / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Sina codes for real-time price + prev_close
SINA_CODE_MAP: dict[str, str] = {
    "SPY": "gb_spy",
    "QQQ": "gb_qqq",
    "IWM": "gb_iwm",
    "GLD": "gb_gld",
    "USO": "gb_uso",
    "VIXY": "gb_vixy",
    "HYG": "gb_hyg",
    "LQD": "gb_lqd",
    "NVDA": "gb_nvda",
    "SMH": "gb_smh",
    "ASML": "gb_asml",
    "TSM": "gb_tsm",
    "TLT": "gb_tlt",
}

# Display name mappings
DISPLAY_NAMES: dict[str, str] = {
    "SPY": "标普500",
    "QQQ": "纳斯达克100",
    "IWM": "罗素2000",
    "GLD": "黄金",
    "USO": "WTI原油",
    "VIXY": "VIX恐慌",
    "HYG": "高收益债",
    "LQD": "投资级债",
    "TLT": "长期国债",
    "NVDA": "英伟达",
    "SMH": "半导体",
    "ASML": "阿斯麦",
    "TSM": "台积电",
}


def _fetch_one_sina(ticker: str, code: str) -> tuple[float, float] | None:
    """Fetch current price and prev_close from Sina. Returns (current, prev) or None."""
    try:
        r = requests.get(
            f"https://hq.sinajs.cn/list={code}",
            headers={"Referer": "https://finance.sina.com.cn"},
            timeout=10,
        )
        inner = r.text.split('"')[1]
        parts = inner.split(",")
        if len(parts) >= 8:
            current = float(parts[1])
            prev = float(parts[7])
            if current > 0 and prev > 0:
                return (current, prev)
    except Exception as e:
        logger.warning("sina_fetch_failed | %s: %s", ticker, str(e)[:80])
    return None


def fetch_all_sina_prices() -> dict[str, tuple[float, float]]:
    """Fetch current + prev_close for all tracked tickers via Sina."""
    results: dict[str, tuple[float, float]] = {}
    for i, (ticker, code) in enumerate(SINA_CODE_MAP.items()):
        if i > 0:
            time.sleep(0.25)
        pair = _fetch_one_sina(ticker, code)
        if pair:
            results[ticker] = pair
    logger.info("sina_prices | fetched %d/%d tickers", len(results), len(SINA_CODE_MAP))
    return results


def load_historical_snapshot(lookback_days: int = 5) -> dict | None:
    """Load the most recent snapshot from at least `lookback_days` ago."""
    if not SNAPSHOT_DIR.exists():
        return None

    cutoff = datetime.now().date() - timedelta(days=lookback_days)
    snapshots = sorted(SNAPSHOT_DIR.glob("*.json"))

    # Find a snapshot from cutoff date or earlier (closest to cutoff)
    best = None
    for sp in reversed(snapshots):
        try:
            dt = datetime.strptime(sp.stem[:10], "%Y-%m-%d").date()
            if dt <= cutoff:
                if best is None or dt > best[0]:
                    best = (dt, sp)
        except ValueError:
            continue

    if best:
        with open(best[1], encoding="utf-8") as f:
            data = json.load(f)
        logger.info(
            "historical_snapshot | loaded %s (%d days ago)",
            best[0],
            (datetime.now().date() - best[0]).days,
        )
        return data
    return None


def save_snapshot(prices: dict[str, tuple[float, float]], date_str: str):
    """Save today's prices to a JSON snapshot file."""
    filepath = SNAPSHOT_DIR / f"{date_str}.json"
    payload = {
        "date": date_str,
        "prices": {t: {"current": p[0], "prev_close": p[1]} for t, p in prices.items()},
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("snapshot_saved | %s (%d tickers)", filepath, len(prices))


def compute_changes(today_str: str | None = None) -> dict[str, dict]:
    """Compute 1-day and weekly changes for all tracked indicators.

    Returns:
        {ticker: {current, chg_1d, chg_1d_pct, chg_5d, chg_5d_pct, source, name}}
    """
    today_str = today_str or datetime.now().strftime("%Y-%m-%d")

    # 1) Fetch today's prices from Sina
    sina_prices = fetch_all_sina_prices()

    # 2) Save snapshot for future comparisons
    if sina_prices:
        save_snapshot(sina_prices, today_str)

    # 3) Load historical snapshot for weekly comparison
    hist = load_historical_snapshot(lookback_days=5)

    # 4) Build result
    result: dict[str, dict] = {}
    for ticker, (current, prev) in sina_prices.items():
        chg = current - prev
        chg_pct = (chg / prev) * 100 if prev > 0 else 0

        entry: dict = {
            "current": round(current, 2),
            "chg_1d": round(chg, 2),
            "chg_1d_pct": round(chg_pct, 2),
            "chg_5d": None,
            "chg_5d_pct": None,
            "chg_5d_days": None,
            "source": "sina",
            "name": DISPLAY_NAMES.get(ticker, ticker),
        }

        # Weekly comparison from saved snapshot
        if hist and ticker in hist.get("prices", {}):
            hist_current = hist["prices"][ticker]["current"]
            delta_5d = current - hist_current
            delta_5d_pct = (delta_5d / hist_current) * 100 if hist_current > 0 else 0
            days_ago = (
                datetime.now().date() - datetime.strptime(hist["date"], "%Y-%m-%d").date()
            ).days
            entry["chg_5d"] = round(delta_5d, 2)
            entry["chg_5d_pct"] = round(delta_5d_pct, 2)
            entry["chg_5d_days"] = days_ago

        result[ticker] = entry

    return result


def format_changes_table(changes: dict[str, dict]) -> str:
    """Format changes as a human-readable table for the daily memo."""
    lines = []
    header = (
        f"{'指标':<10} {'现价':>10} {'日涨跌':>10} {'日涨跌%':>8} {'周涨跌':>10} {'周涨跌%':>8}"
    )
    sep = "-" * 70
    lines.append(sep)
    lines.append(header)
    lines.append(sep)

    for sym in [
        "SPY",
        "QQQ",
        "IWM",
        "GLD",
        "USO",
        "VIXY",
        "HYG",
        "LQD",
        "TLT",
        "NVDA",
        "SMH",
        "ASML",
        "TSM",
    ]:
        info = changes.get(sym)
        if not info:
            continue
        name = DISPLAY_NAMES.get(sym, sym)
        week_val = f"{info['chg_5d']:+.2f}" if info.get("chg_5d") is not None else "      --"
        week_pct = (
            f"{info['chg_5d_pct']:+.2f}%" if info.get("chg_5d_pct") is not None else "     --"
        )

        # Color markers for significant changes
        flag_1d = (
            " ▼" if info["chg_1d_pct"] < -0.5 else (" ▲" if info["chg_1d_pct"] > 0.5 else "  ")
        )
        flag_5d = (
            " ▼"
            if (info.get("chg_5d_pct") or 0) < -1
            else (" ▲" if (info.get("chg_5d_pct") or 0) > 1 else "  ")
        )

        lines.append(
            f"{name:<10} {info['current']:>10.2f} {info['chg_1d']:>+10.2f} {info['chg_1d_pct']:>+7.2f}%{flag_1d}"
            f" {week_val:>10} {week_pct:>8}{flag_5d}"
        )

    lines.append(sep)
    return "\n".join(lines)


# ── CLI test ──
if __name__ == "__main__":
    changes = compute_changes()
    print(format_changes_table(changes))
