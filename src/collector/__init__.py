"""Collector module — Fetch raw macro data from external sources.

Sprint 1:
    YahooCollector — Fetches data from Yahoo Finance via yfinance.

Responsibilities:
    1. Query external APIs / libraries
    2. Map raw response to MacroDataSchema
    3. Handle rate limiting and retries

Prohibited:
    - Database writes (use Repository)
    - Data analysis (use Analyzer)
    - LLM calls
    - Data validation (use validation module)
"""

from src.collector.yahoo import YahooCollector

__all__ = ["YahooCollector"]
