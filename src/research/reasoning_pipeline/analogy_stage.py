"""V5.2 Stage 4: Historical Analogy — What does history tell us?

Professional macro researchers ALWAYS compare to history.
This is not optional — it's what separates research from journalism.

This stage finds the best historical analogies, extracts lessons,
and critically — identifies what's different this time.
"""

from __future__ import annotations

from datetime import datetime

from src.research.reasoning_pipeline.schemas import (
    AnalogyOutput,
    EvidenceOutput,
    ObservationOutput,
    PatternOutput,
    StageStatus,
)


class AnalogyStage:
    """Stage 4: Historical analogy search and comparison."""

    # Curated historical episodes with key characteristics
    HISTORICAL_EPISODES: dict[str, dict] = {
        "1994-1995": {
            "description": "Fed tightening cycle, bond market selloff, EM crisis (Mexico)",
            "regime": "hawkish tightening",
            "triggers": ["rate hikes", "bond selloff", "yield spike", "EM stress"],
            "outcome": "soft landing achieved, but EM crisis in Mexico",
        },
        "1997-1998": {
            "description": "Asian Financial Crisis, LTCM, Fed cuts",
            "regime": "EM contagion / risk-off",
            "triggers": ["currency crisis", "EM crash", "contagion", "fed cut"],
            "outcome": "Fed cut rates, US economy remained resilient, tech bubble continued",
        },
        "2000-2002": {
            "description": "Dot-com bust, recession, aggressive Fed easing",
            "regime": "equity bear / recession",
            "triggers": ["tech crash", "recession", "deflation fear", "aggressive easing"],
            "outcome": "Prolonged equity bear market, mild recession",
        },
        "2004-2006": {
            "description": "Measured pace tightening, housing bubble builds",
            "regime": "gradual tightening / bubble formation",
            "triggers": ["gradual hikes", "housing boom", "easy credit"],
            "outcome": "Housing bubble that eventually caused GFC",
        },
        "2007-2009": {
            "description": "Global Financial Crisis, zero rates, QE",
            "regime": "systemic crisis",
            "triggers": ["credit crisis", "bank failure", "systemic risk", "QE", "ZIRP"],
            "outcome": "Deepest recession since Great Depression",
        },
        "2010-2012": {
            "description": "European sovereign debt crisis",
            "regime": "sovereign risk / fragmentation",
            "triggers": ["sovereign spread", "euro crisis", "draghi", "whatever it takes"],
            "outcome": "Draghi's backstop stabilized markets",
        },
        "2013": {
            "description": "Taper Tantrum",
            "regime": "rate shock",
            "triggers": ["taper", "yield spike", "EM selloff", "bond rout"],
            "outcome": "Temporary selloff, recovery by year-end",
        },
        "2015-2016": {
            "description": "China devaluation, oil crash, manufacturing recession",
            "regime": "global slowdown / disinflation",
            "triggers": [
                "china devaluation",
                "oil crash",
                "manufacturing recession",
                "dollar strength",
            ],
            "outcome": "Fed paused, markets recovered",
        },
        "2018 Q4": {
            "description": "Powell pivot after December rate hike and market crash",
            "regime": "policy error / quick pivot",
            "triggers": ["rate hike", "market crash", "powell pivot", "vix spike"],
            "outcome": "Fed pivoted, markets rallied in 2019",
        },
        "2020": {
            "description": "COVID shock, unprecedented fiscal + monetary stimulus",
            "regime": "exogenous shock / massive stimulus",
            "triggers": ["pandemic", "stimulus", "QE infinity", "fiscal expansion"],
            "outcome": "Fastest recession and recovery in history, followed by inflation",
        },
        "2021-2022": {
            "description": "Post-COVID inflation surge, most aggressive hiking since 1980s",
            "regime": "inflation overshoot / aggressive tightening",
            "triggers": ["inflation surge", "supply chain", "aggressive hikes", "rate shock"],
            "outcome": "Sharpest rate hiking cycle in 40 years",
        },
        "2022-2023": {
            "description": "Regional bank crisis (SVB), BOE gilt intervention",
            "regime": "financial stability risk / rapid tightening side effects",
            "triggers": ["bank failure", "deposit flight", "gilt crisis", "financial stability"],
            "outcome": "Emergency interventions contained contagion",
        },
    }

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def execute(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
        historical_data: dict | None = None,
    ) -> AnalogyOutput:
        """Execute historical analogy search.

        Args:
            observation: Stage 1 output
            evidence: Stage 2 output
            pattern: Stage 3 output
            historical_data: Additional historical context

        Returns:
            AnalogyOutput with ranked analogies and lessons
        """
        output = AnalogyOutput(
            timestamp=datetime.now().isoformat(),
            status=StageStatus.IN_PROGRESS,
        )

        # 1. Find matching historical episodes
        output.analogies = self._find_analogies(
            pattern.patterns,
            evidence.evidence_clusters,
            observation,
        )

        # 2. Extract lessons
        output.lessons = self._extract_lessons(output.analogies)

        # 3. Identify differences
        output.differences = self._identify_differences(output.analogies, observation)

        # 4. Select best analogy
        if output.analogies:
            output.best_analogy = output.analogies[0]["period"]

        # 5. Calibrate confidence
        output.analogy_confidence = self._calibrate(output.analogies)

        # 6. Generate trace
        output.reasoning_trace = self._generate_trace(output)
        output.status = StageStatus.COMPLETED

        return output

    def _find_analogies(
        self,
        patterns: list[str],
        clusters: dict[str, list[str]],
        observation: ObservationOutput,
    ) -> list[dict[str, str]]:
        """Score and rank historical episodes for relevance."""
        scored = []

        # Build query text from current observations
        query = " ".join(patterns) + " "
        query += " ".join(observation.market_moves) + " "
        query += " ".join(observation.data_surprises)
        query_lower = query.lower()

        for period, episode in self.HISTORICAL_EPISODES.items():
            triggers = episode["triggers"]
            # Score by trigger overlap
            matches = sum(1 for t in triggers if t.lower() in query_lower)
            if matches > 0:
                similarity = "high" if matches >= 3 else ("medium" if matches >= 2 else "low")
                scored.append(
                    {
                        "period": period,
                        "description": episode["description"],
                        "similarity": similarity,
                        "regime": episode["regime"],
                        "outcome": episode["outcome"],
                        "match_score": matches,
                    }
                )

        # Sort by match score
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return scored[:3]

    def _extract_lessons(self, analogies: list[dict]) -> list[str]:
        """Extract key lessons from analogies."""
        lessons = []
        for analogy in analogies:
            period = analogy["period"]
            outcome = analogy["outcome"]

            if "soft landing" in outcome:
                lessons.append(
                    f"{period}: Tightening does not always cause recession — soft landings possible"
                )
            if "crisis" in outcome.lower() or "crash" in outcome.lower():
                lessons.append(
                    f"{period}: Tightening cycles can expose hidden financial vulnerabilities"
                )
            if "inflation" in outcome.lower():
                lessons.append(f"{period}: Inflation can persist longer than consensus expects")
            if "recovery" in outcome.lower():
                lessons.append(
                    f"{period}: Markets often recover faster than macro fundamentals suggest"
                )
            if "pivot" in outcome.lower():
                lessons.append(
                    f"{period}: Central banks can and will pivot when financial stability is at risk"
                )
            if "QE" in outcome.upper():
                lessons.append(
                    f"{period}: Unconventional policy can stabilize markets even in extreme scenarios"
                )
            if "contagion" in outcome.lower():
                lessons.append(
                    f"{period}: Local crises can become global through contagion channels"
                )

        return lessons[:6]

    def _identify_differences(
        self,
        analogies: list[dict],
        observation: ObservationOutput,
    ) -> list[str]:
        """Identify how today differs from historical analogies."""
        differences = []

        for analogy in analogies:
            period = analogy["period"]
            # Generic structural differences
            if int(period[:4]) < 2000:
                differences.append(
                    f"vs {period}: Different monetary framework (pre- vs post-GFC), "
                    "different inflation dynamics"
                )
            if int(period[:4]) < 2010:
                differences.append(
                    f"vs {period}: Central bank communication far more transparent now, "
                    "markets price policy more efficiently"
                )
            differences.append(
                f"vs {period}: Current structural backdrop differs — "
                "fiscal dominance, deglobalization, energy transition are unique"
            )

        return differences[:5]

    def _calibrate(self, analogies: list[dict]) -> float:
        """Calibrate analogy confidence."""
        if not analogies:
            return 0.0
        best = analogies[0]
        if best["similarity"] == "high":
            return 0.75
        elif best["similarity"] == "medium":
            return 0.5
        return 0.3

    def _generate_trace(self, output: AnalogyOutput) -> str:
        """Generate reasoning trace."""
        trace = []
        trace.append("=== Stage 4: Historical Analogy ===")
        trace.append(f"Best analogy: {output.best_analogy}")
        trace.append(f"Total analogies found: {len(output.analogies)}")
        trace.append(f"Key lessons: {len(output.lessons)}")
        trace.append(f"Key differences: {len(output.differences)}")
        trace.append(f"Confidence: {output.analogy_confidence:.2f}")
        return "\n".join(trace)
