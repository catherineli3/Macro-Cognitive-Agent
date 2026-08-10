# =============================================================================
# V9 Macro Understanding Scoring Engine — 100-Point Blind Evaluation
# =============================================================================
# Five dimensions, 20 points each:
#   1. Regime Recognition (20)  — Did agent identify correct macro regime?
#   2. Narrative Identification (20) — Did agent identify dominant narrative?
#   3. Causal Reasoning (20) — Is the reasoning chain logically sound?
#   4. Prediction Accuracy (20) — How close was the prediction to reality?
#   5. Risk Awareness (20) — Did agent identify key risks and unknowns?
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


MACRO_UNDERSTANDING_DIMENSIONS = [
    "regime_recognition",
    "narrative_identification",
    "causal_reasoning",
    "prediction_accuracy",
    "risk_awareness",
]


@dataclass
class DimensionScore:
    dimension: str
    score: float  # 0-20
    max_score: float = 20.0
    explanation: str = ""
    agent_answer: str = ""
    expert_answer: str = ""
    gap: str = ""  # what agent missed

    @property
    def normalized(self) -> float:
        return self.score / self.max_score

    @property
    def grade(self) -> str:
        if self.score >= 18:
            return "A"
        elif self.score >= 15:
            return "B"
        elif self.score >= 12:
            return "C"
        elif self.score >= 8:
            return "D"
        return "F"


@dataclass
class BlindTestResult:
    """Complete result of a blind research test."""
    case_id: str
    case_date: str
    case_title: str

    # Overall
    total_score: float = 0.0  # 0-100
    passed: bool = False  # >= 70

    # Per dimension
    regime_recognition: DimensionScore = field(default_factory=lambda: DimensionScore("regime_recognition", 0))
    narrative_identification: DimensionScore = field(default_factory=lambda: DimensionScore("narrative_identification", 0))
    causal_reasoning: DimensionScore = field(default_factory=lambda: DimensionScore("causal_reasoning", 0))
    prediction_accuracy: DimensionScore = field(default_factory=lambda: DimensionScore("prediction_accuracy", 0))
    risk_awareness: DimensionScore = field(default_factory=lambda: DimensionScore("risk_awareness", 0))

    # Agent output
    agent_regime: str = ""
    agent_narrative: str = ""
    agent_beliefs: list[str] = field(default_factory=list)
    agent_prediction: str = ""
    agent_risk: str = ""
    agent_invalidation: str = ""
    agent_asset_implication: str = ""

    # Expert ground truth
    expert_regime: str = ""
    expert_narrative: str = ""
    expert_prediction: str = ""

    # Comparison
    key_misses: list[str] = field(default_factory=list)
    key_strengths: list[str] = field(default_factory=list)
    improvement_notes: str = ""

    @property
    def grade(self) -> str:
        if self.total_score >= 90:
            return "A"
        elif self.total_score >= 80:
            return "B"
        elif self.total_score >= 70:
            return "C"
        elif self.total_score >= 60:
            return "D"
        return "F"


class MacroUnderstandingScorer:
    """Scores agent research output against expert ground truth.

    This is the core V9 evaluation engine. Each dimension is scored
    independently, then aggregated into a 0-100 scale.
    """

    # ── Regime Recognition (20 pts) ──────────────────────────────────

    @staticmethod
    def score_regime(agent_regime: str, expert_regime: dict, macro_context: dict) -> DimensionScore:
        """Score how well agent identified the correct macro regime.

        Regimes are defined by policy stance (monetary + fiscal) and
        economic state (growth + inflation + volatility).
        """
        score = DimensionScore("regime_recognition", 0)

        if not agent_regime:
            score.explanation = "No regime identified"
            score.gap = "Agent produced no regime assessment"
            return score

        agent_lower = agent_regime.lower()
        expert_text = expert_regime.get("description", "")

        # Monetary policy match (6 pts)
        monetary = expert_regime.get("monetary", "")
        if monetary and monetary in agent_lower:
            score.score += 6
        elif monetary and any(t in agent_lower for t in ["tightening", "hawkish", "easing", "dovish"]):
            score.score += 3  # partial match

        # Fiscal policy match (4 pts)
        fiscal = expert_regime.get("fiscal", "")
        if fiscal and fiscal in agent_lower:
            score.score += 4
        elif fiscal and any(t in agent_lower for t in ["expansionary", "contractionary", "neutral"]):
            score.score += 2

        # Growth direction (4 pts)
        growth = expert_regime.get("growth", "")
        if growth and any(t in agent_lower for t in [growth, "accelerating", "decelerating", "contracting", "stable"]):
            if growth in agent_lower:
                score.score += 4
            else:
                score.score += 2

        # Inflation direction (4 pts)
        inflation = expert_regime.get("inflation", "")
        if inflation and any(t in agent_lower for t in [inflation, "rising", "falling", "stable"]):
            if inflation in agent_lower:
                score.score += 4
            else:
                score.score += 2

        # Volatility assessment (2 pts)
        vol = expert_regime.get("volatility", "")
        if vol and vol in agent_lower:
            score.score += 2
        elif vol and any(t in agent_lower for t in ["high", "moderate", "low", "extreme"]):
            score.score += 1

        score.score = min(score.score, 20)
        score.explanation = f"Regime recognition: {score.score}/20"
        score.agent_answer = agent_regime
        score.expert_answer = expert_text
        if score.score < 15:
            score.gap = "Agent missed key regime dimensions"
        return score

    # ── Narrative Identification (20 pts) ─────────────────────────────

    @staticmethod
    def score_narrative(agent_narrative: str, expert_narrative: str, competing: list[str]) -> DimensionScore:
        """Score how well agent identified the dominant narrative."""
        score = DimensionScore("narrative_identification", 0)
        score.agent_answer = agent_narrative
        score.expert_answer = expert_narrative

        if not agent_narrative:
            score.explanation = "No narrative identified"
            score.gap = "Agent produced no narrative assessment"
            return score

        agent_lower = agent_narrative.lower()
        expert_lower = expert_narrative.lower()

        # Word overlap for core concepts
        expert_words = set(expert_lower.split())
        agent_words = set(agent_lower.split())
        if expert_words and agent_words:
            overlap = expert_words.intersection(agent_words)
            key_overlap = len(overlap) / max(len(expert_words), 1)

            if key_overlap > 0.5:
                score.score = 18
            elif key_overlap > 0.35:
                score.score = 14
            elif key_overlap > 0.2:
                score.score = 10
            else:
                score.score = 5

        # Bonus: mentions competing narratives (3 pts)
        if competing:
            mentioned_competing = sum(1 for c in competing if c.lower()[:20] in agent_lower)
            score.score += min(mentioned_competing * 1.5, 3)

        score.score = min(score.score, 20)
        score.explanation = f"Narrative match score: {score.score}/20"
        if score.score < 12:
            score.gap = "Agent narrative significantly diverges from expert consensus"
        return score

    # ── Causal Reasoning (20 pts) ────────────────────────────────────

    @staticmethod
    def score_causality(agent_beliefs: list[str], expected_beliefs: list[str],
                        expected_causal_chain: list[str]) -> DimensionScore:
        """Score the logical reasoning chain quality.

        Checks if agent identifies cause → effect correctly.
        """
        score = DimensionScore("causal_reasoning", 0)

        if not agent_beliefs:
            score.explanation = "No beliefs/reasoning provided"
            score.gap = "Agent produced no causal reasoning"
            return score

        # Structural scoring:
        # - 10 pts: number of beliefs (depth)
        # - 10 pts: alignment with expected causal chain

        # Depth scoring (10 pts max)
        belief_count = len(agent_beliefs)
        if belief_count >= 5:
            score.score += 10
        elif belief_count >= 3:
            score.score += 7
        elif belief_count >= 1:
            score.score += 4

        # Causal chain alignment (10 pts)
        if expected_causal_chain:
            agent_text = " ".join(agent_beliefs).lower()
            matches = 0
            for link in expected_causal_chain:
                link_lower = link.lower()
                if link_lower in agent_text:
                    matches += 1
                elif any(w in agent_text for w in link_lower.split()[:3]):
                    matches += 0.5
            score.score += min(matches * 2, 10)

        score.score = min(score.score, 20)
        score.explanation = f"Causal reasoning depth: {score.score}/20"
        score.agent_answer = "; ".join(agent_beliefs[:3])
        score.expert_answer = "; ".join(expected_beliefs[:3])
        if score.score < 12:
            score.gap = "Agent reasoning lacks depth or misses key causal links"
        return score

    # ── Prediction Accuracy (20 pts) ─────────────────────────────────

    @staticmethod
    def score_prediction(agent_prediction: str, actual_outcome: str,
                         agent_asset: str, asset_reaction: dict) -> DimensionScore:
        """Score how well agent's prediction matched actual outcome."""
        score = DimensionScore("prediction_accuracy", 0)
        score.agent_answer = agent_prediction
        score.expert_answer = actual_outcome

        if not agent_prediction:
            score.explanation = "No prediction provided"
            score.gap = "Agent produced no prediction"
            return score

        agent_lower = agent_prediction.lower()
        actual_lower = actual_outcome.lower()

        # Direction match (10 pts)
        direction = asset_reaction.get("direction", "")
        direction_keywords = {
            "bullish": ["bullish", "rally", "upward", "positive", "gain", "rise"],
            "bearish": ["bearish", "crash", "selloff", "decline", "negative", "fall", "downturn"],
            "neutral": ["neutral", "sideways", "range", "flat", "stable"],
            "v_recovery": ["recovery", "rebound", "bounce", "v-shaped"],
            "crash": ["crash", "collapse", "panic", "extreme"],
        }
        agent_direction = _detect_direction(agent_lower)
        actual_direction = direction
        if agent_direction == actual_direction or (
            actual_direction in direction_keywords and
            any(kw in agent_lower for kw in direction_keywords[actual_direction])
        ):
            score.score += 10
        elif agent_direction and actual_direction:
            # Partial match (opposite direction guessed partially)
            score.score += 3

        # Precision: mentions key drivers (5 pts)
        actual_mentions = set(actual_lower.split())
        prediction_mentions = set(agent_lower.split())
        precision = len(actual_mentions.intersection(prediction_mentions)) / max(len(actual_mentions), 1)
        score.score += min(precision * 10, 5)

        # Asset implication match (5 pts)
        if agent_asset and agent_asset.lower() in agent_lower:
            score.score += 5
        elif agent_asset:
            score.score += 2

        score.score = min(score.score, 20)
        score.explanation = f"Prediction accuracy: {score.score}/20"
        if score.score < 10:
            score.gap = "Agent prediction significantly off from actual outcome"
        return score

    # ── Risk Awareness (20 pts) ──────────────────────────────────────

    @staticmethod
    def score_risk(agent_risk: str, agent_invalidation: str,
                   key_risks: list[str], actual_unknowns: list[str]) -> DimensionScore:
        """Score risk awareness and identification of unknowns."""
        score = DimensionScore("risk_awareness", 0)
        score.agent_answer = agent_risk

        if not agent_risk and not agent_invalidation:
            score.explanation = "No risk assessment provided"
            score.gap = "Agent produced no risk assessment"
            return score

        # Key risk identification (10 pts)
        if key_risks:
            agent_lower = (agent_risk + " " + agent_invalidation).lower()
            matches = 0
            for risk in key_risks:
                risk_lower = risk.lower()
                if risk_lower in agent_lower:
                    matches += 1
                elif any(w in agent_lower for w in risk_lower.split()[:2]):
                    matches += 0.5
            score.score += min(matches * 2, 10)

        # Unknowns acknowledgment (5 pts)
        unknown_signals = ["risk", "unknown", "uncertainty", "if", "could", "might", "however", "but", "tail"]
        agent_lower = (agent_risk + " " + agent_invalidation).lower()
        unknown_count = sum(1 for s in unknown_signals if s in agent_lower)
        score.score += min(unknown_count, 5)

        # Invalidation conditions (5 pts)
        invalidation_signals = ["invalid", "if", "unless", "break", "below", "above", "threshold", "stop"]
        if agent_invalidation:
            inv_count = sum(1 for s in invalidation_signals if s in agent_invalidation.lower())
            score.score += min(inv_count, 5)

        score.score = min(score.score, 20)
        score.explanation = f"Risk awareness: {score.score}/20"
        score.expert_answer = "; ".join(key_risks[:3])
        if score.score < 10:
            score.gap = "Agent insufficiently addresses key risks and unknowns"
        return score

    # ── Aggregate ────────────────────────────────────────────────────

    @classmethod
    def score_full(cls, case_id: str, case_date: str, case_title: str,
                   agent_output: dict, expert_ground_truth: dict) -> BlindTestResult:
        """Run full 100-point blind test scoring."""
        result = BlindTestResult(
            case_id=case_id,
            case_date=case_date,
            case_title=case_title,
            agent_regime=agent_output.get("regime", ""),
            agent_narrative=agent_output.get("narrative", ""),
            agent_beliefs=agent_output.get("beliefs", []),
            agent_prediction=agent_output.get("prediction", ""),
            agent_risk=agent_output.get("risk", ""),
            agent_invalidation=agent_output.get("invalidation", ""),
            agent_asset_implication=agent_output.get("asset_implication", ""),
            expert_regime=expert_ground_truth.get("regime_description", ""),
            expert_narrative=expert_ground_truth.get("dominant_narrative", ""),
            expert_prediction=expert_ground_truth.get("actual_outcome", ""),
        )

        result.regime_recognition = cls.score_regime(
            agent_output.get("regime", ""),
            expert_ground_truth.get("regime", {}),
            expert_ground_truth.get("starting_conditions", {}),
        )
        result.narrative_identification = cls.score_narrative(
            agent_output.get("narrative", ""),
            expert_ground_truth.get("dominant_narrative", ""),
            expert_ground_truth.get("competing_narratives", []),
        )
        result.causal_reasoning = cls.score_causality(
            agent_output.get("beliefs", []),
            expert_ground_truth.get("market_beliefs", "").split(";"),
            expert_ground_truth.get("causal_chain", []),
        )
        result.prediction_accuracy = cls.score_prediction(
            agent_output.get("prediction", ""),
            expert_ground_truth.get("actual_outcome", ""),
            agent_output.get("asset_implication", ""),
            expert_ground_truth.get("asset_reaction", {}),
        )
        result.risk_awareness = cls.score_risk(
            agent_output.get("risk", ""),
            agent_output.get("invalidation", ""),
            expert_ground_truth.get("key_risks", []),
            expert_ground_truth.get("unknowns", []),
        )

        result.total_score = (
            result.regime_recognition.score +
            result.narrative_identification.score +
            result.causal_reasoning.score +
            result.prediction_accuracy.score +
            result.risk_awareness.score
        )
        result.passed = result.total_score >= 70

        # Key misses and strengths
        result.key_misses = [d.gap for d in [
            result.regime_recognition, result.narrative_identification,
            result.causal_reasoning, result.prediction_accuracy, result.risk_awareness
        ] if d.gap]
        result.key_strengths = [d.explanation for d in [
            result.regime_recognition, result.narrative_identification,
            result.causal_reasoning, result.prediction_accuracy, result.risk_awareness
        ] if d.score >= 15]

        return result


def _detect_direction(text: str) -> str:
    """Detect market direction from text."""
    bull_signals = ["bullish", "rally", "up", "gain", "rise", "positive", "recovery", "rebound", "boom"]
    bear_signals = ["bearish", "crash", "selloff", "decline", "fall", "negative", "recession", "depression", "downturn"]

    bull_score = sum(1 for s in bull_signals if s in text)
    bear_score = sum(1 for s in bear_signals if s in text)

    if bull_score > bear_score:
        return "bullish"
    elif bear_score > bull_score:
        return "bearish"
    return "neutral"
