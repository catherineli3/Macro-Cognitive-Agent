"""Sina Finance real-time data collector for US markets.

Replaces Yahoo Finance (yfinance) which is rate-limited in the user's network.
Uses Sina Finance's free HTTP API - no API key required, works from China.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Optional, Dict

import requests

from src.domain.macro_indicator import MacroIndicator
from src.schemas.macro_data import MacroDataSchema
from src.shared.logging import get_logger

logger = get_logger(__name__)


# Sina code mapping: indicator_symbol -> sina_code
SINA_CODE_MAP = {
    "SPY":    "gb_spy",      # S&P 500 ETF (proxy for SPX)
    "QQQ":    "gb_qqq",      # Nasdaq-100 ETF
    "IWM":    "gb_iwm",      # Russell 2000 ETF
    "GLD":    "gb_gld",      # Gold ETF
    "USO":    "gb_uso",      # WTI Oil ETF
    "HYG":    "gb_hyg",      # High Yield Bond ETF
    "LQD":    "gb_lqd",      # Investment Grade Bond ETF
    "TLT":    "gb_tlt",      # 20+ Year Treasury ETF (proxy for US10Y)
    "SHY":    "gb_shy",      # 1-3 Year Treasury ETF (proxy for US2Y)
    "VIXY":   "gb_vixy",     # VIX Short-Term Futures ETF (proxy for VIX)
    "NVDA":   "gb_nvda",     # NVIDIA
    "SMH":    "gb_smh",      # Semiconductor ETF
    "ASML":   "gb_asml",     # ASML
    "TSM":    "gb_tsm",      # TSMC
    "COPX":   "gb_copx",     # Copper Miners ETF (proxy for copper)
    "BND":    "gb_bnd",      # Total Bond Market ETF
}


def fetch_sina_quote(sina_code: str) -> Optional[Dict]:
    """Fetch a single quote from Sina Finance. Returns parsed dict or None."""
    try:
        r = requests.get(
            f"https://hq.sinajs.cn/list={sina_code}",
            headers={"Referer": "https://finance.sina.com.cn"},
            timeout=10,
        )
        text = r.text.strip()
        if not text or '=""' in text:
            return None

        # Parse Sina format: var hq_str_CODE="name,price,change%,time,..."
        inner = text.split('"')[1]
        parts = inner.split(",")

        if len(parts) < 4 or float(parts[1]) == 0:
            return None

        return {
            "name": parts[0],
            "price": float(parts[1]),
            "change_pct": float(parts[2]) if parts[2] else 0.0,
            "time": parts[3],
            "volume": float(parts[7]) if len(parts) > 7 and parts[7] else 0,
        }
    except Exception as exc:
        logger.warning("sina_fetch_failed | code=%s error=%s", sina_code, exc)
        return None


def fetch_all_sina(log_delay: float = 0.3) -> dict[str, dict]:
    """Fetch all mapped indicators from Sina with stagger delay."""
    results: dict[str, dict] = {}
    for i, (indicator, code) in enumerate(SINA_CODE_MAP.items()):
        if i > 0:
            time.sleep(log_delay)
        quote = fetch_sina_quote(code)
        if quote:
            results[indicator] = quote
            logger.info(
                "sina_quote | %s(%s) price=%.2f change=%.2f%%",
                indicator, code, quote["price"], quote["change_pct"],
            )
        else:
            logger.warning("sina_quote_miss | %s(%s) NOT FOUND", indicator, code)
    return results


# ── Test CLI ──
if __name__ == "__main__":
    quotes = fetch_all_sina()
    print(f"\nFetched {len(quotes)}/{len(SINA_CODE_MAP)} indicators from Sina Finance")
    for sym, q in quotes.items():
        chg = f"{q['change_pct']:+.2f}%" if q['change_pct'] != 0 else "FLAT"
        print(f"  {sym:6s}: {q['price']:>10.2f}  ({chg})  {q['name'][:30]}")
