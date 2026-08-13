"""V6.2 Event Understanding — Reason about events, not just collect them.

Key question: "Why does this matter?"
Not: "What happened?"

Every incoming event must be understood through:
    Event → Why important? → Which Narrative? → Which Belief? →
    Which Asset? → Confidence → Unknowns

This moves the agent from being a news aggregator to being a researcher
who understands the significance of each event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from src.live_intelligence.schemas import EventImportance, NormalizedEvent


class UnderstandingDepth(str, Enum):
    """How deeply was the event understood?"""

    SURFACE = "surface"  # Only extracted facts
    CONTEXTUAL = "contextual"  # Placed in context
    ANALYTICAL = "analytical"  # Reasoned about implications
    STRATEGIC = "strategic"  # Connected to portfolio/thesis


@dataclass
class EventUnderstanding:
    """A fully-understood event with reasoning about its significance."""

    understanding_id: str = field(default_factory=lambda: uuid4().hex[:12])
    event_id: str = ""
    event_title: str = ""

    # Core question: Why does this matter?
    importance_rationale: str = ""  # 2-4 sentences on why this matters
    is_market_moving: bool = False
    is_belief_changing: bool = False

    # Narrative linkage
    narrative_id: str = ""
    narrative_name: str = ""
    narrative_impact: str = ""  # "strengthens", "weakens", "challenges", "confirms"
    narrative_confidence: float = 0.5

    # Belief linkage
    beliefs_affected: list[dict] = field(default_factory=list)
    # [{belief_id, belief_name, direction: support/contradict/neutral, strength: 0-1}]

    # Asset linkage
    assets_affected: list[dict] = field(default_factory=list)
    # [{asset_class, ticker, direction: bullish/bearish/neutral, magnitude: 0-1}]

    # Confidence in understanding
    understanding_confidence: float = 0.5
    depth: UnderstandingDepth = UnderstandingDepth.SURFACE

    # Unknowns — what we DON'T know
    unknowns: list[str] = field(default_factory=list)
    questions_raised: list[str] = field(default_factory=list)

    # What to watch next
    follow_up_events: list[str] = field(default_factory=list)
    data_to_watch: list[str] = field(default_factory=list)

    # Meta
    reasoned_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def summary(self) -> str:
        parts = [
            f"Event: {self.event_title}",
            f"Why matters: {self.importance_rationale[:120]}",
            f"Narrative: {self.narrative_name} ({self.narrative_impact})",
            f"Beliefs affected: {len(self.beliefs_affected)}",
            f"Assets affected: {len(self.assets_affected)}",
            f"Confidence: {self.understanding_confidence:.2f}",
        ]
        return " | ".join(parts)

    def to_dict(self) -> dict:
        return {
            "understanding_id": self.understanding_id,
            "event_id": self.event_id,
            "event_title": self.event_title,
            "importance_rationale": self.importance_rationale,
            "is_market_moving": self.is_market_moving,
            "is_belief_changing": self.is_belief_changing,
            "narrative_name": self.narrative_name,
            "narrative_impact": self.narrative_impact,
            "beliefs_affected": self.beliefs_affected,
            "assets_affected": self.assets_affected,
            "understanding_confidence": self.understanding_confidence,
            "depth": self.depth.value,
            "unknowns": self.unknowns,
            "questions_raised": self.questions_raised,
        }


class EventReasoner:
    """Understand events: why they matter, what they affect, what we don't know.

    This is the bridge between raw information intake and the research pipeline.
    Every event that passes freshness/dedup checks must be understood before
    it enters the evidence graph.
    """

    # ── Impact reasoning by category ──────────────────────────────────────

    CATEGORY_RATIONALE = {
        "monetary_policy": """
Monetary policy events directly affect the discount rate for all assets.
Key questions: Is the stance changing? Is forward guidance shifting?
Does this alter the rate path? What does this mean for the dollar?
""",
        "economic_data": """
Economic data reveals the state of the business cycle.
Key questions: Is growth accelerating or decelerating? Is inflation
sticky or transitory? Is the labor market tightening or loosening?
Does this data point confirm or challenge the current narrative?
""",
        "fiscal_policy": """
Fiscal policy affects aggregate demand, bond supply, and sectoral flows.
Key questions: Is fiscal impulse expanding or contracting? What does
this mean for bond yields? Which sectors benefit?
""",
        "geopolitical": """
Geopolitical events introduce uncertainty and potential supply shocks.
Key questions: What is the probability of escalation? Which supply chains
are affected? What is the safe-haven flow implication?
""",
        "market_event": """
Market events reflect positioning, sentiment, and flow dynamics.
Key questions: Is this a correction or regime change? What positioning
is being unwound? Where is the pain trade?
""",
        "speech_commentary": """
Speeches reveal policymakers' reaction functions and current thinking.
Key questions: Is the tone shifting? What data are they watching?
Is there a new framework emerging?
""",
    }

    def __init__(self):
        self._understandings: dict[str, EventUnderstanding] = {}
        self._total_reasoned = 0

    def understand(
        self,
        event: NormalizedEvent,
        narratives: dict | None = None,
        beliefs: dict | None = None,
        market_context: dict | None = None,
    ) -> EventUnderstanding:
        """Understand an event: why it matters, what it affects.

        Args:
            event: Normalized event to understand
            narratives: Active narratives {name: {direction, confidence, ...}}
            beliefs: Active beliefs {id: {name, confidence, ...}}
            market_context: Current market state {asset: {price, trend, ...}}
        """
        understanding = EventUnderstanding(
            event_id=event.event_id,
            event_title=event.title,
        )

        # Step 1: Why does this matter?
        understanding.importance_rationale = self._reason_importance(event)
        understanding.is_market_moving = event.importance in (
            EventImportance.CRITICAL,
            EventImportance.HIGH,
        )
        understanding.is_belief_changing = event.importance == EventImportance.CRITICAL

        # Step 2: Which narrative does this affect?
        narrative_info = self._link_to_narratives(event, narratives or {})
        understanding.narrative_name = narrative_info.get("name", "")
        understanding.narrative_impact = narrative_info.get("impact", "neutral")
        understanding.narrative_confidence = narrative_info.get("confidence", 0.5)

        # Step 3: Which beliefs does this affect?
        understanding.beliefs_affected = self._link_to_beliefs(event, beliefs or {})

        # Step 4: Which assets does this affect?
        understanding.assets_affected = self._link_to_assets(event)

        # Step 5: What don't we know?
        understanding.unknowns = self._identify_unknowns(event)
        understanding.questions_raised = self._generate_questions(event)

        # Step 6: What to watch next?
        understanding.follow_up_events = self._suggest_follow_up(event)
        understanding.data_to_watch = self._suggest_data_to_watch(event)

        # Step 7: Assess understanding confidence
        understanding.understanding_confidence = self._assess_confidence(event, understanding)
        understanding.depth = self._determine_depth(event, understanding)

        # Store
        self._understandings[understanding.understanding_id] = understanding
        self._total_reasoned += 1

        return understanding

    def understand_batch(
        self,
        events: list[NormalizedEvent],
        narratives: dict | None = None,
        beliefs: dict | None = None,
        market_context: dict | None = None,
    ) -> list[EventUnderstanding]:
        """Understand multiple events."""
        return [self.understand(e, narratives, beliefs, market_context) for e in events]

    # ── Internal Reasoning Steps ──────────────────────────────────────────

    def _reason_importance(self, event: NormalizedEvent) -> str:
        """Generate the 'why this matters' rationale."""
        reasons = []

        # Category-specific baseline
        if event.category in self.CATEGORY_RATIONALE:
            reasons.append(self.CATEGORY_RATIONALE[event.category].strip())

        # Importance level
        if event.importance == EventImportance.CRITICAL:
            reasons.append(
                "This is a CRITICAL event that could change the macro regime or alter the dominant narrative."
            )
        elif event.importance == EventImportance.HIGH:
            reasons.append(
                "HIGH importance — this provides significant new evidence for positioning decisions."
            )
        elif event.importance == EventImportance.MEDIUM:
            reasons.append(
                "MEDIUM importance — adds incremental information to the existing picture."
            )

        # Surprise element
        if event.surprise is not None and abs(event.surprise) > 0:
            direction = "above" if event.surprise > 0 else "below"
            reasons.append(
                f"Surprise: actual came in {direction} expectations by {abs(event.surprise):.2f}, suggesting market may need to reprice."
            )

        # Key numbers
        if event.key_numbers:
            nums_str = ", ".join(f"{k}: {v}" for k, v in list(event.key_numbers.items())[:3])
            reasons.append(f"Key numbers: {nums_str}")

        return (
            " ".join(reasons) if reasons else "Incremental information requiring further analysis."
        )

    def _link_to_narratives(self, event: NormalizedEvent, narratives: dict) -> dict:
        """Determine which narrative this event supports/challenges."""
        if not narratives:
            # Default narrative mapping by event category
            default_map = {
                "monetary_policy": "Central Bank Policy Path",
                "economic_data": "Growth-Inflation Dynamics",
                "fiscal_policy": "Fiscal Sustainability",
                "geopolitical": "Geopolitical Risk Premium",
                "market_event": "Risk Appetite Regime",
            }
            name = default_map.get(event.category, "Macro Regime")
            return {"name": name, "impact": "informs", "confidence": 0.5}

        # Keyword-based narrative matching
        text = (event.title + " " + event.summary).lower()
        best_name = ""
        best_confidence = 0.0

        for name, info in narratives.items():
            name_lower = name.lower()
            # Simple overlap scoring
            words = set(name_lower.split())
            text_words = set(text.split())
            overlap = len(words & text_words) / max(len(words), 1)
            if overlap > best_confidence:
                best_confidence = overlap
                best_name = name

        impact = "informs"
        if event.impact_direction in ("bullish", "bearish"):
            if event.impact_direction == "bullish":
                impact = "strengthens"
            else:
                impact = "challenges"

        return {
            "name": best_name or "Macro Regime",
            "impact": impact,
            "confidence": max(best_confidence, 0.3),
        }

    def _link_to_beliefs(self, event: NormalizedEvent, beliefs: dict) -> list[dict]:
        """Determine which beliefs this event affects."""
        results = []

        if not beliefs:
            # Default belief mapping
            if "monetary" in event.category or "fed" in (event.title + event.summary).lower():
                results.append(
                    {
                        "belief_id": "monetary_stance",
                        "belief_name": "Fed Policy Path",
                        "direction": (
                            "support"
                            if "dovish" in (event.title + event.summary).lower()
                            else "contradict"
                        ),
                        "strength": 0.6,
                    }
                )
            if (
                "inflation" in (event.title + event.summary).lower()
                or "cpi" in (event.title + event.summary).lower()
            ):
                results.append(
                    {
                        "belief_id": "inflation_trend",
                        "belief_name": "Inflation Trajectory",
                        "direction": "support",
                        "strength": 0.5,
                    }
                )
            return results

        text = (event.title + " " + event.summary).lower()
        for bid, info in beliefs.items():
            name = info.get("name", bid).lower() if isinstance(info, dict) else str(info).lower()
            if any(w in text for w in name.split()):
                results.append(
                    {
                        "belief_id": bid,
                        "belief_name": (
                            info.get("name", bid) if isinstance(info, dict) else str(info)
                        ),
                        "direction": (
                            "support" if event.impact_direction == "bullish" else "contradict"
                        ),
                        "strength": (
                            min(event.impact_magnitude * 0.8, 1.0)
                            if event.impact_magnitude
                            else 0.5
                        ),
                    }
                )

        return results

    def _link_to_assets(self, event: NormalizedEvent) -> list[dict]:
        """Determine which asset classes are affected."""
        results = []
        impact = event.impact_direction
        magnitude = event.impact_magnitude or 0.3

        # Category → Asset class mapping
        asset_map = {
            "monetary_policy": [
                ("fixed_income", "US 2Y/10Y Treasuries"),
                ("fx", "USD/DXY"),
                ("equity", "SPX/NDX"),
            ],
            "economic_data": [
                ("fixed_income", "Treasuries"),
                ("fx", "USD"),
                ("equity", "Equity Futures"),
            ],
            "geopolitical": [
                ("commodity", "Gold/Oil"),
                ("fx", "Safe Haven FX"),
                ("equity", "Defense/Energy Sectors"),
            ],
            "market_event": [
                ("equity", "Broad Market"),
                ("fixed_income", "Credit Spreads"),
            ],
            "fiscal_policy": [
                ("fixed_income", "Long-end Treasuries"),
                ("fx", "USD"),
                ("equity", "Infra/Defense Sectors"),
            ],
        }

        assets = asset_map.get(event.category, [("equity", "Broad Market")])
        for asset_class, specific in assets:
            results.append(
                {
                    "asset_class": asset_class,
                    "ticker": specific,
                    "direction": impact,
                    "magnitude": magnitude,
                }
            )

        return results

    def _identify_unknowns(self, event: NormalizedEvent) -> list[str]:
        """Identify what we don't know about this event."""
        unknowns = []

        if event.importance in (EventImportance.CRITICAL, EventImportance.HIGH):
            unknowns.append("How will markets fully price this information?")
            unknowns.append("Will this change the central bank's reaction function?")

        if event.category == "monetary_policy":
            unknowns.append("What is the terminal rate now?")
            unknowns.append("When does the cutting cycle begin?")
        elif event.category == "economic_data":
            unknowns.append("Is this a one-off or a trend change?")
            unknowns.append("What do leading indicators suggest for the next print?")
        elif event.category == "geopolitical":
            unknowns.append("What is the probability of escalation?")
            unknowns.append("Which supply chains are most vulnerable?")

        if event.surprise and abs(event.surprise) > 0:
            unknowns.append(
                f"Is the {abs(event.surprise):.2f} surprise due to measurement error or genuine shift?"
            )

        return unknowns[:5]

    def _generate_questions(self, event: NormalizedEvent) -> list[str]:
        """Generate research questions raised by this event."""
        questions = []

        category_questions = {
            "monetary_policy": [
                "Does this shift the probability distribution of rate outcomes?",
                "What does the dot plot / forward guidance now imply?",
            ],
            "economic_data": [
                "Does this confirm or challenge the soft-landing narrative?",
                "What is the market-implied probability now vs before?",
            ],
            "geopolitical": [
                "What is the worst-case scenario and its market impact?",
                "Which sectors have the most exposure?",
            ],
            "market_event": [
                "Is this positioning-driven or fundamentally-driven?",
                "What is the contagion risk to other assets?",
            ],
        }

        questions.extend(
            category_questions.get(
                event.category,
                [
                    "How does this update our base case?",
                    "What evidence would confirm or refute this signal?",
                ],
            )
        )

        return questions[:4]

    def _suggest_follow_up(self, event: NormalizedEvent) -> list[str]:
        """Suggest related events to watch for."""
        follow_ups = []

        if "inflation" in (event.title + event.summary).lower():
            follow_ups.extend(["Next CPI release", "PCE data", "FOMC minutes"])
        if "fed" in (event.title + event.summary).lower() or event.category == "monetary_policy":
            follow_ups.extend(["Fed speakers this week", "FOMC minutes", "Jobs data"])
        if (
            "nfp" in (event.title + event.summary).lower()
            or "payroll" in (event.title + event.summary).lower()
        ):
            follow_ups.extend(["CPI", "Retail sales", "ISM services"])
        if "gdp" in (event.title + event.summary).lower():
            follow_ups.extend(["PMI data", "Industrial production", "Consumer confidence"])

        return (
            follow_ups[:3] if follow_ups else ["Related data releases", "Central bank commentary"]
        )

    def _suggest_data_to_watch(self, event: NormalizedEvent) -> list[str]:
        """Suggest specific data points to monitor after this event."""
        watch_list = []

        category_watch = {
            "monetary_policy": ["Fed funds futures", "2Y yield", "5Y5Y inflation swap", "DXY"],
            "economic_data": [
                "Breakeven inflation",
                "Real yields",
                "Yield curve slope",
                "Credit spreads",
            ],
            "geopolitical": ["VIX", "Gold", "Oil", "CDS spreads"],
            "market_event": ["VIX", "Put/call ratio", "Volume", "Breadth indicators"],
            "fiscal_policy": ["10Y yield", "30Y yield", "CDS on sovereign", "Auction bid/cover"],
        }

        watch_list.extend(
            category_watch.get(event.category, ["VIX", "Treasury yields", "Credit spreads"])
        )
        return watch_list[:4]

    def _assess_confidence(
        self, event: NormalizedEvent, understanding: EventUnderstanding
    ) -> float:
        """How confident are we in this understanding?"""
        factors = []

        # Source reliability
        factors.append(event.confidence * 0.3)

        # Data quality (hard data > soft data > opinion)
        if event.category == "economic_data" and event.key_numbers:
            factors.append(0.9 * 0.3)
        elif event.category in ("monetary_policy", "market_event"):
            factors.append(0.7 * 0.3)
        else:
            factors.append(0.5 * 0.3)

        # Narrative linkage strength
        factors.append(understanding.narrative_confidence * 0.25)

        # Completeness
        completeness = 0.8 if understanding.unknowns else 0.4
        completeness -= 0.1 * min(len(understanding.unknowns), 5)
        factors.append(max(0.1, completeness) * 0.15)

        return sum(factors)

    def _determine_depth(
        self, event: NormalizedEvent, understanding: EventUnderstanding
    ) -> UnderstandingDepth:
        """Determine how deep our understanding is."""
        if (
            understanding.beliefs_affected
            and understanding.assets_affected
            and understanding.unknowns
            and understanding.understanding_confidence > 0.7
        ):
            return UnderstandingDepth.STRATEGIC
        elif understanding.beliefs_affected and understanding.assets_affected:
            return UnderstandingDepth.ANALYTICAL
        elif understanding.narrative_name:
            return UnderstandingDepth.CONTEXTUAL
        return UnderstandingDepth.SURFACE

    def get_understanding(self, understanding_id: str) -> EventUnderstanding | None:
        return self._understandings.get(understanding_id)

    def get_all_understandings(self) -> list[EventUnderstanding]:
        return list(self._understandings.values())

    def get_stats(self) -> dict:
        depths = {}
        for u in self._understandings.values():
            d = u.depth.value
            depths[d] = depths.get(d, 0) + 1
        return {
            "total_reasoned": self._total_reasoned,
            "stored_understandings": len(self._understandings),
            "depth_distribution": depths,
            "avg_confidence": (
                sum(u.understanding_confidence for u in self._understandings.values())
                / max(len(self._understandings), 1)
            ),
        }
