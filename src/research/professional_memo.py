"""V7.4 Professional Memo — Sell-side quality research reports.

Must reach sell-side macro strategy quality:
    - Fixed professional structure (10 sections)
    - Minimum 2500 words
    - Evidence-based with data citations
    - Competing hypotheses considered
    - Clear predictions with invalidation conditions
    - Trade implications with risk management

Structure:
    Executive Summary → Macro Dashboard → Current Narrative →
    Supporting Evidence → Counter Arguments → Historical Analogies →
    Predictions → Trade Implications → Risk → Invalidation Conditions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


@dataclass
class ProfessionalMemo:
    """A professional-grade macro research memo."""
    memo_id: str = field(default_factory=lambda: uuid4().hex[:12])
    
    # Header
    title: str = ""
    author: str = "Macro Research Agent"
    date: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d'))
    classification: str = "INTERNAL — FOR PROFESSIONAL USE ONLY"
    
    # ── Section 1: Executive Summary ─────────────────────────────────────
    executive_summary: str = ""
    
    # ── Section 2: Macro Dashboard ───────────────────────────────────────
    macro_dashboard: dict = field(default_factory=dict)
    # {indicator: {value, trend, implication}}
    
    # ── Section 3: Current Narrative ─────────────────────────────────────
    current_narrative: str = ""
    competing_narratives: list[str] = field(default_factory=list)
    
    # ── Section 4: Supporting Evidence ───────────────────────────────────
    supporting_evidence: list[dict] = field(default_factory=list)
    # [{claim, evidence_type, source, strength, data_points}]
    
    # ── Section 5: Counter Arguments ─────────────────────────────────────
    counter_arguments: list[dict] = field(default_factory=list)
    # [{argument, probability, impact_if_true, mitigating_factors}]
    
    # ── Section 6: Historical Analogies ──────────────────────────────────
    historical_analogies: list[dict] = field(default_factory=list)
    # [{period, description, similarity_score, key_differences, lessons}]
    
    # ── Section 7: Predictions ───────────────────────────────────────────
    predictions: list[dict] = field(default_factory=list)
    # [{prediction, probability, time_horizon, confidence_interval, invalidation}]
    
    # ── Section 8: Trade Implications ────────────────────────────────────
    trade_implications: list[dict] = field(default_factory=list)
    # [{asset, direction, conviction, rationale, sizing_guidance, stop_loss_trigger}]
    
    # ── Section 9: Risk Assessment ───────────────────────────────────────
    risks: list[dict] = field(default_factory=list)
    # [{risk, probability, impact, mitigant, monitoring_metric}]
    
    # ── Section 10: Invalidation Conditions ──────────────────────────────
    invalidation_conditions: list[dict] = field(default_factory=list)
    # [{condition, threshold, current_value, if_triggered_implication}]
    
    # Meta
    word_count: int = 0
    qa_score: Optional[float] = None
    qa_grade: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Sources
    data_sources: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    
    def render(self) -> str:
        """Render the full professional memo in Markdown."""
        sections = [
            self._render_header(),
            self._render_executive_summary(),
            self._render_macro_dashboard(),
            self._render_current_narrative(),
            self._render_supporting_evidence(),
            self._render_counter_arguments(),
            self._render_historical_analogies(),
            self._render_predictions(),
            self._render_trade_implications(),
            self._render_risks(),
            self._render_invalidation(),
            self._render_disclaimer(),
        ]
        
        content = "\n\n".join(sections)
        self.word_count = len(content.split())
        return content
    
    # ── Section Renderers ─────────────────────────────────────────────────

    def _render_header(self) -> str:
        return f"""---
title: "{self.title}"
date: "{self.date}"
author: "{self.author}"
classification: "{self.classification}"
---

# {self.title}

**{self.date}** | {self.author}

"""

    def _render_executive_summary(self) -> str:
        if not self.executive_summary:
            return "## Executive Summary\n\n*Analysis pending.*"
        return f"""## 1. Executive Summary

{self.executive_summary}
"""

    def _render_macro_dashboard(self) -> str:
        lines = ["## 2. Macro Dashboard", "", "| Indicator | Value | Trend | Implication |",
                 "|-----------|-------|-------|-------------|"]
        
        if self.macro_dashboard:
            for indicator, data in list(self.macro_dashboard.items())[:10]:
                value = data.get("value", "—") if isinstance(data, dict) else str(data)
                trend = data.get("trend", "—") if isinstance(data, dict) else ""
                implication = data.get("implication", "") if isinstance(data, dict) else ""
                
                trend_icon = {"up": "↑", "down": "↓", "flat": "→"}.get(trend, trend)
                lines.append(f"| {indicator} | {value} | {trend_icon} | {implication} |")
        else:
            lines.append("| — | — | — | Awaiting data |")
        
        return "\n".join(lines)

    def _render_current_narrative(self) -> str:
        lines = ["## 3. Current Macro Narrative", ""]
        
        if self.current_narrative:
            lines.append(self.current_narrative)
        else:
            lines.append("*Narrative analysis pending.*")
        
        if self.competing_narratives:
            lines.append("\n### Competing Narratives")
            for i, cn in enumerate(self.competing_narratives[:3]):
                lines.append(f"{i+1}. {cn}")
        
        return "\n".join(lines)

    def _render_supporting_evidence(self) -> str:
        lines = ["## 4. Supporting Evidence", ""]
        
        if self.supporting_evidence:
            for i, ev in enumerate(self.supporting_evidence[:8]):
                claim = ev.get("claim", f"Evidence item {i+1}")
                evidence_type = ev.get("evidence_type", "General")
                source = ev.get("source", "")
                strength = ev.get("strength", "Medium")
                
                lines.append(f"### Evidence {i+1}: {claim}")
                lines.append(f"- **Type**: {evidence_type}")
                lines.append(f"- **Source**: {source}")
                lines.append(f"- **Strength**: {strength}")
                
                data_points = ev.get("data_points", [])
                if data_points:
                    lines.append("- **Key Data Points**:")
                    for dp in data_points:
                        lines.append(f"  - {dp}")
                lines.append("")
        else:
            lines.append("*Evidence gathering in progress.*")
        
        return "\n".join(lines)

    def _render_counter_arguments(self) -> str:
        lines = ["## 5. Counter Arguments", ""]
        
        if self.counter_arguments:
            for i, ca in enumerate(self.counter_arguments[:5]):
                argument = ca.get("argument", f"Counter {i+1}")
                probability = ca.get("probability", 0.3)
                impact = ca.get("impact_if_true", "Unknown")
                
                lines.append(f"### Counter {i+1}")
                lines.append(f"**Argument**: {argument}")
                lines.append(f"- **Probability**: {probability:.0%}")
                lines.append(f"- **Impact if True**: {impact}")
                
                mitigants = ca.get("mitigating_factors", [])
                if mitigants:
                    lines.append(f"- **Mitigating Factors**: {', '.join(mitigants)}")
                lines.append("")
        else:
            lines.append("*Counter-argument analysis pending.*")
        
        return "\n".join(lines)

    def _render_historical_analogies(self) -> str:
        lines = ["## 6. Historical Analogies", ""]
        
        if self.historical_analogies:
            for i, ha in enumerate(self.historical_analogies[:4]):
                period = ha.get("period", "Unknown")
                description = ha.get("description", "")
                similarity = ha.get("similarity_score", 0.5)
                differences = ha.get("key_differences", [])
                lessons = ha.get("lessons", [])
                
                lines.append(f"### {period}")
                lines.append(f"- **Description**: {description}")
                lines.append(f"- **Similarity Score**: {similarity:.0%}")
                
                if differences:
                    lines.append(f"- **Key Differences**: {', '.join(differences)}")
                if lessons:
                    lines.append(f"- **Lessons**: {', '.join(lessons)}")
                lines.append("")
        else:
            lines.append("*Historical analogy analysis pending.*")
        
        return "\n".join(lines)

    def _render_predictions(self) -> str:
        lines = ["## 7. Predictions", ""]
        
        if self.predictions:
            lines.append("| # | Prediction | Probability | Time Horizon | Invalidation |")
            lines.append("|---|------------|-------------|--------------|-------------|")
            for i, p in enumerate(self.predictions[:8]):
                pred = p.get("prediction", "")
                prob = p.get("probability", 0.5)
                horizon = p.get("time_horizon", "")
                invalidation = p.get("invalidation", "")
                lines.append(f"| {i+1} | {pred[:80]} | {prob:.0%} | {horizon} | {invalidation[:60]} |")
        else:
            lines.append("*Predictions pending.*")
        
        return "\n".join(lines)

    def _render_trade_implications(self) -> str:
        lines = ["## 8. Trade Implications", ""]
        
        if self.trade_implications:
            lines.append("| Asset | Direction | Conviction | Rationale |")
            lines.append("|-------|-----------|------------|-----------|")
            for ti in self.trade_implications[:6]:
                asset = ti.get("asset", "")
                direction = ti.get("direction", "neutral")
                conviction = ti.get("conviction", "medium")
                rationale = ti.get("rationale", "")
                
                dir_icon = {"long": "🟢 Long", "short": "🔴 Short", "neutral": "⚪ Neutral"}.get(direction, direction)
                lines.append(f"| {asset} | {dir_icon} | {conviction} | {rationale[:80]} |")
        else:
            lines.append("*Trade implications pending.*")
        
        return "\n".join(lines)

    def _render_risks(self) -> str:
        lines = ["## 9. Risk Assessment", ""]
        
        if self.risks:
            lines.append("| Risk | Probability | Impact | Monitoring Metric |")
            lines.append("|------|-------------|--------|------------------|")
            for r in self.risks[:8]:
                risk = r.get("risk", "")
                prob = r.get("probability", 0.2)
                impact = r.get("impact", "medium")
                metric = r.get("monitoring_metric", "")
                lines.append(f"| {risk} | {prob:.0%} | {impact} | {metric} |")
        else:
            lines.append("*Risk assessment pending.*")
        
        return "\n".join(lines)

    def _render_invalidation(self) -> str:
        lines = ["## 10. Invalidation Conditions", ""]
        lines.append("The thesis becomes invalid if any of the following conditions are met:")
        lines.append("")
        
        if self.invalidation_conditions:
            lines.append("| Condition | Threshold | Current | If Triggered |")
            lines.append("|-----------|-----------|---------|-------------|")
            for ic in self.invalidation_conditions[:6]:
                condition = ic.get("condition", "")
                threshold = ic.get("threshold", "")
                current = ic.get("current_value", "—")
                implication = ic.get("if_triggered_implication", "")
                lines.append(f"| {condition} | {threshold} | {current} | {implication} |")
        else:
            lines.append("*Invalidation conditions pending.*")
        
        return "\n".join(lines)

    def _render_disclaimer(self) -> str:
        return """---

**Disclaimer**: This memo is generated by an automated macro research agent for 
analytical purposes. It does not constitute investment advice. All predictions 
are probabilistic and subject to revision as new information becomes available.

**Sources**: """ + (", ".join(self.data_sources[:5]) if self.data_sources else "Automated research pipeline") + """

**QA Grade**: """ + (f"{self.qa_grade} ({self.qa_score:.0f}/100)" if self.qa_score else "Not graded")


class ProfessionalMemoBuilder:
    """Build professional-grade research memos programmatically.

    Usage:
        builder = ProfessionalMemoBuilder()
        memo = (builder
            .title("Fed Policy Path: H2 2026 Outlook")
            .executive_summary("...")
            .add_prediction("Fed cuts 50bp by December", probability=0.65)
            .add_risk("Sticky inflation delays cuts", probability=0.25)
            .build())
        markdown = memo.render()
    """

    def __init__(self):
        self._memo = ProfessionalMemo()

    def title(self, title: str) -> "ProfessionalMemoBuilder":
        self._memo.title = title
        return self

    def executive_summary(self, summary: str) -> "ProfessionalMemoBuilder":
        self._memo.executive_summary = summary
        return self

    def macro_dashboard(self, dashboard: dict) -> "ProfessionalMemoBuilder":
        self._memo.macro_dashboard = dashboard
        return self

    def current_narrative(self, narrative: str, 
                          competing: Optional[list[str]] = None) -> "ProfessionalMemoBuilder":
        self._memo.current_narrative = narrative
        if competing:
            self._memo.competing_narratives = competing
        return self

    def add_evidence(self, claim: str, evidence_type: str = "",
                     source: str = "", strength: str = "Medium",
                     data_points: Optional[list[str]] = None) -> "ProfessionalMemoBuilder":
        self._memo.supporting_evidence.append({
            "claim": claim,
            "evidence_type": evidence_type,
            "source": source,
            "strength": strength,
            "data_points": data_points or [],
        })
        return self

    def add_counter(self, argument: str, probability: float = 0.3,
                    impact: str = "", mitigants: Optional[list[str]] = None) -> "ProfessionalMemoBuilder":
        self._memo.counter_arguments.append({
            "argument": argument,
            "probability": probability,
            "impact_if_true": impact,
            "mitigating_factors": mitigants or [],
        })
        return self

    def add_analogy(self, period: str, description: str,
                    similarity: float = 0.5,
                    differences: Optional[list[str]] = None,
                    lessons: Optional[list[str]] = None) -> "ProfessionalMemoBuilder":
        self._memo.historical_analogies.append({
            "period": period,
            "description": description,
            "similarity_score": similarity,
            "key_differences": differences or [],
            "lessons": lessons or [],
        })
        return self

    def add_prediction(self, prediction: str, probability: float = 0.5,
                       time_horizon: str = "", invalidation: str = "") -> "ProfessionalMemoBuilder":
        self._memo.predictions.append({
            "prediction": prediction,
            "probability": probability,
            "time_horizon": time_horizon,
            "invalidation": invalidation,
        })
        return self

    def add_trade(self, asset: str, direction: str = "neutral",
                  conviction: str = "medium", rationale: str = "") -> "ProfessionalMemoBuilder":
        self._memo.trade_implications.append({
            "asset": asset,
            "direction": direction,
            "conviction": conviction,
            "rationale": rationale,
        })
        return self

    def add_risk(self, risk: str, probability: float = 0.2,
                 impact: str = "medium", monitoring: str = "") -> "ProfessionalMemoBuilder":
        self._memo.risks.append({
            "risk": risk,
            "probability": probability,
            "impact": impact,
            "monitoring_metric": monitoring,
        })
        return self

    def add_invalidation(self, condition: str, threshold: str = "",
                         current: str = "", implication: str = "") -> "ProfessionalMemoBuilder":
        self._memo.invalidation_conditions.append({
            "condition": condition,
            "threshold": threshold,
            "current_value": current,
            "if_triggered_implication": implication,
        })
        return self

    def set_sources(self, sources: list[str]) -> "ProfessionalMemoBuilder":
        self._memo.data_sources = sources
        return self

    def build(self) -> ProfessionalMemo:
        """Finalize and return the memo."""
        # Auto-calculate word count
        rendered = self._memo.render()
        self._memo.word_count = len(rendered.split())
        return self._memo

    @staticmethod
    def from_data(topic: str, macro: dict, market: dict,
                  beliefs: dict, narratives: dict,
                  evidence: list[str], predictions: list[dict]) -> ProfessionalMemo:
        """Quick-build a memo from structured research data."""
        builder = ProfessionalMemoBuilder()
        
        builder.title(f"Macro Research: {topic}")
        
        # Executive summary
        summary_parts = [
            f"This memo analyzes the current macro environment with focus on {topic}.",
            f"Key indicators monitored: {', '.join(list(macro.keys())[:5])}.",
            f"Narrative framework: {', '.join(list(narratives.keys())[:3]) if isinstance(narratives, dict) else 'evolving'}.",
        ]
        builder.executive_summary("\n\n".join(summary_parts))
        
        # Macro dashboard
        builder.macro_dashboard(macro)
        
        # Evidence
        for e in evidence[:5]:
            builder.add_evidence(e, evidence_type="macro_data")
        
        # Predictions
        for p in predictions[:5]:
            if isinstance(p, dict):
                builder.add_prediction(
                    prediction=p.get("prediction", p.get("text", "")),
                    probability=p.get("probability", 0.5),
                    time_horizon=p.get("time_horizon", ""),
                    invalidation=p.get("invalidation", ""),
                )
        
        return builder.build()
