from __future__ import annotations

"""SignalHandler — Executor adapter for Signal Engine.

Capability: "macro.signal"
Reads:      context.artifacts["processed_data"]  (MacroDataSchema[])
Produces:   context.artifacts["signals"]         (SignalSnapshot)
"""

from datetime import datetime, timezone

from src.domain.execution import TaskResultStatus
from src.interfaces.task_handler import TaskHandlerInterface
from src.schemas.execution import TaskResult
from src.schemas.macro_data import MacroDataSchema
from src.schemas.planning import Task
from src.schemas.signal import MacroSignalSchema, SignalSnapshot
from src.shared.logging import get_logger
from src.signal.generator import ThresholdSignalGenerator

logger = get_logger(__name__)


class SignalHandler(TaskHandlerInterface):
    """Executes signal generation via the Signal Engine.

    Capability: "macro.signal"
    Consumes:   context.artifacts["processed_data"]
    Produces:   context.artifacts["signals"] (SignalSnapshot)

    This handler bridges the Executor to the Signal Engine (Sprint 2).
    It generates structured macro signals from processed/normalized data.
    """

    def __init__(self, generator: ThresholdSignalGenerator | None = None) -> None:
        """Initialize with an optional pre-configured signal generator.

        If no generator is provided, a default one is created.
        This enables dependency injection for testing.
        """
        self._generator = generator or ThresholdSignalGenerator()

    def supported_capability(self) -> str:
        return "macro.signal"

    def handler_name(self) -> str:
        return "SignalHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        """Execute signal generation.

        Args:
            task: The task to execute.
            context: ExecutionContext containing upstream artifacts.

        Returns:
            TaskResult with SignalSnapshot in artifacts["signals"].
            Returns SUCCESS with empty snapshot if no data is available.
        """
        started = datetime.now(timezone.utc)

        try:
            # Extract indicator data: try processed_data records, then raw_data records
            data_items = self._extract_data_items(context)

            if not data_items:
                logger.warning("signal_handler_no_data — producing empty snapshot")
                snapshot = SignalSnapshot(summary="No data available for signal generation.")
                return self._success(task, started, snapshot)

            # Generate signals for each data item
            signals: list[MacroSignalSchema] = []
            for item in data_items:
                try:
                    signal = await self._generate_signal(item)
                    signals.append(signal)
                except Exception as exc:
                    logger.warning(
                        "signal_handler_skip_indicator indicator=%s error=%s",
                        item.indicator if hasattr(item, 'indicator') else 'unknown',
                        str(exc),
                    )

            snapshot = SignalSnapshot(
                signals=signals,
                summary=self._build_summary(signals),
            )

            logger.info(
                "signal_handler_completed",
                extra={"signal_count": len(signals), "dimensions": snapshot.dimensions_covered},
            )

            return self._success(task, started, snapshot)

        except Exception as exc:
            completed = datetime.now(timezone.utc)
            logger.error(
                "signal_handler_failed task=%s error=%s",
                task.name,
                str(exc),
            )
            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                status=TaskResultStatus.FAILED,
                error=str(exc),
                artifacts={},
                started_at=started,
                completed_at=completed,
            )

    # ── Private ─────────────────────────────────────────────────────────

    async def _generate_signal(self, data: "MacroDataSchema") -> "MacroSignalSchema":
        """Generate a signal for a single data point.

        Handles both MacroDataSchema (with indicator metadata) and simple dict-like data.
        For data without full indicator metadata, infers dimension from indicator name.
        """
        from src.domain.macro_indicator import Frequency, MacroIndicator, HypothesisDimension

        symbol = getattr(data, 'symbol', 'UNKNOWN')
        if symbol == 'UNKNOWN' and hasattr(data, 'indicator'):
            symbol = str(data.indicator)

        # ── Dimension inference ──────────────────────────────────────
        dimension_str = getattr(data, 'dimension', None) or getattr(data, 'hypothesis_dimension', None)
        if dimension_str is None:
            dimension_str = _infer_dimension(symbol)

        if not dimension_str:
            dimension_str = "Liquidity"

        try:
            dim_enum = HypothesisDimension(dimension_str)
        except (ValueError, TypeError):
            dim_enum = HypothesisDimension.LIQUIDITY

        # ── Category and frequency inference ─────────────────────────
        category = _infer_category(symbol)
        frequency = _infer_frequency(symbol)

        # ── Build MacroIndicator ─────────────────────────────────────
        indicator = MacroIndicator(
            symbol=symbol,
            name=symbol,
            category=category,
            frequency=frequency,
            hypothesis_dimension=dim_enum,
        )

        # ── Ensure MacroDataSchema ───────────────────────────────────
        if not isinstance(data, MacroDataSchema):
            data_dict = data if isinstance(data, dict) else {}
            ts = data_dict.get('timestamp', datetime.now(timezone.utc))
            if isinstance(ts, str):
                from datetime import datetime as _dt
                ts = _dt.fromisoformat(ts)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            data_schema = MacroDataSchema(
                symbol=data_dict.get('symbol') or data_dict.get('indicator', indicator.symbol),
                value=float(data_dict.get('value', 0)),
                timestamp=ts,
                source=data_dict.get('source', 'mock'),
            )
        else:
            data_schema = data

        return await self._generator.generate(
            indicator=indicator,
            current=data_schema,
            history=[],
        )

    @staticmethod
    def _extract_data_items(context) -> list["MacroDataSchema"]:
        """Extract indicator data items from context artifacts.

        Tries multiple artifact formats:
        1. processed_data as list[MacroDataSchema] or list[dict]
        2. processed_data as dict with "records" key (simple handler format)
        3. raw_data records (fallback from SimpleRetrieveHandler)
        """
        processed = context.get_artifact("processed_data", None)
        raw = context.get_artifact("raw_data", None)

        records: list[dict] = []

        # Case 1: processed_data is a dict with nested records (simple handler)
        if isinstance(processed, dict):
            nested = processed.get("records", [])
            if nested:
                records = nested
        # Case 2: processed_data is a list
        elif isinstance(processed, list):
            return SignalHandler._parse_data(processed)

        # Fallback: raw_data records from SimpleRetrieveHandler
        if not records and isinstance(raw, dict):
            records = raw.get("records", [])

        # Convert dict records to MacroDataSchema
        parsed: list[MacroDataSchema] = []
        for rec in records:
            if isinstance(rec, dict) and "indicator" in rec and "value" in rec:
                try:
                    # Parse timestamp from string if needed
                    ts = rec.get("timestamp", datetime.now(timezone.utc))
                    if isinstance(ts, str):
                        from datetime import datetime as _dt
                        ts = _dt.fromisoformat(ts)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)

                    parsed.append(MacroDataSchema(
                        symbol=str(rec["indicator"]),
                        value=float(rec["value"]),
                        timestamp=ts,
                        source=str(rec.get("source", "mock")),
                    ))
                except (ValueError, TypeError) as e:
                    logger.warning(
                        "signal_handler_parse_error record=%s error=%s",
                        str(rec)[:80], str(e),
                    )

        return parsed

    @staticmethod
    def _parse_data(raw: list) -> list["MacroDataSchema"]:
        """Parse raw processed_data into MacroDataSchema objects.

        Handles MacroDataSchema, dict, tuple (from simple handlers), and object types.
        """
        parsed: list[MacroDataSchema] = []
        for item in raw:
            if isinstance(item, MacroDataSchema):
                parsed.append(item)
            elif isinstance(item, dict):
                try:
                    parsed.append(MacroDataSchema(**item))
                except Exception:
                    logger.warning(
                        "signal_handler_skip_invalid_item",
                        extra={"item_keys": list(item.keys()) if isinstance(item, dict) else []},
                    )
            elif isinstance(item, (tuple, list)):
                # Handle tuple from simple handlers: (symbol, value) or (symbol, value, extra...)
                try:
                    symbol = str(item[0]) if len(item) > 0 else "UNKNOWN"
                    value = float(item[1]) if len(item) > 1 else 0.0
                    parsed.append(MacroDataSchema(
                        symbol=symbol,
                        value=value,
                        timestamp=datetime.now(timezone.utc),
                        source="mock",
                    ))
                except (ValueError, TypeError, IndexError):
                    logger.warning("signal_handler_skip_invalid_tuple item=%s", str(item)[:50])
            elif hasattr(item, 'indicator') and hasattr(item, 'value'):
                # Has required attributes — pass through
                parsed.append(item)
        return parsed

    @staticmethod
    def _build_summary(signals: list[MacroSignalSchema]) -> str:
        """Build a one-line summary of the signal picture."""
        if not signals:
            return "No signals generated."
        bearish = sum(1 for s in signals if s.direction.value == "bearish")
        bullish = sum(1 for s in signals if s.direction.value == "bullish")
        neutral = sum(1 for s in signals if s.direction.value == "neutral")
        return (
            f"{len(signals)} signals: {bullish} bullish, {bearish} bearish, "
            f"{neutral} neutral across {len(set(s.dimension for s in signals))} dimensions."
        )

    @staticmethod
    def _success(
        task: Task,
        started: datetime,
        snapshot: SignalSnapshot,
    ) -> TaskResult:
        """Build a successful TaskResult with signal snapshot."""
        completed = datetime.now(timezone.utc)
        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskResultStatus.SUCCESS,
            artifacts={"signals": snapshot},
            started_at=started,
            completed_at=completed,
        )


# ── Dimension Inference ──────────────────────────────────────────────────

# Common indicator → dimension mapping for inference
_INDICATOR_DIMENSION_MAP: dict[str, str] = {
    "DXY": "Liquidity",
    "US10Y": "Liquidity",
    "US2Y": "Liquidity",
    "FEDFUNDS": "Liquidity",
    "SOFR": "Liquidity",
    "HYG": "Credit",
    "IG": "Credit",
    "LQD": "Credit",
    "JNK": "Credit",
    "SPREAD": "Credit",
    "GDP": "Growth",
    "PMI": "Growth",
    "ISM": "Growth",
    "IP": "Growth",
    "INDPRO": "Growth",
    "CPI": "Inflation",
    "PCE": "Inflation",
    "PPI": "Inflation",
    "TIPS": "Inflation",
    "BREAKEVEN": "Inflation",
    "VIX": "Risk_Appetite",
    "VXN": "Risk_Appetite",
    "SKEW": "Risk_Appetite",
}

# Indicator → category and frequency inference
_INDICATOR_CATEGORY_MAP: dict[str, str] = {
    "DXY": "Currency",
    "VIX": "Volatility",
    "VXN": "Volatility",
    "US10Y": "Rates",
    "US2Y": "Rates",
    "FEDFUNDS": "Rates",
    "SOFR": "Rates",
    "HYG": "Credit",
    "IG": "Credit",
    "LQD": "Credit",
    "JNK": "Credit",
    "GDP": "Economic",
    "PMI": "Economic",
    "ISM": "Economic",
    "IP": "Economic",
    "INDPRO": "Economic",
    "CPI": "Inflation",
    "PCE": "Inflation",
    "PPI": "Inflation",
    "TIPS": "Inflation",
}

_INDICATOR_FREQUENCY_MAP: dict[str, str] = {
    "DXY": "Daily",
    "VIX": "Daily",
    "VXN": "Daily",
    "US10Y": "Daily",
    "US2Y": "Daily",
    "FEDFUNDS": "Daily",
    "SOFR": "Daily",
    "HYG": "Daily",
    "IG": "Daily",
    "LQD": "Daily",
    "JNK": "Daily",
    "GDP": "Quarterly",
    "PMI": "Monthly",
    "ISM": "Monthly",
    "IP": "Monthly",
    "INDPRO": "Monthly",
    "CPI": "Monthly",
    "PCE": "Monthly",
    "PPI": "Monthly",
    "TIPS": "Daily",
}


def _infer_dimension(indicator_name: str) -> str | None:
    """Infer hypothesis dimension from indicator symbol."""
    upper = indicator_name.upper().strip()
    for key, dim in _INDICATOR_DIMENSION_MAP.items():
        if key in upper:
            return dim
    return None


def _infer_category(indicator_name: str) -> str:
    """Infer asset class category from indicator symbol."""
    upper = indicator_name.upper().strip()
    for key, cat in _INDICATOR_CATEGORY_MAP.items():
        if key in upper:
            return cat
    return "Other"


def _infer_frequency(indicator_name: str) -> "Frequency":
    """Infer observation frequency from indicator symbol."""
    from src.domain.macro_indicator import Frequency
    upper = indicator_name.upper().strip()
    for key, freq_str in _INDICATOR_FREQUENCY_MAP.items():
        if key in upper:
            return Frequency(freq_str)
    return Frequency.DAILY
