"""V3.5 Production Agent Schemas — daily run report & agent state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class DailyRunReport:
    """Complete report from a single daily agent run.

    This is the single deliverable that captures everything the agent
    produced on a given day — from data to narrative to memo.
    """
    run_id: str = ""
    date: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Phase outputs
    regime_classification: Optional[Any] = None  # MacroRegime
    regime_transition: Optional[Any] = None      # RegimeTransitionModel
    historical_analogs: list[Any] = field(default_factory=list)

    capital_flow_report: Optional[Any] = None    # CapitalFlowReport
    reflexivity_report: Optional[Any] = None
    narrative_report: Optional[Any] = None
    expert_debate_report: Optional[Any] = None

    research_memo: Optional[Any] = None          # ResearchMemo
    learning_report: Optional[Any] = None         # LearningReport
    curiosity_report: Optional[Any] = None        # CuriosityReport

    # Dashboard summary
    summary_headline: str = ""
    key_risks: list[str] = field(default_factory=list)
    key_opportunities: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    conviction: float = 0.5
    action_items: list[str] = field(default_factory=list)

    # Pipeline execution stats
    pipeline_duration_seconds: float = 0.0
    modules_executed: list[str] = field(default_factory=list)
    modules_failed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "date": self.date,
            "timestamp": self.timestamp,
            "summary_headline": self.summary_headline,
            "key_risks": self.key_risks,
            "key_opportunities": self.key_opportunities,
            "sentiment": self.sentiment,
            "conviction": self.conviction,
            "action_items": self.action_items,
            "pipeline_duration_seconds": self.pipeline_duration_seconds,
            "modules_executed": self.modules_executed,
            "modules_failed": self.modules_failed,
            "errors": self.errors,
        }

    def summary(self) -> str:
        """Human-readable daily summary."""
        lines = [
            f"=== Daily Research Report: {self.date} ===",
            f"Headline: {self.summary_headline}",
            f"Sentiment: {self.sentiment} | Conviction: {self.conviction:.1%}",
            "",
        ]
        if self.key_risks:
            lines.append("Key Risks:")
            lines.extend(f"  - {r}" for r in self.key_risks)
        if self.key_opportunities:
            lines.append("Key Opportunities:")
            lines.extend(f"  - {o}" for o in self.key_opportunities)
        if self.action_items:
            lines.append("Actions:")
            lines.extend(f"  - {a}" for a in self.action_items)
        lines.append(f"\nModules: {len(self.modules_executed)} ok, {len(self.modules_failed)} failed")
        lines.append(f"Duration: {self.pipeline_duration_seconds:.1f}s")
        return "\n".join(lines)
