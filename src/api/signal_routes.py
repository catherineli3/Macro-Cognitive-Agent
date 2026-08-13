"""Signal API routes — Sprint 2 Signal Engine endpoints.

GET /signals/snapshot — Returns the current macro signal picture
                        (latest signal per indicator).

All endpoints follow RESTful conventions. Business logic lives
in the Signal module; the API layer handles HTTP concerns only.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from src.schemas.signal import SignalSnapshot
from src.shared.logging import get_logger
from src.storage.signal_repository import SqlSignalRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/snapshot", response_model=SignalSnapshot)
async def get_signal_snapshot() -> SignalSnapshot:
    """Return the current macro signal snapshot.

    For each indicator that has at least one signal, returns
    the most recent signal. This gives a point-in-time picture
    of the macro signal environment.

    Returns:
        SignalSnapshot with signals list + metadata.

    Raises:
        HTTPException 500: If the signal repository is unreachable.
    """
    try:
        repo = SqlSignalRepository()
        signals = await repo.get_snapshot()

        # Build a human-readable summary
        if not signals:
            summary = "No signals generated yet. Run the Signal Pipeline first."
        else:
            bullish = sum(1 for s in signals if s.direction.value == "bullish")
            bearish = sum(1 for s in signals if s.direction.value == "bearish")
            neutral = sum(1 for s in signals if s.direction.value == "neutral")

            dims = sorted(set(s.dimension for s in signals))
            parts = [f"{len(signals)} active signals across {', '.join(dims)}"]
            if bullish:
                parts.append(f"{bullish} bullish")
            if bearish:
                parts.append(f"{bearish} bearish")
            if neutral:
                parts.append(f"{neutral} neutral")
            summary = " | ".join(parts)

        snapshot = SignalSnapshot(
            generated_at=datetime.now(UTC),
            signals=signals,
            summary=summary,
        )

        logger.info(
            "snapshot_returned count=%d dimensions=%s",
            snapshot.count,
            snapshot.dimensions_covered,
        )
        return snapshot

    except Exception as exc:
        logger.error("snapshot_error error=%s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve signal snapshot: {exc}",
        ) from exc
