"""RuleBasedPlanner — Deterministic, keyword-driven plan decomposition.

Sprint 3 implements rule-based planning only (no LLM). The planner:
    1. Loads planning rule templates from planning_rules.yaml
    2. Matches user goal keywords against trigger_keywords
    3. Merges matching templates (union of tasks, union of dependencies)
    4. Deduplicates by task ID
    5. Returns a validated ExecutionPlan

The Planner is domain-agnostic:
    - It does NOT know about specific indicators (DXY, US10Y, etc.)
    - It generates ABSTRACT tasks with generic Agent types
    - It does NOT execute, call tools, or reason

Future (Sprint 4+):
    - LLMPlanner replaces keyword matching with LLM-driven decomposition
    - Same PlannerInterface, zero downstream changes
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import BaseModel

from src.interfaces.planner import PlannerInterface
from src.schemas.planning import ExecutionPlan, Task
from src.shared.config import load_yaml
from src.shared.exceptions import PlanCreationError
from src.shared.logging import get_logger

logger = get_logger(__name__)


class _RuleTaskDef(BaseModel):
    """Internal: parsed task definition from YAML."""

    id: str
    name: str
    description: str = ""
    type: str  # Will be validated against TaskType
    priority: int = 1
    dependencies: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)  # Sprint 4: capability routing


class _PlanningRule(BaseModel):
    """Internal: parsed planning rule from YAML."""

    rule_id: str
    description: str = ""
    trigger_keywords: list[str] = field(default_factory=list)
    tasks: list[_RuleTaskDef] = field(default_factory=list)


@dataclass
class _RuleMatch:
    """Internal: a rule that matched the user goal, with weighted score."""

    rule: _PlanningRule
    score: int  # Number of matched keywords


class RuleBasedPlanner(PlannerInterface):
    """Deterministic planner: goal keywords → rule templates → ExecutionPlan.

    Implements PlannerInterface. Stateless, thread-safe, pure — no external
    dependencies beyond the rules config file.

    Usage:
        planner = RuleBasedPlanner()
        plan = await planner.create_plan("Analyze global liquidity")
    """

    # Default rules config filename
    DEFAULT_RULES_FILE = "planning_rules.yaml"

    def __init__(self, rules_file: str | None = None) -> None:
        """Initialize the planner by loading rule templates.

        Args:
            rules_file: Filename in configs/ directory.
                        Default: planning_rules.yaml.
        """
        self._rules_file = rules_file or self.DEFAULT_RULES_FILE
        self._rules: list[_PlanningRule] = self._load_rules()
        logger.info(
            "RuleBasedPlanner initialized",
            extra={
                "rules_file": self._rules_file,
                "rule_count": len(self._rules),
            },
        )

    # ── PlannerInterface ──────────────────────────────────────────────

    async def create_plan(self, goal: str) -> ExecutionPlan:
        """Decompose a user goal into a structured ExecutionPlan.

        Pipeline:
            goal → keyword matching → rule template merging →
            task dedup → plan construction → validation

        Args:
            goal: Natural language user goal.

        Returns:
            A validated, immutable ExecutionPlan.

        Raises:
            PlanCreationError: If no rules match the goal.
        """
        goal_lower = goal.lower().strip()
        if not goal_lower:
            raise PlanCreationError(
                "Cannot create plan for empty goal",
                details={"goal": goal},
            )

        # Step 1: Match rules against goal keywords
        matches = self._match_rules(goal_lower)

        if not matches:
            raise PlanCreationError(
                f"No planning rules match goal: '{goal[:80]}'",
                details={
                    "goal": goal,
                    "available_rules": [r.rule_id for r in self._rules],
                },
            )

        # Step 2: Merge tasks from all matched rules (union, dedup by ID)
        merged_tasks = self._merge_tasks(matches)
        merged_explanations = self._merge_explanations(matches)

        # Step 3: Convert to domain Task objects
        from src.planning.validator import PlanValidator

        tasks = [
            Task(
                id=t.id,
                name=t.name,
                description=t.description,
                type=t.type,  # type: ignore[arg-type]  # Validated below
                priority=t.priority,
                dependencies=list(set(t.dependencies)),  # Dedup dependencies
                config=t.config or {},  # Sprint 4: capability routing
            )
            for t in merged_tasks
        ]

        # Step 4: Build the plan
        plan = ExecutionPlan(
            goal=goal,
            tasks=tasks,
            plan_explanation=merged_explanations,
        )

        # Step 5: Validate
        try:
            PlanValidator.validate(plan)
        except Exception as exc:
            raise PlanCreationError(
                f"Generated plan failed validation: {exc}",
                details={
                    "goal": goal,
                    "matched_rules": [m.rule.rule_id for m in matches],
                    "validation_error": str(exc),
                },
            ) from exc

        logger.info(
            "Plan created",
            extra={
                "plan_id": plan.plan_id,
                "goal": goal[:80],
                "task_count": plan.task_count,
                "matched_rules": [m.rule.rule_id for m in matches],
            },
        )
        return plan

    def source_name(self) -> str:
        """Human-readable planner name for logging & audit."""
        return f"RuleBasedPlanner(rules={self._rules_file}, templates={len(self._rules)})"

    # ── Internal ──────────────────────────────────────────────────────

    def _load_rules(self) -> list[_PlanningRule]:
        """Load and parse planning rules from YAML config."""
        raw = load_yaml(self._rules_file)
        rules_data = raw.get("rules", [])
        if not rules_data:
            raise PlanCreationError(
                f"No rules defined in {self._rules_file}",
                details={"file": self._rules_file},
            )

        rules: list[_PlanningRule] = []
        for i, rule_data in enumerate(rules_data):
            try:
                rules.append(_PlanningRule(**rule_data))
            except Exception as exc:
                logger.error(
                    f"Skipping invalid rule at index {i}: {exc}",
                    extra={"rule_index": i, "rule_data": str(rule_data)[:200]},
                )
        return rules

    def _match_rules(self, goal_lower: str) -> list[_RuleMatch]:
        """Find all rules whose trigger_keywords appear in the goal.

        Scoring: count of matched keywords (for tie-breaking, future use).
        The __default__ rule always matches if no other rules do.
        """
        matches: list[_RuleMatch] = []

        for rule in self._rules:
            keywords = rule.trigger_keywords

            # __default__ is a fallback — skip it during normal matching
            if "__default__" in keywords:
                continue

            matched_keywords = [kw for kw in keywords if re.search(re.escape(kw), goal_lower)]

            if matched_keywords:
                matches.append(_RuleMatch(rule=rule, score=len(matched_keywords)))

        # If nothing matched, activate the default rule(s)
        if not matches:
            for rule in self._rules:
                if "__default__" in rule.trigger_keywords:
                    matches.append(_RuleMatch(rule=rule, score=0))
                    break

        # Sort by score descending (more keyword matches = more relevant)
        matches.sort(key=lambda m: m.score, reverse=True)

        logger.debug(
            "Rule matching complete",
            extra={
                "goal": goal_lower[:80],
                "matches": [{"rule_id": m.rule.rule_id, "score": m.score} for m in matches],
            },
        )
        return matches

    @staticmethod
    def _merge_tasks(matches: list[_RuleMatch]) -> list[_RuleTaskDef]:
        """Merge tasks from all matched rules.

        Strategy: Union merge. Tasks with the same ID are deduplicated
        (first occurrence wins). Dependencies are merged as union.
        """
        seen: dict[str, _RuleTaskDef] = {}

        for match in matches:
            for task in match.rule.tasks:
                if task.id not in seen:
                    seen[task.id] = task
                else:
                    # Merge dependencies (union)
                    existing = seen[task.id]
                    merged_deps = list(set(existing.dependencies) | set(task.dependencies))
                    existing.dependencies = merged_deps

        return list(seen.values())

    @staticmethod
    def _merge_explanations(matches: list[_RuleMatch]) -> str:
        """Build a human-readable explanation of the plan structure."""
        if not matches:
            return "No rules matched."

        parts: list[str] = []
        parts.append(f"Plan generated from {len(matches)} rule template(s):")

        for i, match in enumerate(matches, 1):
            parts.append(
                f"  {i}. [{match.rule.rule_id}] {match.rule.description}"
                f" (matched keywords: {match.score})"
            )

        parts.append(
            "\nExecution order follows task dependency chain: "
            "RETRIEVE → PROCESS → ANALYZE → GENERATE → VALIDATE."
        )

        return "\n".join(parts)
