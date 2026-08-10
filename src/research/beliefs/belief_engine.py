"""BeliefEngine — converts narratives into research beliefs with Bayesian updating.

This is the core of M4. It transforms narrative intelligence (M3) into
structured, verifiable beliefs that can be tested against market data.

V3.2: Extended to accept NarrativeObject (V3.2 rich narrative) alongside
Narrative (V3.0), and integrates BeliefGraph competition awareness.

Architecture:
    Narratives[] + NarrativeObjects[] + MacroStateVector
              ↓
    TemplateMatcher → matches narratives to belief templates
              ↓
    BeliefUpdateEngine → initializes beliefs with Beta-Bayesian prior
              ↓
    BeliefGraph → auto-discovers SUPPORTS/COMPETES/CONTRADICTS/EXPLAINS
              ↓
    ResearchBelief[] → beliefs ready for prediction and validation
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Union

from src.research.beliefs.schemas import (
    BeliefDomain,
    EvidenceSource,
    ResearchBelief,
)
from src.research.beliefs.belief_update_engine import BeliefUpdateEngine
from src.research.beliefs.belief_graph import BeliefGraph
from src.research.beliefs.belief_lifecycle import BeliefLifecycleManager
from src.research.beliefs.belief_store import BeliefStore
from src.research.beliefs.template_matcher import TemplateMatcher
from src.research.narrative.schemas import Narrative, NarrativeObject
from src.research.models.mental_model import ResearchConclusion
from src.shared.logging import get_logger

logger = get_logger(__name__)


class BeliefEngine:
    """Core belief engine — narratives → beliefs → predictions.

    Usage:
        engine = BeliefEngine()

        # From narratives
        beliefs = engine.generate_from_narratives(narratives, state_vector)

        # Update with new evidence
        engine.update_belief(belief, "DXY broke 106", EvidenceSource.MARKET_DATA, "supporting")

        # Manage lifecycle
        engine.evaluate_lifecycle(beliefs)

        # Persist
        engine.save(beliefs)
    """

    def __init__(self) -> None:
        self.update_engine = BeliefUpdateEngine()
        self.template_matcher = TemplateMatcher()
        self.lifecycle = BeliefLifecycleManager()
        self.store = BeliefStore()
        self.graph = BeliefGraph()

    def generate_from_narratives(
        self,
        narratives: list[Union[Narrative, NarrativeObject]],
        state_vector: dict,
        conclusions: Optional[list[ResearchConclusion]] = None,
    ) -> list[ResearchBelief]:
        """Generate beliefs from detected narratives and macro state.

        Accepts both Narrative (V3.0) and NarrativeObject (V3.2).

        Flow:
            1. TemplateMatcher finds matching belief templates
            2. BeliefUpdateEngine initializes each belief
            3. Evidence from state vector and conclusions is attached
            4. V3.2: Evidence from NarrativeObject causal chains is attached
            5. Graph relationships are auto-discovered (V3.2 enhanced)
            6. Lifecycle evaluation considers graph competition

        Returns:
            List of initialized ResearchBelief objects.
        """
        # Separate V3.0 and V3.2 narratives
        v3_narratives = [n for n in narratives if isinstance(n, Narrative) and not isinstance(n, NarrativeObject)]
        v32_narratives = [n for n in narratives if isinstance(n, NarrativeObject)]

        # Convert V3.2 objects to V3.0 for template matching
        all_v3 = list(v3_narratives)
        for n32 in v32_narratives:
            all_v3.append(Narrative(
                id=n32.id,
                title=n32.title,
                description=n32.description,
                category=n32.category,
                score=n32.confidence,
                source_signals=n32.supporting_evidence,
            ))

        matches = self.template_matcher.match(all_v3)
        beliefs: list[ResearchBelief] = []

        for match in matches:
            # Initialize belief from template
            belief = self.update_engine.initialize_belief(
                title=match["belief_title"],
                domain=match["domain"],
                description=match["belief_description"],
            )

            # Attach source narrative info
            belief.source_narratives.append(match["source_narrative"])

            # ── V3.2: Attach narrative object data ──────────────────
            source_narrative_id = match.get("source_narrative_id", "")
            for n32 in v32_narratives:
                if n32.id == source_narrative_id or n32.title == match.get("source_narrative", ""):
                    # Add causal chain as evidence
                    for step in n32.causal_chain:
                        self.update_engine.add_evidence(
                            belief,
                            description=f"[Causal] {step}",
                            source=EvidenceSource.INFERENCE,
                            direction="supporting",
                            confidence=n32.confidence,
                            value=n32.confidence,
                        )
                    # Add supporting evidence
                    for ev in n32.supporting_evidence:
                        self.update_engine.add_evidence(
                            belief,
                            description=f"[Evidence] {ev[:120]}",
                            source=EvidenceSource.INFERENCE,
                            direction="supporting",
                            confidence=n32.source_diversity or 0.6,
                            value=0.6,
                        )
                    # Add contradicting evidence
                    for ev in n32.contradicting_evidence:
                        self.update_engine.add_evidence(
                            belief,
                            description=f"[Contradicting] {ev[:120]}",
                            source=EvidenceSource.INFERENCE,
                            direction="contradicting",
                            confidence=0.5,
                            value=-0.3,
                        )
                    # Record mental models
                    for mm in n32.mental_models_used:
                        if mm not in belief.source_models:
                            belief.source_models.append(mm)
                    # Boost confidence based on regime fit
                    belief.confidence = max(belief.confidence, n32.confidence)
                    break

            # Add evidence from state vector
            for dim_name, dim_data in state_vector.items():
                if dim_name.lower() == match["domain"].value.lower() or dim_name == match["domain"].value:
                    score = dim_data.get("score", 0.5)
                    direction = dim_data.get("direction", "neutral")

                    ev_dir = "supporting" if score > 0.5 else "contradicting"
                    self.update_engine.add_evidence(
                        belief,
                        description=f"{dim_name}: {direction} (score={score:.2f})",
                        source=EvidenceSource.MACRO_DATA,
                        direction=ev_dir,
                        confidence=dim_data.get("confidence", 0.7),
                        value=score,
                    )

                    # Add driver evidence
                    for driver in dim_data.get("drivers", []):
                        self.update_engine.add_evidence(
                            belief,
                            description=f"Driver {driver} supports {dim_name} {direction}",
                            source=EvidenceSource.MACRO_DATA,
                            direction=ev_dir,
                            value=0.5,
                        )

            # Add evidence from mental model conclusions
            if conclusions:
                for c in conclusions:
                    if c.domain.lower() == match["domain"].value.lower():
                        ev_dir = "supporting" if c.confidence >= 0.5 else "contradicting"
                        self.update_engine.add_evidence(
                            belief,
                            description=f"Model {c.model_name}: {c.conclusion[:80]}",
                            source=EvidenceSource.INFERENCE,
                            direction=ev_dir,
                            confidence=c.confidence,
                            value=c.confidence,
                        )
                        belief.source_models.append(c.model_name)

            # Set confidence from match score
            belief.confidence = max(belief.confidence, match["match_score"] * 0.9)
            belief.update_confidence()

            self.graph.add_belief(belief)
            beliefs.append(belief)

        # V3.2: Auto-discover relationships (enhanced algorithm)
        new_relations = self.graph.auto_discover_relations()

        # V3.2: Evaluate lifecycle — pass graph context for competition awareness
        for belief in beliefs:
            self.lifecycle.evaluate(belief)

        # Log competition clusters
        clusters = self.graph.find_competition_clusters()
        if clusters:
            logger.info(
                "belief_engine_generated | %d beliefs from %d narratives (%d matches) "
                "| %d new graph relations | %d competition clusters",
                len(beliefs), len(narratives), len(matches),
                new_relations, len(clusters),
            )
        else:
            logger.info(
                "belief_engine_generated | %d beliefs from %d narratives (%d matches) "
                "| %d new graph relations",
                len(beliefs), len(narratives), len(matches), new_relations,
            )
        return beliefs

    def generate_from_narrative_competition(
        self,
        competition_result,
        state_vector: dict,
        conclusions: Optional[list[ResearchConclusion]] = None,
    ) -> tuple[list[ResearchBelief], dict]:
        """V3.2: Generate beliefs from a NarrativeCompetitionResult.

        Each competing narrative produces its own belief, and the graph
        auto-discovers COMPETES relations between them.

        Args:
            competition_result: NarrativeCompetitionResult from NarrativeCompetition
            state_vector: Current macro state
            conclusions: Mental model conclusions

        Returns:
            Tuple of (beliefs, competition_graph_stats).
        """
        narrative_objects = competition_result.narratives

        # Generate beliefs from all competing narratives
        beliefs = self.generate_from_narratives(
            narratives=narrative_objects,
            state_vector=state_vector,
            conclusions=conclusions,
        )

        # Ensure competition relations exist between beliefs from competing narratives
        belief_ids = [b.id for b in beliefs]
        for i, a in enumerate(beliefs):
            for b in beliefs[i + 1:]:
                if a.domain == b.domain and a.id != b.id:
                    # Same domain from competing narratives → COMPETES
                    self.graph.add_relation(
                        a.id, b.id,
                        BeliefRelationType.COMPETES,
                        strength=0.65,
                        description=f"Competing beliefs from narrative competition",
                    )

        stats = self.graph.get_graph_stats()
        return beliefs, stats

    def update_belief(
        self,
        belief: ResearchBelief,
        description: str,
        source: EvidenceSource,
        direction: str = "supporting",
        confidence: float = 0.7,
        value: float = 0.0,
    ) -> ResearchBelief:
        """Add evidence to an existing belief and update it."""
        self.update_engine.add_evidence(
            belief, description, source, direction, confidence, value,
        )
        self.lifecycle.evaluate(belief)
        return belief

    def evaluate_lifecycle(self, beliefs: list[ResearchBelief]) -> dict:
        """Evaluate lifecycle stage for all beliefs."""
        for b in beliefs:
            self.lifecycle.evaluate(b)
        return self.lifecycle.get_stage_summary(beliefs)

    def apply_decay(self, beliefs: list[ResearchBelief], half_life_days: float = 30.0) -> None:
        """Apply time decay to all beliefs."""
        for b in beliefs:
            self.update_engine.apply_decay(b, half_life_days)

    def save(self, beliefs: list[ResearchBelief], date_str: Optional[str] = None) -> str:
        return self.store.save(beliefs, date_str)

    def load_latest(self) -> list[ResearchBelief]:
        beliefs = self.store.load_latest()
        for b in beliefs:
            self.graph.add_belief(b)
        return beliefs

    def get_domain_summary(self, beliefs: list[ResearchBelief]) -> dict:
        """Summarize beliefs by domain."""
        summary = {}
        for domain in BeliefDomain:
            domain_beliefs = [b for b in beliefs if b.domain == domain]
            if domain_beliefs:
                summary[domain.value] = {
                    "count": len(domain_beliefs),
                    "active": sum(1 for b in domain_beliefs if b.is_active),
                    "avg_confidence": round(
                        sum(b.confidence for b in domain_beliefs) / len(domain_beliefs), 3
                    ),
                    "titles": [b.title for b in domain_beliefs],
                }
        return summary
