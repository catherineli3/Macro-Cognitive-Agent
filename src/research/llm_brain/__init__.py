"""llm_brain — V3.4 Macro Research Brain Upgrade.

The LLM Brain adds deep reasoning on top of the rule-based macro analysis
pipeline. It transforms structured data (state_vector, narratives, beliefs,
mental models) into ResearchMemos — the output of a senior macro researcher.

Core components:
    ResearchMemo          — The output schema (deep analysis + judgment)
    ResearchReasoningAgent — The reasoning engine (prompt → LLM → structured output)
    PromptArchitecture    — System prompts, few-shot examples, reasoning templates
    LLMClient             — Abstraction layer for multiple LLM providers
"""

from src.research.llm_brain.llm_client import LLMClient, LLMResponse
from src.research.llm_brain.prompts import (
    EXPERT_PERSONAS,
    MACRO_REASONING_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    PromptArchitecture,
)
from src.research.llm_brain.research_reasoning_agent import (
    ReasoningInput,
    ResearchReasoningAgent,
)
from src.research.llm_brain.schemas import (
    AssetImplication,
    BeliefSynthesis,
    CausalAnalysis,
    ConfidenceCalibration,
    EvidenceAssessment,
    FalsificationCheck,
    NarrativeAnalysis,
    RegimeAnalysis,
    ResearchMemo,
    TailRisk,
)

__all__ = [
    "ResearchMemo",
    "RegimeAnalysis",
    "NarrativeAnalysis",
    "CausalAnalysis",
    "EvidenceAssessment",
    "BeliefSynthesis",
    "FalsificationCheck",
    "AssetImplication",
    "TailRisk",
    "ConfidenceCalibration",
    "ResearchReasoningAgent",
    "ReasoningInput",
    "PromptArchitecture",
    "RESEARCHER_SYSTEM_PROMPT",
    "MACRO_REASONING_PROMPT",
    "EXPERT_PERSONAS",
    "LLMClient",
    "LLMResponse",
]
