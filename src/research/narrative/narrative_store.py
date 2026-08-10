"""NarrativeStore — persistence and retrieval of narrative history.

Narratives evolve over time. The store provides:
    - Save/load narratives to disk (JSON)
    - Version history for each narrative
    - Compare current vs previous narratives
    - Track narrative lifecycle (active/archived)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.research.narrative.schemas import Narrative
from src.shared.logging import get_logger

logger = get_logger(__name__)


class NarrativeStore:
    """Persistent store for narrative history.

    Data is stored as JSON files in the given directory:
        narrative_store/{date}/narratives.json
        narrative_store/latest.json  ← symlink or copy to latest

    Usage:
        store = NarrativeStore()
        store.save(narratives)  # Save today's narratives
        prev = store.load_latest()  # Load yesterday's
        changed = store.detect_changes(prev, current)  # What changed?
    """

    def __init__(self, store_dir: str = "narrative_store") -> None:
        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        narratives: list[Narrative],
        date_str: Optional[str] = None,
    ) -> str:
        """Save narratives to disk.

        Args:
            narratives: List of narratives to save.
            date_str: Date string (YYYY-MM-DD), defaults to today.

        Returns:
            Path to saved file.
        """
        date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        date_dir = self._store_dir / date_str
        date_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "date": date_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "narrative_count": len(narratives),
            "narratives": [n.to_dict() for n in narratives],
        }

        filepath = date_dir / "narratives.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        # Also save as latest
        latest_path = self._store_dir / "latest.json"
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        logger.info("narrative_store_saved | %s | %d narratives", date_str, len(narratives))
        return str(filepath)

    def load_latest(self) -> Optional[list[Narrative]]:
        """Load the most recent narratives."""
        latest_path = self._store_dir / "latest.json"
        if not latest_path.exists():
            logger.warning("narrative_store_no_latest")
            return None

        with open(latest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return self._deserialize(data.get("narratives", []))

    def load_date(self, date_str: str) -> Optional[list[Narrative]]:
        """Load narratives for a specific date."""
        filepath = self._store_dir / date_str / "narratives.json"
        if not filepath.exists():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return self._deserialize(data.get("narratives", []))

    def detect_changes(
        self,
        previous: Optional[list[Narrative]],
        current: list[Narrative],
    ) -> dict:
        """Detect what changed between two narrative sets.

        Returns:
            Dict with new, removed, upgraded, downgraded narratives.
        """
        if not previous:
            return {
                "new": [n.title for n in current],
                "removed": [],
                "upgraded": [],
                "downgraded": [],
                "unchanged": [],
            }

        prev_map = {n.title: n for n in previous}
        curr_map = {n.title: n for n in current}

        prev_titles = set(prev_map.keys())
        curr_titles = set(curr_map.keys())

        new_titles = curr_titles - prev_titles
        removed_titles = prev_titles - curr_titles
        common_titles = prev_titles & curr_titles

        upgraded = []
        downgraded = []
        unchanged = []

        for title in common_titles:
            prev_conf = prev_map[title].confidence
            curr_conf = curr_map[title].confidence
            delta = curr_conf - prev_conf

            if delta > 0.15:
                upgraded.append({"title": title, "delta": round(delta, 3)})
            elif delta < -0.15:
                downgraded.append({"title": title, "delta": round(delta, 3)})
            else:
                unchanged.append(title)

        result = {
            "new": sorted(new_titles),
            "removed": sorted(removed_titles),
            "upgraded": sorted(upgraded, key=lambda x: x["delta"], reverse=True),
            "downgraded": sorted(downgraded, key=lambda x: x["delta"]),
            "unchanged": sorted(unchanged),
        }

        logger.info(
            "narrative_changes | new=%d removed=%d upgraded=%d downgraded=%d",
            len(result["new"]),
            len(result["removed"]),
            len(result["upgraded"]),
            len(result["downgraded"]),
        )
        return result

    def get_history(self, narrative_title: str, limit: int = 30) -> list[dict]:
        """Get the version history of a specific narrative across dates."""
        history = []
        date_dirs = sorted(
            [d for d in self._store_dir.iterdir() if d.is_dir()],
            key=lambda d: d.name,
            reverse=True,
        )[:limit]

        for date_dir in date_dirs:
            filepath = date_dir / "narratives.json"
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for n_data in data.get("narratives", []):
                    if n_data.get("title") == narrative_title:
                        history.append({
                            "date": date_dir.name,
                            "confidence": n_data["confidence"],
                            "composite_score": n_data["composite_score"],
                            "strength": n_data["strength"],
                            "is_active": n_data.get("is_active", True),
                        })
                        break

        return history

    def list_dates(self) -> list[str]:
        """List all dates with stored narratives."""
        return sorted(
            [d.name for d in self._store_dir.iterdir() if d.is_dir()],
            reverse=True,
        )

    # ── Internal ─────────────────────────────────────────────────────────────

    @staticmethod
    def _deserialize(data: list[dict]) -> list[Narrative]:
        """Reconstruct Narrative objects from JSON dicts."""
        narratives = []
        for n_data in data:
            n = Narrative(
                id=n_data.get("id", ""),
                title=n_data.get("title", ""),
                description=n_data.get("description", ""),
                confidence=n_data.get("confidence", 0.0),
                strength=n_data.get("strength", 0.0),
                novelty_score=n_data.get("novelty_score", 0.0),
                market_consensus=n_data.get("market_consensus", 0.5),
                composite_score=n_data.get("composite_score", 0.0),
                breadth=n_data.get("breadth", 0.0),
                supporting_models=n_data.get("supporting_models", []),
                contradicting_models=n_data.get("contradicting_models", []),
                affected_assets=n_data.get("affected_assets", []),
                source_list=n_data.get("source_list", []),
                is_active=n_data.get("is_active", True),
                version=n_data.get("version", 1),
            )
            narratives.append(n)
        return narratives
