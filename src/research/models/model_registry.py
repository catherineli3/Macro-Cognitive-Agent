"""ModelRegistry — unified registration and dispatch for all mental models.

All models are registered here. ResearchCycle queries the registry,
not individual model classes. This ensures no hardcoded if/else.

Usage:
    registry = ModelRegistry()
    registry.register(LiquidityModel())
    ...
    conclusions = registry.evaluate_all(snapshot)
"""

from __future__ import annotations

from typing import Optional

from src.research.models.mental_model import MentalModel, ModelInput, ResearchConclusion
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ModelRegistry:
    """Central registry for all mental models.

    Responsibilities:
        1. Register models by domain.
        2. Dispatch evaluate_all() across all registered models.
        3. Provide lookup by domain name.
        4. Enable selective evaluation (single domain).

    Usage:
        registry = ModelRegistry()
        registry.register(LiquidityModel())
        registry.register(CreditModel())
        # ... register all models
        conclusions = registry.evaluate_all(snapshot)
    """

    def __init__(self) -> None:
        self._models: dict[str, MentalModel] = {}
        self._domains: list[str] = []

    # ── Registration ────────────────────────────────────────────────────────

    def register(self, model: MentalModel) -> None:
        """Register a mental model.

        Args:
            model: An instance of a MentalModel subclass.
        """
        key = model.model_name
        if key in self._models:
            logger.warning("model_registry_duplicate | model=%s (replacing)", key)
        self._models[key] = model
        if model.domain not in self._domains:
            self._domains.append(model.domain)
        logger.debug("model_registry_register | model=%s domain=%s", key, model.domain)

    def register_all(self, models: list[MentalModel]) -> None:
        """Register multiple models at once."""
        for model in models:
            self.register(model)

    # ── Evaluation ──────────────────────────────────────────────────────────

    def evaluate_all(self, snapshot: dict) -> list[ResearchConclusion]:
        """Evaluate ALL registered models against a snapshot.

        Args:
            snapshot: M1 MacroSnapshot dict.

        Returns:
            Flat list of all ResearchConclusions from all models.
        """
        input_data = ModelInput(snapshot=snapshot)
        all_conclusions: list[ResearchConclusion] = []

        for name, model in self._models.items():
            try:
                conclusions = model.evaluate(input_data)
                all_conclusions.extend(conclusions)
                logger.debug(
                    "model_evaluated | model=%s conclusions=%d",
                    name,
                    len(conclusions),
                )
            except Exception as exc:
                logger.error(
                    "model_evaluation_failed | model=%s error=%s",
                    name,
                    exc,
                )

        logger.info(
            "registry_evaluate_all_done | models=%d conclusions=%d",
            len(self._models),
            len(all_conclusions),
        )
        return all_conclusions

    def evaluate_domain(
        self, domain: str, snapshot: dict
    ) -> list[ResearchConclusion]:
        """Evaluate only models for a specific domain."""
        input_data = ModelInput(snapshot=snapshot)
        conclusions: list[ResearchConclusion] = []

        for name, model in self._models.items():
            if model.domain.lower() == domain.lower():
                try:
                    conclusions.extend(model.evaluate(input_data))
                except Exception as exc:
                    logger.error("model_eval_domain_failed | %s: %s", name, exc)

        return conclusions

    def evaluate_model(
        self, model_name: str, snapshot: dict
    ) -> Optional[list[ResearchConclusion]]:
        """Evaluate a single named model."""
        model = self._models.get(model_name)
        if model is None:
            logger.warning("model_not_found | name=%s", model_name)
            return None

        input_data = ModelInput(snapshot=snapshot)
        try:
            return model.evaluate(input_data)
        except Exception as exc:
            logger.error("model_eval_single_failed | %s: %s", model_name, exc)
            return None

    # ── Introspection ───────────────────────────────────────────────────────

    @property
    def registered_models(self) -> list[str]:
        """Return names of all registered models."""
        return sorted(self._models.keys())

    @property
    def registered_domains(self) -> list[str]:
        """Return all macro domains covered."""
        return list(self._domains)

    def get_model(self, model_name: str) -> Optional[MentalModel]:
        """Get a specific model instance by name."""
        return self._models.get(model_name)

    def __len__(self) -> int:
        return len(self._models)


# ── Global Registry Builder ─────────────────────────────────────────────────


def build_default_registry() -> ModelRegistry:
    """Build and return the default ModelRegistry with all 7 core models.

    This is the recommended entry point. It ensures all models are
    registered before any evaluation happens.

    Usage:
        registry = build_default_registry()
        conclusions = registry.evaluate_all(snapshot)
    """
    from src.research.models.ai_capex_model import AICapexModel
    from src.research.models.credit_model import CreditModel
    from src.research.models.dollar_model import DollarModel
    from src.research.models.growth_model import GrowthModel
    from src.research.models.inflation_model import InflationModel
    from src.research.models.liquidity_model import LiquidityModel
    from src.research.models.policy_model import PolicyModel

    registry = ModelRegistry()
    registry.register_all([
        LiquidityModel(),
        CreditModel(),
        InflationModel(),
        GrowthModel(),
        PolicyModel(),
        DollarModel(),
        AICapexModel(),
    ])
    return registry
