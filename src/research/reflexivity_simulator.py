"""V8.3 Reflexivity Simulation — Soros-style feedback loop analysis.

The agent must answer:
    - If everyone believes this, then what?
    - If everyone buys, then what?
    - If positioning becomes crowded, then what?

True Soros reflexivity: market prices affect fundamentals, which affect
market prices, creating self-reinforcing or self-defeating cycles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class ReflexivityPhase(str, Enum):
    """Stages of a reflexive process."""
    LATENT = "latent"                # Feedback loop not yet active
    EMERGING = "emerging"            # Early signs of reflexivity
    SELF_REINFORCING = "reinforcing"  # Trend affecting fundamentals
    SELF_VALIDATING = "validating"    # Prices appear to confirm thesis
    UNSUSTAINABLE = "unsustainable"   # Far from equilibrium
    INFLECTION = "inflection"         # Turning point approaching
    SELF_DEFEATING = "defeating"      # Trend reversing on itself


class CrowdingRisk(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class ReflexivityAnalysis:
    """Complete reflexivity analysis for a thesis/position."""
    analysis_id: str = field(default_factory=lambda: uuid4().hex[:8])
    thesis: str = ""
    date: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d'))
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Phase assessment
    phase: ReflexivityPhase = ReflexivityPhase.LATENT
    phase_confidence: float = 0.5
    time_to_inflection: str = ""          # e.g., "3-6 months"
    
    # The question chain
    if_everyone_believes: str = ""        # What if this is consensus?
    if_everyone_positions: str = ""       # What if everyone is long?
    if_crowding: str = ""                 # What if positioning is extreme?
    
    # Feedback loop analysis
    self_reinforcing_mechanism: str = ""  # How do prices affect fundamentals?
    fundamental_impact: str = ""          # What fundamentals are being changed?
    divergence_from_equilibrium: float = 0.0  # 0 = equilibrium, 1 = far
    
    # Crowding assessment
    crowding_level: CrowdingRisk = CrowdingRisk.MODERATE
    positioning_data: str = ""            # Evidence of positioning
    crowded_by: list[str] = field(default_factory=list)  # Who is crowded?
    
    # Vulnerability
    vulnerability_score: float = 0.0      # 0–100: how vulnerable to reversal?
    catalyst_for_reversal: list[str] = field(default_factory=list)
    estimated_drawdown_if_reversal: str = ""
    
    # Historical precedent
    historical_analogy: str = ""
    analogy_outcome: str = ""
    
    def render(self) -> str:
        return f"""# Reflexivity Analysis

**Thesis**: {self.thesis}
**Date**: {self.date}
**Phase**: {self.phase.value} (confidence: {self.phase_confidence:.0%})

---

## The Consensus Questions

### If Everyone Believes This…
{self.if_everyone_believes or 'Analysis pending.'}

### If Everyone Positions for This…
{self.if_everyone_positions or 'Analysis pending.'}

### If Positioning Becomes Crowded…
{self.if_crowding or 'Analysis pending.'}

---

## Feedback Loop Analysis

### Self-Reinforcing Mechanism
{self.self_reinforcing_mechanism or 'No mechanism identified.'}

### Fundamental Impact
{self.fundamental_impact or 'No impact identified.'}

### Divergence from Equilibrium
**Score**: {self.divergence_from_equilibrium:.0%} 
({'Far from equilibrium — reversal risk elevated' if self.divergence_from_equilibrium > 0.7 else 'Approaching equilibrium'})

---

## Crowding Assessment

**Crowding Level**: {self.crowding_level.value.upper()}
**Positioning Evidence**: {self.positioning_data or 'No data.'}

### Vulnerability
**Score**: {self.vulnerability_score:.0f}/100
{'⚠️ HIGH VULNERABILITY — reversal could be violent' if self.vulnerability_score > 70 else ''}

### Potential Catalysts for Reversal
{chr(10).join(f'- {c}' for c in self.catalyst_for_reversal) if self.catalyst_for_reversal else '- None identified.'}

### Estimated Drawdown if Reversal
{self.estimated_drawdown_if_reversal or 'Not estimated.'}

---

## Historical Analogy
**Period**: {self.historical_analogy or 'None identified.'}
**Outcome**: {self.analogy_outcome or 'N/A'}

---
*Reflexivity Analysis by Macro Research Agent V8.3*
"""


class ReflexivitySimulator:
    """Simulate Soros-style reflexivity for any macro thesis.

    Core idea: In financial markets, participants' views affect the
    fundamentals they are trying to predict. This creates feedback loops
    that can drive markets far from equilibrium before eventually reversing.
    """

    def __init__(self):
        self.analyses: dict[str, ReflexivityAnalysis] = {}

    def analyze(self, thesis: str,
                market_data: Optional[dict] = None,
                positioning_data: Optional[dict] = None,
                narratives: Optional[list[str]] = None,
                beliefs: Optional[list[dict]] = None) -> ReflexivityAnalysis:
        """Run reflexivity analysis on a thesis."""
        
        analysis = ReflexivityAnalysis(thesis=thesis)
        
        # Consensus questions
        analysis.if_everyone_believes = self._if_everyone_believes(thesis, narratives)
        analysis.if_everyone_positions = self._if_everyone_positions(thesis, positioning_data)
        analysis.if_crowding = self._if_crowding(thesis, positioning_data)
        
        # Feedback loop
        analysis.self_reinforcing_mechanism = self._find_feedback_mechanism(thesis)
        analysis.fundamental_impact = self._assess_fundamental_impact(thesis)
        analysis.divergence_from_equilibrium = self._estimate_divergence(thesis, market_data)
        
        # Phase determination
        analysis.phase = self._determine_phase(thesis, analysis.divergence_from_equilibrium)
        
        # Crowding
        analysis.crowding_level = self._assess_crowding(positioning_data)
        analysis.crowded_by = self._identify_crowded_players(positioning_data)
        analysis.positioning_data = self._summarize_positioning(positioning_data)
        
        # Vulnerability
        analysis.vulnerability_score = self._calculate_vulnerability(analysis)
        analysis.catalyst_for_reversal = self._identify_catalysts(thesis)
        analysis.estimated_drawdown_if_reversal = self._estimate_drawdown(analysis)
        
        # Historical
        analogy = self._find_historical_analogy(thesis)
        analysis.historical_analogy = analogy.get("period", "")
        analysis.analogy_outcome = analogy.get("outcome", "")
        
        self.analyses[analysis.analysis_id] = analysis
        return analysis

    # ── Consensus Questions ───────────────────────────────────────────────

    def _if_everyone_believes(self, thesis: str,
                              narratives: Optional[list[str]]) -> str:
        """What happens if this becomes the dominant narrative?"""
        if not narratives:
            return (
                "If this becomes the dominant market narrative, it would be "
                "fully priced into assets. The opportunity would shift from "
                "the direction of the thesis to the timing of when it breaks. "
                "Late entrants would bear disproportionate risk."
            )
        
        narrative_str = ", ".join(narratives[:2]) if len(narratives) > 1 else narratives[0]
        return (
            f"If everyone believes '{thesis[:60]}', the narrative would be fully "
            f"absorbed into market prices. The marginal buyer would be the last "
            f"to position. Current related narrative: '{narrative_str}'. "
            f"The key risk becomes: what catalyst proves the consensus wrong?"
        )

    def _if_everyone_positions(self, thesis: str,
                               positioning: Optional[dict]) -> str:
        if not positioning:
            return (
                "If everyone is long this thesis, the asymmetric payoff shifts "
                "to the downside. Every incremental buyer has less conviction "
                "than the last. The unwind, when it comes, will be disorderly "
                "because everyone is on the same side."

            )
        return (
            f"If everyone positions for this, the market becomes one-sided. "
            f"Positioning data suggests {positioning}. "
            f"When everyone who wants to buy has bought, only sellers remain."
        )

    def _if_crowding(self, thesis: str,
                     positioning: Optional[dict]) -> str:
        return (
            "Crowded positioning creates the risk of a violent unwind. "
            "When positioning is extreme, even small disappointments can "
            "trigger cascading stop-losses and forced liquidation. "
            "The more crowded the trade, the larger the potential overshoot "
            "in the opposite direction."
        )

    # ── Feedback Loop Analysis ────────────────────────────────────────────

    def _find_feedback_mechanism(self, thesis: str) -> str:
        """Identify self-reinforcing mechanisms in the thesis."""
        thesis_lower = thesis.lower()
        
        mechanics = []
        
        if any(w in thesis_lower for w in ["dollar", "usd", "currency"]):
            mechanics.append(
                "Dollar strength/weakness affects EM funding costs → EM growth → "
                "commodity demand → commodity currencies → back to dollar."
            )
        if any(w in thesis_lower for w in ["equity", "stock", "sp", "market"]):
            mechanics.append(
                "Rising equities → wealth effect → consumption → earnings → "
                "equities rise further. Self-reinforcing until mean reversion."
            )
        if any(w in thesis_lower for w in ["inflation", "cpi", "price"]):
            mechanics.append(
                "Inflation expectations → wage demands → actual inflation → "
                "higher inflation expectations. Wage-price spiral risk."
            )
        if any(w in thesis_lower for w in ["credit", "bond", "yield", "spread"]):
            mechanics.append(
                "Tightening credit → lower investment → weaker growth → "
                "wider spreads → further tightening. Credit cycle feedback."
            )
        if any(w in thesis_lower for w in ["tech", "ai", "capex"]):
            mechanics.append(
                "AI investment → productivity gains → earnings → more AI investment. "
                "Reflexive until diminishing returns or overcapacity."
            )
        
        if not mechanics:
            mechanics.append(
                "Prices affecting sentiment → sentiment affecting flows → "
                "flows affecting prices. Classic market reflexivity."
            )
        
        return " ".join(mechanics)

    def _assess_fundamental_impact(self, thesis: str) -> str:
        thesis_lower = thesis.lower()
        
        if any(w in thesis_lower for w in ["rate", "fed", "monetary", "cut"]):
            return (
                "Rate expectations affect: mortgage rates → housing demand → "
                "construction employment → consumer spending → GDP growth. "
                "The rate path itself influences the economy it's trying to manage."
            )
        elif any(w in thesis_lower for w in ["equity", "stock"]):
            return (
                "Equity prices affect: wealth effect → consumer confidence → "
                "retail spending → corporate earnings → equity valuations. "
                "Higher prices create the conditions for higher prices."
            )
        return (
            "Market prices affect economic behavior through wealth effects, "
            "funding costs, and sentiment channels. The distinction between "
            "fundamental and self-fulfilling becomes blurred."
        )

    def _estimate_divergence(self, thesis: str,
                             market_data: Optional[dict]) -> float:
        if not market_data:
            return 0.5  # Default moderate divergence
        # Simplified: check for extreme valuations/positioning
        divergence = 0.3
        if market_data.get("valuation_extreme", False):
            divergence += 0.3
        if market_data.get("positioning_extreme", False):
            divergence += 0.2
        return min(divergence, 1.0)

    def _determine_phase(self, thesis: str,
                         divergence: float) -> ReflexivityPhase:
        if divergence < 0.2:
            return ReflexivityPhase.LATENT
        elif divergence < 0.4:
            return ReflexivityPhase.EMERGING
        elif divergence < 0.6:
            return ReflexivityPhase.SELF_REINFORCING
        elif divergence < 0.8:
            return ReflexivityPhase.SELF_VALIDATING
        else:
            return ReflexivityPhase.UNSUSTAINABLE

    # ── Crowding Assessment ───────────────────────────────────────────────

    def _assess_crowding(self, positioning: Optional[dict]) -> CrowdingRisk:
        if not positioning:
            return CrowdingRisk.MODERATE
        
        extreme = positioning.get("extreme_positioning", False)
        one_sided = positioning.get("one_sided", False)
        
        if extreme:
            return CrowdingRisk.EXTREME
        elif one_sided:
            return CrowdingRisk.HIGH
        return CrowdingRisk.MODERATE

    def _identify_crowded_players(self, positioning: Optional[dict]) -> list[str]:
        if not positioning:
            return ["Institutional investors", "Hedge funds", "Retail flow"]
        return positioning.get("crowded_by", ["Multiple investor types"])

    def _summarize_positioning(self, positioning: Optional[dict]) -> str:
        if not positioning:
            return "Positioning data unavailable."
        return str(positioning.get("summary", "Positioning data available."))

    def _calculate_vulnerability(self, analysis: ReflexivityAnalysis) -> float:
        score = 0.0
        
        # Divergence contribution
        score += analysis.divergence_from_equilibrium * 40
        
        # Crowding contribution
        crowding_score = {
            CrowdingRisk.NONE: 0, CrowdingRisk.LOW: 15,
            CrowdingRisk.MODERATE: 30, CrowdingRisk.HIGH: 45,
            CrowdingRisk.EXTREME: 60,
        }
        score += crowding_score.get(analysis.crowding_level, 30)
        
        return min(score, 100.0)

    def _identify_catalysts(self, thesis: str) -> list[str]:
        return [
            "Significant data miss that challenges the thesis",
            "Policy surprise that shifts the macro landscape",
            "Positioning-driven liquidation event",
            "Correlation breakdown forcing deleveraging",
            "Exogenous shock (geopolitical, financial accident)",
        ]

    def _estimate_drawdown(self, analysis: ReflexivityAnalysis) -> str:
        if analysis.vulnerability_score > 70:
            return "15-25%+ — violent mean reversion possible"
        elif analysis.vulnerability_score > 50:
            return "10-15% correction likely on catalyst"
        elif analysis.vulnerability_score > 30:
            return "5-10% pullback on disappointment"
        return "Moderate (3-7%) on position adjustment"

    def _find_historical_analogy(self, thesis: str) -> dict:
        thesis_lower = thesis.lower()
        
        if any(w in thesis_lower for w in ["tech", "ai", "bubble"]):
            return {"period": "Dot-com bubble (1999-2000)", 
                    "outcome": "80%+ drawdown in NASDAQ, but genuine innovation survived."}
        if any(w in thesis_lower for w in ["inflation", "stagflation"]):
            return {"period": "1970s stagflation",
                    "outcome": "Decade of poor risk-adjusted returns until Volcker shock."}
        if any(w in thesis_lower for w in ["dollar", "usd"]):
            return {"period": "USD cycles (1980-85 Plaza Accord, 2014-16 DXY peak)",
                    "outcome": "Extended trends followed by coordinated reversals."}
        if any(w in thesis_lower for w in ["credit", "debt", "leverage"]):
            return {"period": "2008 GFC / 2000 dot-com credit cycle",
                    "outcome": "Leverage unwinds are always more violent than buildups."}
        
        return {"period": "Typical reflexivity cycle", 
                "outcome": "Trend extends far beyond fundamentals, then reverts sharply."}

    def get_analysis(self, analysis_id: str) -> Optional[ReflexivityAnalysis]:
        return self.analyses.get(analysis_id)

    def get_all_analyses(self) -> list[ReflexivityAnalysis]:
        return list(self.analyses.values())

    def get_stats(self) -> dict:
        if not self.analyses:
            return {"total_analyses": 0}
        
        phases = {}
        for a in self.analyses.values():
            p = a.phase.value
            phases[p] = phases.get(p, 0) + 1
        
        return {
            "total_analyses": len(self.analyses),
            "phase_distribution": phases,
            "avg_vulnerability": sum(a.vulnerability_score for a in self.analyses.values()) / len(self.analyses),
            "extreme_crowding": sum(1 for a in self.analyses.values() if a.crowding_level == CrowdingRisk.EXTREME),
        }
