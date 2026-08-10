"""V5.2 Stage 9: Risk — Comprehensive risk monitoring and watchlist.

Every macro view, prediction, and trade needs explicit risk monitoring.

This stage produces:
    - Ranked risks by severity x probability
    - Tail risks
    - Correlation breakdown risks
    - 24-hour and 1-week watchlists
    - Key data release calendar
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.research.reasoning_pipeline.schemas import (
    ObservationOutput,
    EvidenceOutput,
    PatternOutput,
    HypothesisOutput,
    PredictionOutput,
    TradeOutput,
    CounterOutput,
    RiskOutput,
    StageStatus,
)


class RiskStage:
    """Stage 9: Risk identification, monitoring, and watchlist generation."""

    KNOWN_TAIL_RISKS = [
        "China property/credit event",
        "Taiwan Strait escalation",
        "Middle East energy supply disruption",
        "Cyber attack on financial infrastructure",
        "Sovereign debt crisis in major economy",
        "Pandemic / biosecurity event",
        "AI-driven market dislocation",
        "Climate-related financial shock",
        "Major bank / counterparty failure",
        "Nuclear / geopolitical escalation",
    ]

    STANDARD_DATA_RELEASES = {
        "US": ["Nonfarm Payrolls (1st Fri)", "CPI (mid-month)", "FOMC Decision",
               "GDP (advance)", "Retail Sales", "ISM Manufacturing", "PCE"],
        "EU": ["ECB Decision", "Flash CPI", "GDP", "PMI"],
        "CN": ["PBOC LPR", "GDP", "CPI/PPI", "PMI", "Trade Balance"],
        "JP": ["BOJ Decision", "CPI", "GDP", "Tankan"],
    }

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def execute(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
        hypothesis: HypothesisOutput,
        prediction: PredictionOutput,
        trade: TradeOutput,
        counter: CounterOutput,
    ) -> RiskOutput:
        """Execute risk assessment and monitoring setup.

        Args:
            observation: Stage 1
            evidence: Stage 2
            pattern: Stage 3
            hypothesis: Stage 5
            prediction: Stage 7
            trade: Stage 8
            counter: Stage 6

        Returns:
            RiskOutput with comprehensive risk monitoring
        """
        output = RiskOutput(
            timestamp=datetime.now().isoformat(),
            status=StageStatus.IN_PROGRESS,
        )

        # 1. Ranked risk list
        output.risks = self._rank_risks(
            observation, evidence, pattern, hypothesis, counter, trade
        )

        # 2. Tail risks
        output.tail_risks = self._assess_tail_risks(pattern)

        # 3. Correlation risks
        output.correlation_risks = self._assess_correlation_risks(
            evidence, pattern
        )

        # 4. Watchlists
        output.watchlist_24h = self._build_24h_watchlist(
            observation, evidence, pattern
        )
        output.watchlist_1w = self._build_1w_watchlist(
            observation, prediction, evidence
        )

        # 5. Key data releases
        output.key_data_releases = self._build_data_calendar(observation)

        # 6. Generate trace
        output.reasoning_trace = self._generate_trace(output)
        output.status = StageStatus.COMPLETED

        return output

    def _rank_risks(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
        hypothesis: HypothesisOutput,
        counter: CounterOutput,
        trade: TradeOutput,
    ) -> list[dict]:
        """Rank risks by severity x probability."""
        risks = []

        # 1. Counter-based risks
        for c in counter.counter_arguments:
            severity_score = {"fatal": 1.0, "major": 0.7, "minor": 0.3}.get(
                c.get("severity", "major"), 0.5
            )
            prob = c.get("probability", 0.3)
            risk_score = severity_score * prob

            risks.append({
                "risk": c["claim"][:120],
                "severity": c.get("severity", "major"),
                "probability": round(prob, 2),
                "risk_score": round(risk_score, 2),
                "impact": "Hypothesis invalidation" if risk_score > 0.3 else "Conviction adjustment",
                "hedge": self._suggest_hedge(c.get("severity", "major")),
                "monitor": "Incoming data consistency with central case",
            })

        # 2. Evidence-gap risks
        if evidence.evidence_gaps:
            risks.append({
                "risk": f"Evidence gaps in: {'; '.join(evidence.evidence_gaps[:3])}",
                "severity": "major",
                "probability": 0.4,
                "risk_score": 0.28,
                "impact": "Blind spots in analysis",
                "hedge": "Reduce position size until gaps filled",
                "monitor": f"Watch for data covering: {evidence.evidence_gaps[0]}",
            })

        # 3. Positioning risk
        risks.append({
            "risk": (
                "Crowded consensus positioning — even correct views may not generate "
                "alpha if market is already priced for the scenario"
            ),
            "severity": "minor",
            "probability": 0.45,
            "risk_score": 0.14,
            "impact": "Limited upside on correct calls",
            "hedge": "Consider options strategies for asymmetric payoff",
            "monitor": "Positioning surveys, CFTC COT, flow data",
        })

        # Sort by risk score descending
        risks.sort(key=lambda r: r["risk_score"], reverse=True)
        return risks

    def _assess_tail_risks(self, pattern: PatternOutput) -> list[str]:
        """Assess tail risks relevant to current environment."""
        patterns_text = " ".join(pattern.patterns).lower()

        # Filter tail risks that are most relevant
        relevant = []

        if "risk-off" in patterns_text or "credit" in patterns_text:
            relevant.extend([
                "Financial accident triggered by rapid tightening",
                "Major bank / counterparty failure",
            ])

        if "inflation" in patterns_text:
            relevant.extend([
                "Second wave of inflation forcing super-hawkish policy",
                "Stagflation scenario: 1970s redux",
            ])

        if "geopolitical" in patterns_text:
            relevant.extend([
                "China Taiwan Strait escalation",
                "Middle East energy supply disruption",
            ])

        # Always include these
        relevant.append("Black swan event: unknown unknown with systemic impact")
        relevant.append("AI-driven market dislocation (flash crash type event)")

        return relevant[:5]

    def _assess_correlation_risks(
        self,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
    ) -> list[str]:
        """Assess which correlations might break."""
        risks = []

        patterns_text = " ".join(pattern.patterns).lower()

        # Bond-equity correlation
        risks.append(
            "Bond-equity correlation: If inflation surprises to the upside, "
            "bonds and equities may sell off together (no hedge benefit)"
        )

        # Dollar-risk correlation
        if "dollar" in patterns_text.lower() or "usd" in patterns_text.lower():
            risks.append(
                "USD-EM correlation: Strong dollar may cause EM stress; "
                "correlation can turn non-linear"
            )

        # Commodity-inflation correlation
        if "commodity" in patterns_text.lower() or "inflation" in patterns_text:
            risks.append(
                "Commodity-equity correlation: Supply-driven commodity spikes "
                "may be negative for equities (cost-push vs demand-pull)"
            )

        return risks

    def _build_24h_watchlist(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
    ) -> list[str]:
        """Build immediate (next 24 hours) watchlist."""
        watchlist = []

        # Key levels to watch
        for move in observation.market_moves[:3]:
            watchlist.append(f"Monitor: {move}")

        # Gap risks
        if "VIX" in str(observation.market_moves):
            watchlist.append(
                "Overnight gap risk: Check Asia/Europe session for any dislocations"
            )

        # Key news risk
        watchlist.append(
            "Central bank speaker risk: Any unscheduled comments could move markets"
        )

        # Liquidity check
        watchlist.append("Liquidity monitoring: Check bid-ask spreads, depth of book")

        return watchlist

    def _build_1w_watchlist(
        self,
        observation: ObservationOutput,
        prediction: PredictionOutput,
        evidence: EvidenceOutput,
    ) -> list[str]:
        """Build 1-week watchlist."""
        watchlist = []

        # Prediction monitoring
        if prediction.predictions:
            watchlist.append(
                f"Monitor: Data vs. forecast '{prediction.predictions[0]['claim'][:50]}...'"
            )

        # Evidence tracking
        if evidence.evidence_gaps:
            watchlist.append(
                f"Fill gaps: Watch for new data on {evidence.evidence_gaps[0]}"
            )

        # Key events
        watchlist.append("Central bank communication: Scheduled speeches, minutes release")
        watchlist.append("Positioning check: Review after key data releases")

        # Dependency tracking
        if prediction.forecast_dependencies:
            watchlist.append(
                f"Track dependency: {prediction.forecast_dependencies[0]}"
            )

        return watchlist

    def _build_data_calendar(self, observation: ObservationOutput) -> list[str]:
        """Build key data release calendar."""
        calendar = []

        # Priority data based on what we're watching
        sources_text = " ".join(observation.sources).lower()

        if "us" in sources_text or any("us" in s.lower() for s in observation.observations):
            calendar.extend(self.STANDARD_DATA_RELEASES["US"])

        if any(kw in sources_text for kw in ["euro", "ecb", "eu"]):
            calendar.extend(self.STANDARD_DATA_RELEASES["EU"])

        if any(kw in sources_text for kw in ["china", "cn", "pboc"]):
            calendar.extend(self.STANDARD_DATA_RELEASES["CN"])

        return calendar[:8] if calendar else self.STANDARD_DATA_RELEASES["US"]

    def _suggest_hedge(self, severity: str) -> str:
        """Suggest hedging approach based on risk severity."""
        if severity == "fatal":
            return "Tail hedges: OTM puts, VIX calls, long vol strategies"
        elif severity == "major":
            return "Partial hedge: Reduce position size, buy protection on correlated assets"
        return "Monitoring only: No explicit hedge needed unless probability increases"

    def _generate_trace(self, output: RiskOutput) -> str:
        """Generate reasoning trace."""
        trace = []
        trace.append("=== Stage 9: Risk ===")
        trace.append(f"Ranked risks: {len(output.risks)}")
        if output.risks:
            trace.append(f"  Top risk: {output.risks[0]['risk'][:60]}... (score={output.risks[0]['risk_score']})")
        trace.append(f"Tail risks: {len(output.tail_risks)}")
        trace.append(f"Correlation risks: {len(output.correlation_risks)}")
        trace.append(f"24h watchlist: {len(output.watchlist_24h)} items")
        trace.append(f"1w watchlist: {len(output.watchlist_1w)} items")
        trace.append(f"Data calendar: {len(output.key_data_releases)} releases")
        return "\n".join(trace)
