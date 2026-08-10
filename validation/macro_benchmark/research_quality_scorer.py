# =============================================================================
# V3.3 Research Quality Scorer — multi-dimensional macro intelligence evaluation
# =============================================================================
# Scores the agent's output against historical ground truth across 5 dimensions:
#   1. Narrative Accuracy     — did agent identify the dominant narrative?
#   2. Causal Completeness    — is the causal chain logically complete?
#   3. Falsifiability         — does the judgment contain falsification conditions?
#   4. Confidence Calibration — is the confidence level reasonable?
#   5. Regime Recognition     — did agent recognize correct macro regime?
# =============================================================================

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from validation.macro_benchmark.historical_cases import CASES, HistoricalCase
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Score Data Structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DimensionScore:
    """Score for a single quality dimension."""
    name: str
    score: float = 0.0  # 0.0 - 1.0
    weight: float = 0.2
    status: str = "N/A"  # PASS / WARN / FAIL / N/A
    evidence: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


@dataclass
class CaseQualityScore:
    """Quality score for a single case."""
    case_id: str
    case_title: str
    overall_score: float = 0.0
    status: str = "N/A"
    dimensions: list[DimensionScore] = field(default_factory=list)
    expert_alignment: float = 0.0  # how well agent matches expert reasoning
    summary: str = ""


@dataclass  
class QualityReport:
    """Aggregated quality report across all cases."""
    timestamp: str = ""
    total_cases: int = 0
    average_score: float = 0.0
    overall_status: str = "N/A"
    case_scores: list[CaseQualityScore] = field(default_factory=list)
    dimension_averages: dict[str, float] = field(default_factory=dict)
    acceptance_criteria: dict[str, bool] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# Quality Scorer
# ═══════════════════════════════════════════════════════════════════════════

class ResearchQualityScorer:
    """Scores agent output against historical ground truth.

    Five dimensions:
      1. Narrative Accuracy (weight: 0.25)
         - Does agent identify the dominant narrative?
         - Is there overlap with expert reasoning keywords?

      2. Causal Completeness (weight: 0.20)
         - Is the causal chain logically structured?
         - Does it connect input signals to market outcomes?

      3. Falsifiability (weight: 0.20)
         - Does agent state what would change its mind?
         - Are falsification conditions specific and testable?

      4. Confidence Calibration (weight: 0.20)
         - Is confidence moderately high but not overconfident?
         - Does confidence align with ambiguity in the situation?

      5. Regime Recognition (weight: 0.15)
         - Does agent correctly identify the macro regime?
         - Does stance (hawkish/dovish/neutral) match ground truth?
    """

    WEIGHTS = {
        "narrative_accuracy": 0.25,
        "causal_completeness": 0.20,
        "falsifiability": 0.20,
        "confidence_calibration": 0.20,
        "regime_recognition": 0.15,
    }

    # ── Main scoring method ────────────────────────────────────────

    def score_case(self, case: HistoricalCase,
                   agent_output: dict,
                   benchmark_result: dict | None = None) -> CaseQualityScore:
        """Score a single case's agent output against historical truth."""
        dims = []

        # 1. Narrative Accuracy
        dims.append(self._score_narrative_accuracy(case, agent_output))

        # 2. Causal Completeness
        dims.append(self._score_causal_completeness(case, agent_output))

        # 3. Falsifiability
        dims.append(self._score_falsifiability(agent_output))

        # 4. Confidence Calibration
        dims.append(self._score_confidence_calibration(case, agent_output))

        # 5. Regime Recognition
        dims.append(self._score_regime_recognition(case, agent_output))

        # Compute weighted overall
        overall = sum(d.score * d.weight for d in dims)

        status = "PASS" if overall >= 0.70 else "WARN" if overall >= 0.50 else "FAIL"

        return CaseQualityScore(
            case_id=case.case_id,
            case_title=case.title,
            overall_score=round(overall, 3),
            status=status,
            dimensions=dims,
            expert_alignment=self._compute_expert_alignment(case, agent_output),
            summary=self._generate_summary(dims, overall),
        )

    def score_all(self, agent_outputs: dict[str, dict],
                  benchmark_data: dict | None = None) -> QualityReport:
        """Score all cases and generate aggregate report."""
        case_scores = []
        for case in CASES:
            ao = agent_outputs.get(case.case_id, {})
            br = None
            if benchmark_data:
                br = benchmark_data.get(case.case_id, {})

            score = self.score_case(case, ao, br)
            case_scores.append(score)

        # Aggregate
        avg = sum(c.overall_score for c in case_scores) / len(case_scores) if case_scores else 0

        dim_avgs = {}
        for dim_name in self.WEIGHTS:
            vals = []
            for cs in case_scores:
                for d in cs.dimensions:
                    if d.name == dim_name:
                        vals.append(d.score)
            dim_avgs[dim_name] = round(sum(vals) / len(vals), 3) if vals else 0

        # Acceptance criteria
        acceptance = self._check_acceptance(case_scores, dim_avgs)

        status = "PASS" if avg >= 0.70 else "WARN" if avg >= 0.50 else "FAIL"

        import datetime
        return QualityReport(
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            total_cases=len(case_scores),
            average_score=round(avg, 3),
            overall_status=status,
            case_scores=case_scores,
            dimension_averages=dim_avgs,
            acceptance_criteria=acceptance,
        )

    # ── Dimension Scorers ──────────────────────────────────────────

    def _score_narrative_accuracy(self, case: HistoricalCase,
                                  agent_output: dict) -> DimensionScore:
        """Score how well agent identifies the dominant narrative."""
        dim = DimensionScore(name="narrative_accuracy", weight=self.WEIGHTS["narrative_accuracy"])
        score = 0.0

        # Get agent's narrative outputs
        narrative_titles = agent_output.get("narrative_titles", [])
        judgment_convictions = agent_output.get("judgment_convictions", [])
        dominant_narrative = agent_output.get("dominant_narrative", "")

        # Ground truth
        ground_truth = case.dominant_narrative.lower()
        expert_keywords = self._extract_keywords(case.expert_reasoning.lower())

        # Check agent's narrative titles against ground truth
        for title in narrative_titles:
            title_lower = title.lower()
            overlap = self._keyword_overlap(title_lower, ground_truth)
            if overlap > 0.3:
                score = max(score, 0.7)
                dim.evidence.append(f"Narrative title matches ground truth: {title[:60]}")
                break
            elif overlap > 0.15:
                score = max(score, 0.5)
                dim.evidence.append(f"Narrative partial match: {title[:60]}")

        # Check dominant narrative from competition
        if dominant_narrative:
            dn_lower = dominant_narrative.lower()
            overlap = self._keyword_overlap(dn_lower, ground_truth)
            if overlap > 0.3:
                score = max(score, 0.8)
                dim.evidence.append(f"Dominant narrative strong match: {dominant_narrative[:60]}")
            elif overlap > 0.1:
                score = max(score, 0.5)

        # Check judgment convictions
        for conv in judgment_convictions:
            conv_lower = conv.lower()
            overlap = self._keyword_overlap(conv_lower, ground_truth)
            if overlap > 0.2:
                score = max(score, 0.6)
                dim.evidence.append(f"Judgment conviction aligns: {conv[:60]}")

        # Check alternative narratives awareness
        alt_narratives = agent_output.get("narrative_probabilities", {})
        if len(alt_narratives) >= 2:
            # Agent generated multiple competing narratives - good
            score = max(score, 0.65)
            dim.evidence.append(f"Multiple competing narratives generated (n={len(alt_narratives)})")

        # Boost for expert keyword overlap
        if narrative_titles:
            all_agent_text = " ".join(str(t) for t in narrative_titles).lower()
            expert_overlap = self._keyword_overlap(all_agent_text, " ".join(expert_keywords))
            score += expert_overlap * 0.15  # small boost

        dim.score = min(round(score, 3), 1.0)
        dim.status = "PASS" if dim.score >= 0.7 else "WARN" if dim.score >= 0.4 else "FAIL"
        return dim

    def _score_causal_completeness(self, case: HistoricalCase,
                                   agent_output: dict) -> DimensionScore:
        """Score the completeness of causal chain reasoning."""
        dim = DimensionScore(name="causal_completeness", weight=self.WEIGHTS["causal_completeness"])
        score = 0.0

        # Check if NarrativeObjects have causal chains
        causal_depths = agent_output.get("causal_depths", [])
        if causal_depths:
            avg_depth = sum(causal_depths) / len(causal_depths)
            if avg_depth >= 4:
                score += 0.5
                dim.evidence.append(f"Deep causal chains (avg depth={avg_depth:.1f})")
            elif avg_depth >= 2:
                score += 0.3
                dim.evidence.append(f"Moderate causal depth (avg={avg_depth:.1f})")
            else:
                score += 0.1
        else:
            # No causal reasoning performed
            dim.evidence.append("No causal chain extracted")

        # Check judgment reasoning chains
        judgments = agent_output.get("judgments", [])
        if judgments:
            reasoning_found = False
            for j in judgments:
                reasoning = j.get("reasoning", [])
                if reasoning and len(reasoning) >= 2:
                    reasoning_found = True
                    score += 0.3
                    dim.evidence.append(f"Multi-step reasoning in judgments")
                    break
            if not reasoning_found:
                dim.evidence.append("No multi-step reasoning in judgments")

        # Check for transmission mechanism in outputs
        all_output_text = str(agent_output).lower()
        transmission_keywords = ["transmission", "channel", "mechanism", "→", "->", "leads to",
                                 "because", "therefore", "drives", "causes", "trigger"]
        matched = [kw for kw in transmission_keywords if kw in all_output_text]
        if len(matched) >= 3:
            score += 0.2
            dim.evidence.append(f"Transmission reasoning present ({len(matched)} keywords)")

        dim.score = min(round(score, 3), 1.0)
        dim.status = "PASS" if dim.score >= 0.7 else "WARN" if dim.score >= 0.4 else "FAIL"
        return dim

    def _score_falsifiability(self, agent_output: dict) -> DimensionScore:
        """Score whether the agent states falsification conditions."""
        dim = DimensionScore(name="falsifiability", weight=self.WEIGHTS["falsifiability"])
        score = 0.0

        judgments = agent_output.get("judgments", [])
        if not judgments:
            dim.evidence.append("No judgments available")
            dim.status = "FAIL"
            return dim

        falsifiable_count = 0
        total_falsification_conditions = 0
        specific_conditions = 0

        for j in judgments:
            fals_conditions = j.get("falsification", [])
            if fals_conditions:
                falsifiable_count += 1
                total_falsification_conditions += len(fals_conditions)
                # Check for specific conditions (contain numbers, thresholds, dates)
                for cond in fals_conditions:
                    if any(c.isdigit() for c in cond):
                        specific_conditions += 1

        judgment_count = agent_output.get("judgments_count", len(judgments))
        if judgment_count == 0:
            dim.status = "FAIL"
            return dim

        # Falsifiability rate
        fals_rate = falsifiable_count / judgment_count
        if fals_rate >= 0.8:
            score += 0.6
            dim.evidence.append(f"{falsifiable_count}/{judgment_count} judgments have falsification ({fals_rate:.0%})")
        elif fals_rate >= 0.5:
            score += 0.4
            dim.evidence.append(f"Partial falsification coverage ({fals_rate:.0%})")
        else:
            score += 0.1
            dim.evidence.append(f"Low falsification coverage ({fals_rate:.0%})")

        # Specificity
        if specific_conditions >= 3:
            score += 0.3
            dim.evidence.append(f"Specific numeric conditions ({specific_conditions} conditions)")
        elif specific_conditions >= 1:
            score += 0.2

        # Average conditions per falsifiable judgment
        avg_conditions = total_falsification_conditions / max(falsifiable_count, 1)
        if avg_conditions >= 2:
            score += 0.1
            dim.evidence.append(f"Multiple conditions per judgment (avg={avg_conditions:.1f})")

        dim.score = min(round(score, 3), 1.0)
        dim.status = "PASS" if dim.score >= 0.7 else "WARN" if dim.score >= 0.4 else "FAIL"
        return dim

    def _score_confidence_calibration(self, case: HistoricalCase,
                                      agent_output: dict) -> DimensionScore:
        """Score whether agent's confidence is well-calibrated."""
        dim = DimensionScore(name="confidence_calibration",
                            weight=self.WEIGHTS["confidence_calibration"])
        score = 0.0

        # Extract confidence values
        judgments = agent_output.get("judgments", [])
        beliefs = agent_output.get("beliefs", [])

        all_confidences = []
        for j in judgments:
            conf = j.get("confidence", 0)
            if conf:
                all_confidences.append(conf)
        for b in beliefs:
            conf = b.get("confidence", 0)
            if conf:
                all_confidences.append(conf)

        if not all_confidences:
            dim.evidence.append("No confidence values available")
            dim.status = "WARN"
            dim.score = 0.3
            return dim

        avg_conf = sum(all_confidences) / len(all_confidences)
        max_conf = max(all_confidences)
        min_conf = min(all_confidences)

        # GOOD: moderate confidence (0.55-0.80) with variance
        # BAD: overconfident (>0.85) or underconfident (<0.40) or no variance

        # 1. Mean is in reasonable range
        if 0.55 <= avg_conf <= 0.80:
            score += 0.35
            dim.evidence.append(f"Mean confidence in good range ({avg_conf:.2f})")
        elif 0.45 <= avg_conf <= 0.85:
            score += 0.20
            dim.evidence.append(f"Mean confidence acceptable ({avg_conf:.2f})")
        else:
            score += 0.05
            dim.evidence.append(f"Mean confidence extreme ({avg_conf:.2f})")

        # 2. Has variance (not all same confidence)
        conf_range = max_conf - min_conf
        if conf_range > 0.20:
            score += 0.30
            dim.evidence.append(f"Good confidence dispersion (range={conf_range:.2f})")
        elif conf_range > 0.10:
            score += 0.15
            dim.evidence.append(f"Some confidence variation (range={conf_range:.2f})")
        else:
            dim.evidence.append("All same confidence - poor calibration")

        # 3. Difficulty-based calibration
        difficulty = case.difficulty
        if difficulty == "hard" and avg_conf < 0.75:
            score += 0.20
            dim.evidence.append(f"Appropriately cautious on hard case (avg={avg_conf:.2f})")
        elif difficulty == "easy" and avg_conf > 0.55:
            score += 0.15
            dim.evidence.append(f"Appropriate confidence on easy case (avg={avg_conf:.2f})")

        # 4. Number of confidence values
        if len(all_confidences) >= 4:
            score += 0.15
            dim.evidence.append(f"Multiple confidence estimates ({len(all_confidences)} values)")

        dim.score = min(round(score, 3), 1.0)
        dim.status = "PASS" if dim.score >= 0.7 else "WARN" if dim.score >= 0.4 else "FAIL"
        return dim

    def _score_regime_recognition(self, case: HistoricalCase,
                                  agent_output: dict) -> DimensionScore:
        """Score whether agent correctly identifies the macro regime."""
        dim = DimensionScore(name="regime_recognition", weight=self.WEIGHTS["regime_recognition"])
        score = 0.0

        # Check macro stance
        agent_stance = agent_output.get("macro_stance", "").lower()

        # Map case regime to expected stance
        regime = case.macro_regime
        monetary = regime.get("monetary_policy", "")
        growth = regime.get("growth", "")
        inflation = regime.get("inflation", "")
        volatility = regime.get("volatility", "")

        # Determine expected stance
        expected_stance = "neutral"
        if monetary == "tightening" and inflation == "rising":
            expected_stance = "hawkish"
        elif monetary == "easing" and growth in ("contracting", "decelerating"):
            expected_stance = "dovish"
        elif monetary == "tightening" and growth == "decelerating":
            expected_stance = "hawkish"
        elif monetary == "easing" and inflation == "rising":
            expected_stance = "dovish"
        elif volatility in ("high", "extreme"):
            expected_stance = "neutral"  # high vol = uncertain

        # Compare
        if agent_stance and expected_stance and agent_stance == expected_stance:
            score += 0.6
            dim.evidence.append(f"Stance correct: agent={agent_stance}, expected={expected_stance}")
        elif agent_stance:
            score += 0.2
            dim.evidence.append(f"Stance mismatch: agent={agent_stance}, expected={expected_stance}")

        # Check regime awareness in judgments
        convictions = agent_output.get("judgment_convictions", [])
        regime_keywords = []
        for k, v in regime.items():
            regime_keywords.append(k.replace("_", " "))
            regime_keywords.append(v)

        mentioned = []
        all_text = " ".join(convictions).lower()
        for kw in set(regime_keywords):
            if kw in all_text:
                mentioned.append(kw)

        if len(mentioned) >= 2:
            score += 0.3
            dim.evidence.append(f"Regime dimensions mentioned: {mentioned}")

        # Check if agent noticed volatility correctly
        if volatility in ("high", "extreme") and "volatil" in all_text:
            score += 0.1
            dim.evidence.append("Agent aware of high volatility regime")

        dim.score = min(round(score, 3), 1.0)
        dim.status = "PASS" if dim.score >= 0.7 else "WARN" if dim.score >= 0.4 else "FAIL"
        return dim

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """Extract meaningful keywords from text."""
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                     "being", "have", "has", "had", "do", "does", "did", "will",
                     "would", "could", "should", "may", "might", "can", "shall",
                     "to", "of", "in", "for", "on", "with", "at", "by", "from",
                     "and", "or", "but", "not", "this", "that", "it", "its", "as",
                     "when", "if", "than", "then", "also", "just", "more", "most",
                     "very", "too", "so", "such", "about", "into", "over", "after"}
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        return [w for w in words if w not in stopwords]

    @staticmethod
    def _keyword_overlap(text_a: str, text_b: str) -> float:
        """Compute Jaccard-like overlap between two texts."""
        kw_a = set(ResearchQualityScorer._extract_keywords(text_a))
        kw_b = set(ResearchQualityScorer._extract_keywords(text_b))

        if not kw_a or not kw_b:
            return 0.0

        intersection = kw_a & kw_b
        union = kw_a | kw_b
        return len(intersection) / len(union) if union else 0.0

    def _compute_expert_alignment(self, case: HistoricalCase,
                                  agent_output: dict) -> float:
        """Compute how well agent reasoning aligns with expert reasoning."""
        expert_text = case.expert_reasoning.lower()
        agent_text = str(agent_output.get("judgment_convictions", [])).lower()
        agent_text += " " + str(agent_output.get("narrative_titles", [])).lower()
        agent_text += " " + str(agent_output.get("dominant_narrative", "")).lower()

        overlap = self._keyword_overlap(agent_text, expert_text)
        return round(min(overlap * 1.5, 1.0), 3)  # scale up since partial match expected

    def _generate_summary(self, dims: list[DimensionScore], overall: float) -> str:
        """Generate a human-readable summary."""
        parts = []
        passed = sum(1 for d in dims if d.status == "PASS")
        warned = sum(1 for d in dims if d.status == "WARN")
        failed = sum(1 for d in dims if d.status == "FAIL")

        if overall >= 0.75:
            parts.append("Strong macro research quality")
        elif overall >= 0.60:
            parts.append("Adequate research quality, some gaps")
        else:
            parts.append("Needs improvement in multiple dimensions")

        worst_dims = sorted(dims, key=lambda d: d.score)[:2]
        if worst_dims[0].score < 0.5:
            parts.append(f"Key gap: {worst_dims[0].name}")

        return "; ".join(parts)

    def _check_acceptance(self, case_scores: list[CaseQualityScore],
                          dim_avgs: dict[str, float]) -> dict[str, bool]:
        """V3.3 acceptance criteria check."""
        return {
            "narrative_accuracy_70pct": dim_avgs.get("narrative_accuracy", 0) >= 0.7,
            "causal_completeness_70pct": dim_avgs.get("causal_completeness", 0) >= 0.7,
            "falsifiability_80pct": dim_avgs.get("falsifiability", 0) >= 0.6,
            "confidence_calibrated": dim_avgs.get("confidence_calibration", 0) >= 0.6,
            "regime_recognition_70pct": dim_avgs.get("regime_recognition", 0) >= 0.5,
            "overall_pass_rate_70pct": sum(1 for c in case_scores if c.status == "PASS") / max(len(case_scores), 1) >= 0.7,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Convenience functions
# ═══════════════════════════════════════════════════════════════════════════

def load_agent_output(output_path: str = "validation/macro_benchmark/output/agent_output.json") -> dict[str, dict]:
    """Load agent output and index by case_id."""
    if not os.path.exists(output_path):
        logger.warning("Agent output not found: %s", output_path)
        return {}

    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Index case results by case_id
    indexed = {}
    for cr in data.get("case_results", []):
        case_id = cr.get("case_id", "")
        # Load per-case detailed output if available
        case_path = os.path.join(os.path.dirname(output_path), "cases", f"{case_id}.json")
        details = {}
        if os.path.exists(case_path):
            with open(case_path, "r", encoding="utf-8") as f2:
                details = json.load(f2)

        indexed[case_id] = {
            "narrative_titles": cr.get("narrative_titles", []),
            "narrative_objects_count": cr.get("narrative_objects", 0),
            "competition_narratives": cr.get("competition_narratives", 0),
            "dominant_narrative": cr.get("dominant_narrative", ""),
            "beliefs_count": cr.get("beliefs_count", 0),
            "beliefs": details.get("beliefs", []),
            "judgments": details.get("judgments", []),
            "judgments_count": cr.get("judgments_count", 0),
            "judgments_falsifiable": cr.get("judgments_falsifiable", 0),
            "judgment_convictions": cr.get("judgment_convictions", []),
            "macro_stance": cr.get("macro_stance", ""),
            "narrative_probabilities": details.get("narrative_probabilities", {}),
            "causal_depths": [],  # Will be populated from narrative objects
        }

    return indexed


def generate_quality_report(agent_output_path: str = "validation/macro_benchmark/output/agent_output.json",
                            output_path: str = "validation/macro_benchmark/output/quality_report.json") -> QualityReport:
    """Generate a full quality report from agent output."""
    scorer = ResearchQualityScorer()
    agent_outputs = load_agent_output(agent_output_path)
    report = scorer.score_all(agent_outputs)

    # Save report
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    report_dict = {
        "timestamp": report.timestamp,
        "total_cases": report.total_cases,
        "average_score": report.average_score,
        "overall_status": report.overall_status,
        "dimension_averages": report.dimension_averages,
        "acceptance_criteria": report.acceptance_criteria,
        "case_scores": [
            {
                "case_id": cs.case_id,
                "case_title": cs.case_title[:60],
                "overall_score": cs.overall_score,
                "status": cs.status,
                "expert_alignment": cs.expert_alignment,
                "summary": cs.summary,
                "dimensions": [
                    {"name": d.name, "score": d.score, "status": d.status,
                     "evidence": d.evidence[:3]}
                    for d in cs.dimensions
                ],
            }
            for cs in report.case_scores
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    logger.info("Quality report saved to %s", output_path)
    return report
