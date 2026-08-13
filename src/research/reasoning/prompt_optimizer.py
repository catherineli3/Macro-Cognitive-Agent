"""PromptOptimizer — Improve reasoning prompts based on feedback.

Quality: Prompts are the interface to LLM reasoning. Better prompts = better
research quality. This module adjusts prompts based on prediction accuracy
feedback from the ReasoningFeedback system.

Mechanism:
    1. Track which prompt patterns lead to correct vs wrong predictions
    2. Store successful prompt patterns
    3. When an error pattern recurs, suggest prompt adjustments
    4. A/B test prompt variants on historical data
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class PromptVariant:
    """A prompt variant with performance metrics."""

    variant_id: str = ""
    module_name: str = ""  # Which module this prompt is for
    prompt_text: str = ""
    version: int = 1

    # Performance
    times_used: int = 0
    times_correct: int = 0
    accuracy: float = 0.0

    # Scope
    applicable_scenarios: list[str] = field(default_factory=list)
    # e.g., ["regime_stable_growth", "regime_tightening"]

    # Feedback
    last_used: str = ""
    notes: str = ""


@dataclass
class PromptOptimizationReport:
    """Report of prompt optimization actions."""

    report_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    variant_changes: list[dict] = field(default_factory=list)
    # [{module, old_prompt_summary, new_prompt_summary, reason}]

    recommendations: list[str] = field(default_factory=list)
    bottom_line: str = ""


class PromptOptimizer:
    """Optimize reasoning prompts based on prediction feedback.

    Learning: Track what works, improve what doesn't.
    """

    def __init__(self):
        self.variants: dict[str, PromptVariant] = {}
        self._init_default_prompts()

    def evaluate_and_optimize(
        self, feedback_entries: list, module_name: str = "macro_reasoner"
    ) -> PromptOptimizationReport:
        """Evaluate recent performance and suggest prompt adjustments.

        Args:
            feedback_entries: List of FeedbackEntry from ReasoningFeedback
            module_name: Which module to optimize prompts for

        Returns:
            PromptOptimizationReport with suggested changes
        """
        report = PromptOptimizationReport(report_id=f"POP_{str(uuid.uuid4())[:8]}")
        changes = []
        recommendations = []

        if not feedback_entries:
            report.recommendations = ["No feedback data available — prompts unchanged"]
            report.bottom_line = "No action taken"
            return report

        # 1. Compute error rates by error source
        total = len(feedback_entries)
        errors = [f for f in feedback_entries if not f.was_correct]
        error_rate = len(errors) / total if total > 0 else 0.0

        # 2. Causal logic errors → adjust reasoning prompt
        causal_errors = [f for f in errors if f.error_source == "causal_logic"]
        if causal_errors:
            key = f"{module_name}_causal"
            self._update_variant(key, accuracy=1 - (len(causal_errors) / total))
            changes.append(
                {
                    "module": module_name,
                    "improvement": "Strengthen causal chain requirements in reasoning prompt",
                    "reason": f"{len(causal_errors)} causal logic errors detected",
                }
            )
            recommendations.append(
                "Add explicit causal chain verification step: "
                "'Before concluding, verify: (1) Is each link testable? "
                "(2) Are alternative causal paths considered? "
                "(3) What is the single biggest assumption?'"
            )

        # 3. Confidence calibration errors → adjust confidence guidance
        conf_errors = [f for f in errors if f.error_source == "confidence_calibration"]
        if conf_errors:
            changes.append(
                {
                    "module": module_name,
                    "improvement": "Add confidence calibration guardrails to prompt",
                    "reason": f"{len(conf_errors)} overconfidence errors detected",
                }
            )
            recommendations.append(
                "Add confidence scaffolding: 'For each hypothesis, state: "
                "(1) What would make you more confident? "
                "(2) What would make you less confident? "
                "(3) At what confidence threshold would you NOT act?'"
            )

        # 4. Data quality errors → tighten evidence requirements
        data_errors = [f for f in errors if f.error_source == "data_quality"]
        if data_errors:
            changes.append(
                {
                    "module": module_name,
                    "improvement": "Increase minimum evidence requirements in prompt",
                    "reason": f"{len(data_errors)} insufficient-evidence predictions failed",
                }
            )
            recommendations.append(
                "Require minimum 3 independent evidence sources before making "
                "directional predictions. Flag predictions with <3 sources as 'speculative'."
            )

        # 5. Overall accuracy
        correct = total - len(errors)
        if error_rate > 0.5:
            recommendations.append(
                f"CRITICAL: Accuracy {correct}/{total} ({1-error_rate:.0%}) — "
                "consider fundamentally restructuring reasoning prompts. "
                "The current framework may have systemic errors."
            )

        # 6. Update variant accuracy
        for f_entry in feedback_entries:
            pred = f_entry.prediction
            scenario = pred.get("scenario", pred.get("domain", "general"))
            key = f"{module_name}_{scenario}"
            self._update_variant(key, accuracy=1.0 if f_entry.was_correct else 0.0)

        report.variant_changes = changes
        report.recommendations = recommendations
        report.bottom_line = (
            f"{len(changes)} prompt adjustments recommended based on "
            f"{total} predictions ({correct} correct, {1-error_rate:.0%} accuracy)"
        )

        return report

    def get_best_prompt_variant(
        self, module_name: str, scenario: str = "general"
    ) -> PromptVariant | None:
        """Get the best-performing prompt variant for a module/scenario.

        Returns the variant with highest accuracy, falling back to default.
        """
        key = f"{module_name}_{scenario}"
        return self.variants.get(key, self.variants.get(f"{module_name}_default"))

    def record_prediction(self, module_name: str, variant_id: str, was_correct: bool):
        """Record a single prediction outcome against a prompt variant."""
        if variant_id in self.variants:
            v = self.variants[variant_id]
            v.times_used += 1
            if was_correct:
                v.times_correct += 1
            v.accuracy = v.times_correct / v.times_used if v.times_used > 0 else 0.0

    # ── Internal ──

    def _init_default_prompts(self):
        """Initialize default prompt variants."""
        defaults = {
            "macro_reasoner_default": {
                "module": "macro_reasoner",
                "text": "Analyze the macro evidence and produce a research memo with causal reasoning. "
                "For each conclusion, cite specific evidence. For each hypothesis, provide "
                "a counter-argument. Calibrate confidence based on evidence strength.",
            },
            "hypothesis_builder_default": {
                "module": "hypothesis_builder",
                "text": "Build causal hypotheses from evidence clusters. Each hypothesis must have: "
                "(1) A clear causal chain, (2) Named assumptions, (3) Falsification conditions. "
                "Distinguish structural from cyclical factors.",
            },
            "counter_argument_default": {
                "module": "counter_argument_generator",
                "text": "Generate counter-arguments for each hypothesis. Ask: "
                '"What could make this wrong? What is the market missing? '
                'What historical precedent contradicts this view?"',
            },
        }

        for key, config in defaults.items():
            self.variants[key] = PromptVariant(
                variant_id=f"PV_{str(uuid.uuid4())[:8]}",
                module_name=config["module"],
                prompt_text=config["text"],
                version=1,
                applicable_scenarios=["general"],
            )

    def _update_variant(self, key: str, accuracy: float):
        """Track variant accuracy."""
        if key not in self.variants:
            parts = key.rsplit("_", 1)
            module = parts[0] if parts else "macro_reasoner"
            scenario = parts[1] if len(parts) > 1 else "general"

            self.variants[key] = PromptVariant(
                variant_id=f"PV_{str(uuid.uuid4())[:8]}",
                module_name=module,
                prompt_text=f"Optimized prompt for {module} in scenario: {scenario}",
                version=1,
            )

        v = self.variants[key]
        v.times_used += 1
        if accuracy > 0.5:
            v.times_correct += 1
        v.accuracy = v.times_correct / v.times_used if v.times_used > 0 else 0.0
        v.last_used = datetime.now(UTC).isoformat()
