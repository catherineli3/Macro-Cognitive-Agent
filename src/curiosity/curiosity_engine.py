"""CuriosityEngine — generates research questions from uncertainty.

Top researchers don't just analyze data — they identify what they don't know
that could change their thesis, then go research it.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from src.curiosity.schemas import CuriosityReport, ResearchQuestion, UncertaintyNode

DOMAIN_IMPORTANCE = {
    "liquidity": 0.9,
    "credit": 0.85,
    "inflation": 0.8,
    "growth": 0.85,
    "fiscal": 0.7,
    "dollar": 0.75,
    "volatility": 0.65,
    "geopolitical": 0.7,
    "housing": 0.6,
    "labor": 0.65,
    "tech_capex": 0.7,
    "commodities": 0.6,
}

QUESTION_TEMPLATES = {
    "liquidity": "What is the current state of {} and how likely is it to change in the next 3 months?",
    "credit": "Are {} conditions improving or deteriorating, and what are the lead indicators?",
    "inflation": "Will {} remain the dominant macro driver, or is a regime shift underway?",
    "growth": "Is {} sustainable at current levels, and what are the key risks?",
    "dollar": "How will {} impact global liquidity conditions and EM assets?",
    "fiscal": "What is the trajectory of {} and its implications for rates and growth?",
    "tech_capex": "Is {} investment converting into measurable revenue and productivity?",
}

DOMAIN_DATA = {
    "liquidity": ["SOFR volumes", "Reverse repo usage", "Bank reserve data"],
    "credit": ["HY OAS", "IG OAS", "Loan officer survey", "Delinquency rates"],
    "inflation": ["CPI components", "PCE", "Wage growth", "Inflation swaps"],
    "growth": ["PMI", "ISM", "GDPNow", "Retail sales"],
    "dollar": ["DXY", "CFTC positioning", "TIC data", "Central bank reserves"],
    "tech_capex": ["Hyperscaler capex", "Semiconductor shipments", "Cloud revenue"],
    "fiscal": ["CBO projections", "Deficit trajectory", "Auction demand"],
}


class CuriosityEngine:
    """Generates research questions from belief uncertainty."""

    def generate_questions(
        self,
        beliefs: list[Any],
        mental_models: dict | None = None,
        learning_report: dict | None = None,
        date: str | None = None,
    ) -> CuriosityReport:
        if date is None:
            date = datetime.now(UTC).strftime("%Y-%m-%d")

        nodes = self._build_uncertainty_map(beliefs, learning_report)
        nodes.sort(key=lambda n: n.curiosity_score, reverse=True)
        top = nodes[:10]

        questions = []
        for node in top[:8]:
            q = self._generate_question(node, date)
            questions.append(q)
        questions.sort(key=lambda q: q.priority, reverse=True)

        most_important = top[0].topic if top else "No clear unknown"
        agenda = [
            f"#{i+1} [{q.domain.upper()}] {q.question} (P:{q.priority:.0%})"
            for i, q in enumerate(questions[:5])
        ]

        return CuriosityReport(
            report_id=f"cur_{date}",
            date=date,
            uncertainty_nodes=nodes,
            top_unknowns=top,
            research_questions=questions,
            priority_questions=questions[:5],
            most_important_unknown=most_important,
            recommended_research_agenda=agenda,
        )

    def _build_uncertainty_map(
        self, beliefs: list[Any], learning_report: dict | None
    ) -> list[UncertaintyNode]:
        nodes = []
        for belief in beliefs:
            title = getattr(belief, "title", "Unknown")
            domain_raw = getattr(belief, "domain", "")
            domain = domain_raw.value if hasattr(domain_raw, "value") else str(domain_raw)
            confidence = float(getattr(belief, "confidence", 0.5) or 0.5)
            evidence = int(getattr(belief, "evidence_count", 0) or 0)
            importance = DOMAIN_IMPORTANCE.get(domain, 0.5)
            uncertainty = (1.0 - confidence) * 0.7 + max(0, 1.0 - evidence / 10.0) * 0.3
            curiosity = importance * uncertainty
            unknown = self._identify_aspects(belief, confidence, evidence, domain)
            bid = getattr(belief, "belief_id", "") or getattr(belief, "id", "")
            content = getattr(belief, "content", "") or getattr(belief, "description", "")

            nodes.append(
                UncertaintyNode(
                    topic=title,
                    domain=domain,
                    current_confidence=round(confidence, 2),
                    importance=importance,
                    uncertainty=round(uncertainty, 2),
                    curiosity_score=round(curiosity, 3),
                    related_beliefs=[bid],
                    existing_knowledge=content,
                    unknown_aspects=unknown,
                )
            )
        return nodes

    def _identify_aspects(
        self, belief: Any, confidence: float, evidence: int, domain: str
    ) -> list[str]:
        aspects = []
        if confidence < 0.5:
            aspects.append(f"Directional conviction low ({confidence:.0%})")
        if evidence < 3:
            aspects.append(f"Only {evidence} pieces of evidence")
        if confidence > 0.8 and evidence < 5:
            aspects.append("High confidence, limited evidence — potential overconfidence")
        domain_unknowns = {
            "credit": ["Private credit stress", "Rating migration"],
            "liquidity": ["Hidden leverage", "Funding stress"],
            "inflation": ["Services stickiness", "Wage-price spiral"],
            "growth": ["Productivity trend", "Fiscal impulse"],
            "dollar": ["Reserve diversification", "Petrodollar evolution"],
        }
        for key, items in domain_unknowns.items():
            if key == domain:
                aspects.extend(items)
        return aspects[:4]

    def _generate_question(self, node: UncertaintyNode, date: str) -> ResearchQuestion:
        template = QUESTION_TEMPLATES.get(
            node.domain, "What don't we understand about {} that matters for our thesis?"
        )
        question = template.format(node.topic.lower())
        q_id = hashlib.md5(f"{question}{date}".encode()).hexdigest()[:12]

        if node.current_confidence > 0.7:
            flip = f"If {node.topic} shows 2-3 months of counter-trend data"
        elif node.current_confidence > 0.4:
            flip = f"If a clear directional trend in {node.topic} emerges"
        else:
            flip = f"If any signal emerges in {node.topic}"

        return ResearchQuestion(
            question_id=q_id,
            question=question,
            domain=node.domain,
            priority=round(node.curiosity_score, 2),
            hypothesis=f"Current view: {node.topic} — confidence {node.current_confidence:.0%}",
            what_would_change_mind=flip,
            data_needed=DOMAIN_DATA.get(node.domain, ["Market data", "Economic data"]),
            status="open",
            generated_at=datetime.now(UTC).isoformat(),
        )

    def resolve_question(
        self, question: ResearchQuestion, findings: str, confidence_change: float
    ) -> ResearchQuestion:
        question.status = "answered"
        return question
