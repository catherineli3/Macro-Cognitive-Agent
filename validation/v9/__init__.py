# =============================================================================
# V9: Research Capability Validation & Reality Training
# =============================================================================
# NOT architecture. NOT abstraction.
# ONLY: benchmark, data, evaluation, learning, improvement.
# =============================================================================

from validation.v9.historical_cases import (
    HistoricalCase,
    CASES,
    build_all_cases,
    get_case_by_id,
    get_cases_by_tag,
    get_cases_by_cycle,
    get_cases_by_difficulty,
)

from validation.v9.scoring_engine import (
    MacroUnderstandingScorer,
    BlindTestResult,
    DimensionScore,
    MACRO_UNDERSTANDING_DIMENSIONS,
)

from validation.v9.blind_test import (
    BlindTestRunner,
    BlindTestCase,
    BlindTestSuite,
    v10_agent_research,      # V10: real LLM agent
    simulate_agent_research,  # V10: backward-compat alias
)

from validation.v9.prediction_calibration import (
    EnhancedPredictionLedger,
    PredictionRecord,
    ErrorDiagnosis,
    ErrorType,
)

from validation.v9.report_benchmark import (
    ReportBenchmark,
    MemoComparisonResult,
    ResearchQualityDimensions,
)

from validation.v9.reasoning_optimizer import (
    ReasoningOptimizer,
    ReasoningError,
    ReasoningStyle,
    ImprovementIteration,
    ERROR_PATTERNS,
    VERSION_EVOLUTION,
)

from validation.v9.paper_trading import (
    PaperPortfolio,
    PortfolioSnapshot,
    TradeRecommendation,
)

from validation.v9.agent_evaluation import (
    AgentEvaluator,
    CapabilityReport,
)

from validation.v9.benchmark_runner import (
    V9BenchmarkRunner,
    V9BenchmarkResult,
    quick_benchmark,
    full_benchmark,
)

from validation.v9.expert_comparison import (
    ExpertComparator,
    ExpertComparisonResult,
    InstitutionalBenchmark,
    run_expert_comparison,
)


__all__ = [
    # Phase 1: Historical cases
    "HistoricalCase", "CASES", "build_all_cases",
    "get_case_by_id", "get_cases_by_tag",
    "get_cases_by_cycle", "get_cases_by_difficulty",
    # Phase 2: Blind test + scoring
    "MacroUnderstandingScorer", "BlindTestResult", "DimensionScore",
    "MACRO_UNDERSTANDING_DIMENSIONS",
    "BlindTestRunner", "BlindTestCase", "BlindTestSuite",
    "v10_agent_research", "simulate_agent_research",
    # Phase 3: Prediction calibration
    "EnhancedPredictionLedger", "PredictionRecord",
    "ErrorDiagnosis", "ErrorType",
    # Phase 4: Report benchmark
    "ReportBenchmark", "MemoComparisonResult",
    "ResearchQualityDimensions",
    # Phase 5: Reasoning optimization
    "ReasoningOptimizer", "ReasoningError", "ReasoningStyle",
    "ImprovementIteration", "ERROR_PATTERNS", "VERSION_EVOLUTION",
    # Phase 6: Paper trading
    "PaperPortfolio", "PortfolioSnapshot", "TradeRecommendation",
    # Phase 7: Agent evaluation
    "AgentEvaluator", "CapabilityReport",
    # Integration
    "V9BenchmarkRunner", "V9BenchmarkResult",
    "quick_benchmark", "full_benchmark",
    "ExpertComparator", "ExpertComparisonResult",
    "InstitutionalBenchmark", "run_expert_comparison",
]
