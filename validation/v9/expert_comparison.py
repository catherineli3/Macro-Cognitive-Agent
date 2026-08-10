# =============================================================================
# V9 Expert Comparison — Compare Agent Against Institutional Research
# =============================================================================
# Compares agent's macro analysis with:
#   - Expert views embedded in historical cases
#   - Institutional research benchmarks (Bridgewater, JPMorgan, Goldman, MS)
#   - Consensus macro frameworks
#
# Metrics:
#   - Regime Agreement: Did agent identify same regime as experts?
#   - Narrative Overlap: How similar is agent's narrative to expert view?
#   - Causal Alignment: Does agent follow similar causal reasoning?
#   - Directional Accuracy: Did agent get the same market direction call?
#   - Risk Concordance: Did agent identify same risks as experts?
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from validation.v9.historical_cases import HistoricalCase, CASES, build_all_cases
from validation.v9.scoring_engine import BlindTestResult


# ══════════════════════════════════════════════════════════════════════
# Expert Comparison Result
# ══════════════════════════════════════════════════════════════════════


@dataclass
class ExpertComparisonResult:
    """Result of comparing agent output to expert analysis on one case."""
    case_id: str
    case_date: str

    # Core metrics (0-1, higher = better match)
    regime_agreement: float = 0.0
    narrative_overlap: float = 0.0
    causal_alignment: float = 0.0
    directional_accuracy: float = 0.0
    risk_concordance: float = 0.0

    # Aggregate
    composite_score: float = 0.0  # 0-1
    similarity_percentage: float = 0.0  # 0-100%

    # Details
    agent_regime: str = ""
    expert_regime: str = ""
    agent_narrative: str = ""
    expert_narrative: str = ""
    key_divergences: list[str] = field(default_factory=list)
    key_alignments: list[str] = field(default_factory=list)

    def passed(self, threshold: float = 0.8) -> bool:
        """Check if similarity meets institutional threshold (80%)."""
        return self.similarity_percentage >= (threshold * 100)


@dataclass
class InstitutionalBenchmark:
    """Benchmark result against a specific institution's research framework."""
    institution: str
    total_cases: int = 0
    average_similarity: float = 0.0

    # Dimension breakdown
    regime_agreement_avg: float = 0.0
    narrative_overlap_avg: float = 0.0
    causal_alignment_avg: float = 0.0
    directional_accuracy_avg: float = 0.0
    risk_concordance_avg: float = 0.0

    results: list[ExpertComparisonResult] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.institution}: Similarity={self.average_similarity:.1%} "
            f"(Regime={self.regime_agreement_avg:.1%}, "
            f"Narrative={self.narrative_overlap_avg:.1%}, "
            f"Causal={self.causal_alignment_avg:.1%}, "
            f"Direction={self.directional_accuracy_avg:.1%}, "
            f"Risk={self.risk_concordance_avg:.1%})"
        )


# ══════════════════════════════════════════════════════════════════════
# Expert Comparator
# ══════════════════════════════════════════════════════════════════════


class ExpertComparator:
    """Compare agent output against expert analysis from historical cases.

    Each historical case contains the expert_view — what top macro
    researchers thought at that time. This engine compares agent output
    to that expert benchmark across 5 dimensions.
    """

    # Institutional research framework characteristics
    INSTITUTIONAL_FRAMEWORKS = {
        "bridgewater": {
            "focus": ["monetary policy", "credit creation", "debt cycle", "productivity"],
            "methodology": "How the Economic Machine Works — transactions-based",
            "key_indicators": ["debt/GDP", "credit impulse", "labor slack", "productivity trend"],
        },
        "jpmorgan": {
            "focus": ["liquidity", "positioning", "flow of funds", "earnings"],
            "methodology": "Flows & Liquidity — cross-asset positioning framework",
            "key_indicators": ["central bank balance sheet", "equity positioning", "credit spreads", "EPS growth"],
        },
        "goldman": {
            "focus": ["growth-inflation mix", "policy response", "valuation"],
            "methodology": "Top-down macro — growth/inflation quadrants",
            "key_indicators": ["ISM", "CPI", "Fed funds path", "earnings yield vs bond yield"],
        },
        "morgan_stanley": {
            "focus": ["cycle positioning", "leading indicators", "sector rotation"],
            "methodology": "Cycle Framework — 4 phases: recovery/expansion/contraction/recession",
            "key_indicators": ["LEI", "yield curve", "PMI", "earnings revisions"],
        },
    }

    def __init__(self):
        self._ensure_cases()

    def _ensure_cases(self):
        if not CASES:
            build_all_cases()

    def compare_single(
        self,
        case: HistoricalCase,
        agent_output: dict,
    ) -> ExpertComparisonResult:
        """Compare agent output against expert view for a single case.

        Args:
            case: The historical case with expert_view
            agent_output: Dict with keys: regime, narrative, beliefs,
                          prediction, risk, invalidation, asset_implication
        """
        result = ExpertComparisonResult(
            case_id=case.case_id,
            case_date=case.date,
        )

        # Store raw outputs
        result.agent_regime = agent_output.get("regime", "")
        result.expert_regime = case.expert_view
        result.agent_narrative = agent_output.get("narrative", "")
        result.expert_narrative = case.dominant_narrative

        # ── 1. Regime Agreement ──────────────────────────────────────
        result.regime_agreement = self._compare_regime(
            agent_output.get("regime", ""),
            case.macro_regime,
            case.expert_view,
        )

        # ── 2. Narrative Overlap ─────────────────────────────────────
        result.narrative_overlap = self._compare_narrative(
            agent_output.get("narrative", ""),
            case.dominant_narrative,
            case.market_beliefs,
        )

        # ── 3. Causal Alignment ──────────────────────────────────────
        result.causal_alignment = self._compare_causal(
            agent_output.get("beliefs", []),
            case.causal_chain,
        )

        # ── 4. Directional Accuracy ──────────────────────────────────
        result.directional_accuracy = self._compare_direction(
            agent_output.get("prediction", ""),
            agent_output.get("asset_implication", ""),
            case.asset_reaction,
        )

        # ── 5. Risk Concordance ──────────────────────────────────────
        result.risk_concordance = self._compare_risk(
            agent_output.get("risk", ""),
            agent_output.get("invalidation", ""),
            case.key_risks,
            case.unknowns,
        )

        # ── Aggregate ────────────────────────────────────────────────
        weights = [0.25, 0.25, 0.20, 0.15, 0.15]
        result.composite_score = sum([
            result.regime_agreement * weights[0],
            result.narrative_overlap * weights[1],
            result.causal_alignment * weights[2],
            result.directional_accuracy * weights[3],
            result.risk_concordance * weights[4],
        ])
        result.similarity_percentage = result.composite_score * 100

        # Identify divergences and alignments
        result.key_divergences = self._find_divergences(result, case)
        result.key_alignments = self._find_alignments(result)

        return result

    def compare_batch(
        self,
        cases: list[HistoricalCase],
        agent_outputs: list[dict],
    ) -> InstitutionalBenchmark:
        """Compare agent against expert across a batch of cases."""
        benchmark = InstitutionalBenchmark(institution="expert_consensus")
        results = []

        for case, ao in zip(cases, agent_outputs):
            try:
                r = self.compare_single(case, ao)
                results.append(r)
            except Exception:
                continue

        benchmark.results = results
        benchmark.total_cases = len(results)

        if results:
            benchmark.average_similarity = sum(r.similarity_percentage for r in results) / len(results) / 100
            benchmark.regime_agreement_avg = sum(r.regime_agreement for r in results) / len(results)
            benchmark.narrative_overlap_avg = sum(r.narrative_overlap for r in results) / len(results)
            benchmark.causal_alignment_avg = sum(r.causal_alignment for r in results) / len(results)
            benchmark.directional_accuracy_avg = sum(r.directional_accuracy for r in results) / len(results)
            benchmark.risk_concordance_avg = sum(r.risk_concordance for r in results) / len(results)

        return benchmark

    def benchmark_institutional_styles(
        self,
        cases: list[HistoricalCase],
        agent_outputs: list[dict],
    ) -> dict[str, InstitutionalBenchmark]:
        """Run comparison against multiple institutional frameworks."""
        results = {}
        for inst_name, framework in self.INSTITUTIONAL_FRAMEWORKS.items():
            # Score how well agent's approach matches each institution's methodology
            inst_benchmark = self._score_institutional_fit(
                cases, agent_outputs, inst_name, framework
            )
            results[inst_name] = inst_benchmark
        return results

    def _score_institutional_fit(
        self,
        cases: list[HistoricalCase],
        agent_outputs: list[dict],
        inst_name: str,
        framework: dict,
    ) -> InstitutionalBenchmark:
        """Score how closely agent's thinking patterns match an institution's framework."""
        benchmark = InstitutionalBenchmark(institution=inst_name)

        focus_keywords = framework["focus"]
        methodology = framework["methodology"]
        key_indicators = framework["key_indicators"]

        scores = []
        for case, ao in zip(cases, agent_outputs):
            # Check if agent uses this institution's key indicators in analysis
            agent_text = " ".join([
                ao.get("regime", ""),
                ao.get("narrative", ""),
                ao.get("prediction", ""),
                ao.get("risk", ""),
                " ".join(ao.get("beliefs", [])),
            ]).lower()

            # Score indicator coverage
            indicator_hits = sum(
                1 for ind in key_indicators
                if ind.lower() in agent_text
            )
            indicator_score = indicator_hits / max(len(key_indicators), 1)

            # Score thematic alignment
            focus_hits = sum(
                1 for f in focus_keywords
                if f.lower() in agent_text
            )
            focus_score = focus_hits / max(len(focus_keywords), 1)

            combined_score = (indicator_score * 0.6 + focus_score * 0.4)
            scores.append(combined_score)

        if scores:
            benchmark.average_similarity = sum(scores) / len(scores)
        benchmark.total_cases = len(cases)
        return benchmark

    # ── Dimension Comparison Methods ─────────────────────────────────

    def _compare_regime(self, agent_regime: str, case_regime: dict,
                        expert_view: str) -> float:
        """Compare agent's regime assessment to expert's."""
        if not agent_regime:
            return 0.0

        agent_lower = agent_regime.lower()
        expert_lower = expert_view.lower()

        score = 0.0

        # Monetary policy match (0.3 weight)
        monetary = case_regime.get("monetary", "")
        if monetary and monetary in agent_lower:
            score += 0.3
        elif monetary:
            # Check for partial match
            monetary_map = {
                "easing": ["easing", "dovish", "accommodative", "loose"],
                "tightening": ["tightening", "hawkish", "restrictive"],
                "neutral": ["neutral", "on hold", "pause"],
            }
            if any(t in agent_lower for t in monetary_map.get(monetary, [])):
                score += 0.15

        # Growth assessment match (0.25 weight)
        growth = case_regime.get("growth", "")
        growth_map = {
            "accelerating": ["accelerating", "booming", "strong", "above trend"],
            "decelerating": ["decelerating", "slowing", "moderating"],
            "contracting": ["contracting", "recession", "negative"],
            "stable": ["stable", "steady", "trend"],
        }
        if growth and any(t in agent_lower for t in growth_map.get(growth, [])):
            score += 0.25
        elif growth:
            score += 0.08

        # Inflation assessment match (0.25 weight)
        inflation = case_regime.get("inflation", "")
        inflation_map = {
            "rising": ["rising", "increasing", "accelerating", "building"],
            "falling": ["falling", "declining", "decelerating", "disinflation"],
            "stable": ["stable", "anchored", "contained"],
        }
        if inflation and any(t in agent_lower for t in inflation_map.get(inflation, [])):
            score += 0.25
        elif inflation:
            score += 0.08

        # Overall regime framework match (0.2 weight)
        regime_signals = ["regime", "phase", "cycle", "environment", "backdrop"]
        if any(s in agent_lower for s in regime_signals):
            # Check semantic overlap with expert view
            expert_words = set(expert_lower.split())
            agent_words = set(agent_lower.split())
            if expert_words and agent_words:
                overlap = len(expert_words & agent_words) / len(expert_words)
                score += min(overlap, 0.2)

        return min(score, 1.0)

    def _compare_narrative(self, agent_narrative: str,
                           expert_narrative: str,
                           market_beliefs: str) -> float:
        """Compare narrative alignment."""
        if not agent_narrative:
            return 0.0

        agent_lower = agent_narrative.lower()
        expert_lower = expert_narrative.lower()
        beliefs_lower = market_beliefs.lower() if market_beliefs else ""

        # Core concept overlap (0.5 weight)
        expert_words = set(expert_lower.split())
        agent_words = set(agent_lower.split())
        if expert_words and agent_words:
            concept_overlap = len(expert_words & agent_words) / len(expert_words)
        else:
            concept_overlap = 0.0

        # Market belief alignment (0.3 weight)
        if beliefs_lower:
            belief_words = set(beliefs_lower.split())
            belief_overlap = len(agent_words & belief_words) / max(len(belief_words), 1)
        else:
            belief_overlap = 0.3  # Neutral if no beliefs available

        # Narrative structure quality (0.2 weight)
        structure_signals = ["because", "due to", "driven by", "resulting", "leading to",
                            "implies", "suggests", "indicates", "reflects"]
        structure_score = sum(1 for s in structure_signals if s in agent_lower) / len(structure_signals)

        return concept_overlap * 0.5 + belief_overlap * 0.3 + structure_score * 0.2

    def _compare_causal(self, agent_beliefs: list[str],
                        expert_causal_chain: list[str]) -> float:
        """Compare causal reasoning chains."""
        if not agent_beliefs:
            return 0.0

        agent_text = " ".join(agent_beliefs).lower()
        if not expert_causal_chain:
            return 0.5  # Neutral if no expert chain available

        # Check how many causal links the agent identified
        matches = 0
        for link in expert_causal_chain:
            link_lower = link.lower()
            # Extract key concepts from causal link
            concepts = [w for w in link_lower.split()
                       if len(w) > 3 and w not in ("that", "this", "from", "with", "will")]
            key_concepts = concepts[:3]  # First 3 meaningful words
            if key_concepts and all(c in agent_text for c in key_concepts):
                matches += 1.0
            elif key_concepts and any(c in agent_text for c in key_concepts):
                matches += 0.5

        # Direction of causality correct
        causal_signals = ["→", "-->", "leads to", "causes", "drives", "results in", "implies"]
        agent_uses_causal = any(s in agent_text for s in causal_signals)
        causal_bonus = 0.1 if agent_uses_causal else 0.0

        raw_score = matches / len(expert_causal_chain) if expert_causal_chain else 0.5
        return min(raw_score + causal_bonus, 1.0)

    def _compare_direction(self, agent_prediction: str,
                          agent_asset: str,
                          asset_reaction: dict) -> float:
        """Compare directional market calls."""
        if not agent_prediction:
            return 0.0

        agent_lower = agent_prediction.lower()
        direction = asset_reaction.get("direction", "")

        # Direction keyword matching
        direction_keywords = {
            "bullish": ["bullish", "rally", "up", "gain", "rise", "positive", "recovery",
                       "rebound", "boom", "risk on"],
            "bearish": ["bearish", "crash", "selloff", "decline", "fall", "negative",
                       "recession", "depression", "downturn", "risk off"],
            "neutral": ["neutral", "sideways", "range", "flat", "stable", "mixed"],
            "risk_on": ["risk on", "risk-on", "cyclical", "beta"],
            "risk_off": ["risk off", "risk-off", "defensive", "safe haven"],
            "v_recovery": ["recovery", "rebound", "bounce", "v-shaped", "v shape"],
            "muddle_through": ["muddle through", "grinding", "slow growth", "gradual"],
            "crash": ["crash", "collapse", "panic", "extreme", "crisis"],
        }

        # Score: does agent direction match actual?
        if direction:
            expected_terms = direction_keywords.get(direction, [])
            if expected_terms and any(t in agent_lower for t in expected_terms):
                return 0.85
            # Check for opposite direction
            opposite_map = {
                "bullish": ["bearish", "crash", "selloff"],
                "bearish": ["bullish", "rally", "recovery"],
                "risk_on": ["risk off", "safe haven"],
                "risk_off": ["risk on", "cyclical"],
            }
            opposite_terms = opposite_map.get(direction, [])
            if opposite_terms and any(t in agent_lower for t in opposite_terms):
                return 0.1
            return 0.4

        return 0.5  # Neutral if direction not available

    def _compare_risk(self, agent_risk: str, agent_invalidation: str,
                     key_risks: list[str], unknowns: list[str]) -> float:
        """Compare risk awareness."""
        if not agent_risk and not agent_invalidation:
            return 0.0

        agent_text = (agent_risk + " " + agent_invalidation).lower()
        all_expert_risks = key_risks + unknowns

        if not all_expert_risks:
            # If no expert risks available, check if agent shows risk awareness
            risk_signals = ["risk", "danger", "vulnerable", "fragile", "could", "might",
                          "however", "but", "if", "concern", "threat"]
            risk_aware = sum(1 for s in risk_signals if s in agent_text)
            return min(risk_aware / 5, 1.0)

        # Check overlap with expert-identified risks
        matched_risks = 0
        for risk in all_expert_risks:
            risk_lower = risk.lower()
            risk_concepts = [w for w in risk_lower.split()
                           if len(w) > 3 and w not in ("that", "this", "the", "and", "for")]
            key_concepts = risk_concepts[:3]
            if key_concepts and all(c in agent_text for c in key_concepts):
                matched_risks += 1.0
            elif key_concepts and any(c in agent_text for c in key_concepts):
                matched_risks += 0.5

        coverage = matched_risks / len(all_expert_risks) if all_expert_risks else 0.5

        # Invalidation condition quality
        invalidation_bonus = 0.1 if agent_invalidation and len(agent_invalidation) > 20 else 0.0

        return min(coverage + invalidation_bonus, 1.0)

    # ── Divergence Analysis ──────────────────────────────────────────

    def _find_divergences(self, result: ExpertComparisonResult,
                         case: HistoricalCase) -> list[str]:
        """Identify key areas where agent diverged from expert."""
        divergences = []
        if result.regime_agreement < 0.6:
            divergences.append(f"Regime divergence: agent saw '{result.agent_regime[:60]}' vs expert '{result.expert_regime[:60]}'")
        if result.narrative_overlap < 0.5:
            divergences.append(f"Narrative divergence: agent narrative differs from '{result.expert_narrative[:60]}'")
        if result.causal_alignment < 0.5:
            divergences.append(f"Causal misalignment: agent reasoning differs from expert causal chain")
        if result.directional_accuracy < 0.5:
            divergences.append(f"Directional mismatch: agent market call differs from actual outcome")
        if result.risk_concordance < 0.5:
            divergences.append(f"Risk blind spot: agent missed key expert-identified risks")
        return divergences

    def _find_alignments(self, result: ExpertComparisonResult) -> list[str]:
        """Identify key areas where agent aligned with expert."""
        alignments = []
        if result.regime_agreement >= 0.8:
            alignments.append("Strong regime agreement with expert assessment")
        if result.narrative_overlap >= 0.7:
            alignments.append("Narrative closely aligns with expert consensus")
        if result.causal_alignment >= 0.7:
            alignments.append("Causal reasoning matches expert analytical framework")
        if result.directional_accuracy >= 0.8:
            alignments.append("Market direction call aligns with actual outcome")
        if result.risk_concordance >= 0.7:
            alignments.append("Risk assessment covers key expert-identified risks")
        return alignments


# ══════════════════════════════════════════════════════════════════════
# Quick Run
# ══════════════════════════════════════════════════════════════════════

def run_expert_comparison(
    agent_fn=None,
    sample_size: Optional[int] = None,
) -> InstitutionalBenchmark:
    """Run expert comparison across historical cases.

    Args:
        agent_fn: Function that takes blind prompt dict and returns agent output dict
        sample_size: If set, sample N cases

    Returns:
        InstitutionalBenchmark with aggregated expert comparison results
    """
    from validation.v9.blind_test import v10_agent_research

    if agent_fn is None:
        agent_fn = v10_agent_research

    # Load cases
    if not CASES:
        build_all_cases()

    cases = list(CASES)
    if sample_size:
        import random
        random.seed(42)
        cases = random.sample(cases, min(sample_size, len(cases)))

    # Run agent on each case
    comparator = ExpertComparator()
    agent_outputs = []
    blind_cases = []

    for case in cases:
        blind_prompt = {
            "date": case.date,
            "title": case.title,
            "macro_regime": case.macro_regime,
            "starting_conditions": case.starting_conditions,
            "market_beliefs_at_time": case.market_beliefs,
        }
        blind_cases.append(case)
        agent_outputs.append(agent_fn(blind_prompt))

    # Compare
    benchmark = comparator.compare_batch(blind_cases, agent_outputs)

    # Also run institutional style benchmarks
    inst_benchmarks = comparator.benchmark_institutional_styles(blind_cases, agent_outputs)

    print(f"\nExpert Comparison Results ({benchmark.total_cases} cases):")
    print(f"  Average Expert Similarity: {benchmark.average_similarity:.1%}")
    print(f"  V9 Target: >=80% | Status: {'PASS' if benchmark.average_similarity >= 0.8 else 'FAIL'}")
    print(f"\n  Dimension Breakdown:")
    print(f"    Regime Agreement:      {benchmark.regime_agreement_avg:.1%}")
    print(f"    Narrative Overlap:     {benchmark.narrative_overlap_avg:.1%}")
    print(f"    Causal Alignment:      {benchmark.causal_alignment_avg:.1%}")
    print(f"    Directional Accuracy:  {benchmark.directional_accuracy_avg:.1%}")
    print(f"    Risk Concordance:      {benchmark.risk_concordance_avg:.1%}")

    print(f"\n  Institutional Framework Fit:")
    for name, ib in inst_benchmarks.items():
        print(f"    {ib.summary()}")

    return benchmark


if __name__ == "__main__":
    run_expert_comparison(sample_size=20)
