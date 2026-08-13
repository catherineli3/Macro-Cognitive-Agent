"""Candidate Generator — Generate ~30 candidate hypotheses from macro signals.

Milestone A: Combines template-based generation with signal-driven instantiation.
Each candidate carries evidence claims, a thesis statement, and a transmission chain.
"""

from __future__ import annotations

from src.hypothesis.signal_engine import AnomalousSignal, SignalReport, SignalTheme
from src.schemas.hypothesis_v3_1 import CandidateHypothesis, EvidenceClaim, TransmissionSegment
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Dimension Definitions ────────────────────────────────────────────────────

DIMENSIONS = ["liquidity", "credit", "growth", "risk_appetite", "inflation"]

DIMENSION_LABELS = {
    "liquidity": "Liquidity Conditions",
    "credit": "Credit Markets",
    "growth": "Economic Growth",
    "risk_appetite": "Risk Appetite",
    "inflation": "Inflation Dynamics",
}

# ── Hypothesis Templates ─────────────────────────────────────────────────────

# Each template defines: thesis pattern, narrative, dimension, direction,
# trigger conditions, evidence indicators, and transmission chain segments.
_HYPOTHESIS_TEMPLATES: list[dict] = [
    # ═══ LIQUIDITY ═══
    {
        "id": "liq_01",
        "dimension": "liquidity",
        "direction": "bullish",
        "trigger_themes": ["liquidity_easing", "dollar_weakness"],
        "thesis": "Liquidity easing will be the dominant macro driver, pushing risk assets higher.",
        "narrative": (
            "Liquidity conditions are easing as signaled by {signals}. "
            "Historically, liquidity-driven rallies broaden across equities, credit, and EM assets. "
            "The transmission path flows through cheaper funding → credit expansion → risk asset appreciation."
        ),
        "evidence_indicators": ["DXY", "US02Y", "FED_FUNDS"],
        "transmission": [
            {
                "source": "liquidity",
                "target": "credit",
                "direction": "+",
                "desc": "Easing liquidity expands credit availability",
            },
            {
                "source": "credit",
                "target": "NASDAQ",
                "direction": "+",
                "desc": "Cheaper credit fuels equity investment",
            },
        ],
    },
    {
        "id": "liq_02",
        "dimension": "liquidity",
        "direction": "bearish",
        "trigger_themes": ["liquidity_tightening"],
        "thesis": "Liquidity tightening constrains risk assets; defensive positioning is warranted.",
        "narrative": (
            "Liquidity is tightening as {signals}. "
            "Tighter financial conditions restrict capital flows and suppress risk appetite. "
            "Defensive positioning across equities and a stronger dollar are expected outcomes."
        ),
        "evidence_indicators": ["DXY", "US02Y", "FED_FUNDS"],
        "transmission": [
            {
                "source": "liquidity",
                "target": "credit",
                "direction": "-",
                "desc": "Tightening liquidity restricts credit",
            },
            {
                "source": "credit",
                "target": "NASDAQ",
                "direction": "-",
                "desc": "Restricted credit weighs on equities",
            },
        ],
    },
    {
        "id": "liq_03",
        "dimension": "liquidity",
        "direction": "bullish",
        "trigger_themes": ["liquidity_easing"],
        "thesis": "Fed easing cycle will weaken the dollar and benefit emerging markets and gold.",
        "narrative": (
            "A Fed easing cycle, driven by {signals}, historically weakens the dollar. "
            "Dollar weakness supports EM currencies, commodity prices, and gold. "
            "The transmission: lower rates → capital outflows from USD → dollar depreciation → commodity/EM rally."
        ),
        "evidence_indicators": ["US02Y", "DXY", "Gold"],
        "transmission": [
            {
                "source": "liquidity",
                "target": "DXY",
                "direction": "-",
                "desc": "Easing reduces dollar demand",
            },
            {
                "source": "DXY",
                "target": "Gold",
                "direction": "-",
                "desc": "Weaker dollar supports gold",
            },
        ],
    },
    {
        "id": "liq_04",
        "dimension": "liquidity",
        "direction": "neutral",
        "trigger_themes": [],
        "thesis": "Liquidity conditions are stable; no strong directional bias from monetary factors.",
        "narrative": (
            "Liquidity indicators show no decisive direction. "
            "Monetary policy is in a holding pattern and not providing a clear catalyst for risk assets. "
            "Focus should shift to growth and credit dynamics for directional cues."
        ),
        "evidence_indicators": ["DXY", "US02Y"],
        "transmission": [
            {
                "source": "liquidity",
                "target": "NASDAQ",
                "direction": "~",
                "desc": "Stable liquidity has limited impact on equities",
            },
        ],
    },
    # ═══ CREDIT ═══
    {
        "id": "crd_01",
        "dimension": "credit",
        "direction": "bullish",
        "trigger_themes": ["liquidity_easing", "risk_on"],
        "thesis": "Credit conditions are improving; credit-sensitive assets will outperform.",
        "narrative": (
            "Credit spreads are tightening as {signals}. "
            "Improving credit conditions support HYG and risk-on positioning. "
            "The credit cycle expansion favors lower-quality credit and equity beta."
        ),
        "evidence_indicators": ["HYG", "VIX"],
        "transmission": [
            {
                "source": "credit",
                "target": "HYG",
                "direction": "+",
                "desc": "Tightening spreads boost high-yield bonds",
            },
            {
                "source": "credit",
                "target": "SPX",
                "direction": "+",
                "desc": "Credit expansion supports equity valuations",
            },
        ],
    },
    {
        "id": "crd_02",
        "dimension": "credit",
        "direction": "bearish",
        "trigger_themes": ["credit_stress", "liquidity_tightening"],
        "thesis": "Credit stress is building; widening spreads signal risk aversion ahead.",
        "narrative": (
            "Credit markets are showing stress as {signals}. "
            "Widening spreads and elevated volatility historically precede equity drawdowns. "
            "Defensive rotation out of high-yield and into quality is the expected response."
        ),
        "evidence_indicators": ["HYG", "VIX"],
        "transmission": [
            {
                "source": "credit",
                "target": "HYG",
                "direction": "-",
                "desc": "Widening spreads hurt high-yield",
            },
            {
                "source": "credit",
                "target": "SPX",
                "direction": "-",
                "desc": "Credit contraction spills into equities",
            },
        ],
    },
    {
        "id": "crd_03",
        "dimension": "credit",
        "direction": "bearish",
        "trigger_themes": ["credit_stress"],
        "thesis": "Credit markets are issuing a warning that equity markets are ignoring — a correction is likely.",
        "narrative": (
            "Despite stable equities, credit markets are deteriorating as {signals}. "
            "This divergence between credit and equity markets has historically resolved "
            "with equities catching down to credit. The transmission lag is typically 2-4 weeks."
        ),
        "evidence_indicators": ["HYG", "SPX"],
        "transmission": [
            {
                "source": "credit",
                "target": "HYG",
                "direction": "-",
                "desc": "Credit stress evident in HYG weakness",
            },
            {
                "source": "HYG",
                "target": "SPX",
                "direction": "+",
                "desc": "HYG leads SPX — divergence resolves with SPX declining",
            },
        ],
    },
    # ═══ GROWTH ═══
    {
        "id": "grw_01",
        "dimension": "growth",
        "direction": "bullish",
        "trigger_themes": ["growth_accelerating", "risk_on"],
        "thesis": "Economic growth is accelerating; cyclical equities and rates will rise together.",
        "narrative": (
            "Growth indicators point to acceleration as {signals}. "
            "In a growth-driven regime, equities and bond yields rise together — "
            "the 'good' kind of rate increase that does not threaten risk assets."
        ),
        "evidence_indicators": ["SPX", "US10Y"],
        "transmission": [
            {
                "source": "growth",
                "target": "SPX",
                "direction": "+",
                "desc": "Growth drives earnings → equity appreciation",
            },
            {
                "source": "growth",
                "target": "US10Y",
                "direction": "+",
                "desc": "Growth raises real rate expectations",
            },
        ],
    },
    {
        "id": "grw_02",
        "dimension": "growth",
        "direction": "bearish",
        "trigger_themes": ["growth_slowing"],
        "thesis": "Growth is decelerating; defensive rotation and duration exposure are warranted.",
        "narrative": (
            "Growth momentum is fading as {signals}. "
            "Decelerating growth typically triggers rotation from cyclicals to defensives "
            "and rallies in duration-sensitive assets as rate expectations decline."
        ),
        "evidence_indicators": ["SPX", "US10Y"],
        "transmission": [
            {
                "source": "growth",
                "target": "SPX",
                "direction": "-",
                "desc": "Slowing growth weighs on earnings",
            },
            {
                "source": "growth",
                "target": "US10Y",
                "direction": "-",
                "desc": "Slowing growth reduces rate expectations",
            },
        ],
    },
    {
        "id": "grw_03",
        "dimension": "growth",
        "direction": "bullish",
        "trigger_themes": ["growth_accelerating"],
        "thesis": "Strong growth will overwhelm inflation concerns; real assets and equities both benefit.",
        "narrative": (
            "Growth acceleration is strong enough to make inflation secondary as {signals}. "
            "Real growth drives real returns — nominal rate increases are absorbed by earnings growth. "
            "Equities and commodities benefit from the demand pull."
        ),
        "evidence_indicators": ["SPX", "US10Y", "Gold"],
        "transmission": [
            {
                "source": "growth",
                "target": "SPX",
                "direction": "+",
                "desc": "Strong growth lifts all equity sectors",
            },
            {
                "source": "growth",
                "target": "Gold",
                "direction": "+",
                "desc": "Demand-pull supports commodity prices",
            },
        ],
    },
    # ═══ RISK APPETITE ═══
    {
        "id": "rsk_01",
        "dimension": "risk_appetite",
        "direction": "bullish",
        "trigger_themes": ["risk_on", "liquidity_easing"],
        "thesis": "Risk appetite is strong and broadening; laggard sectors will catch up.",
        "narrative": (
            "Risk appetite indicators confirm a bullish environment as {signals}. "
            "Low volatility and rising equities create a positive feedback loop. "
            "The breadth of the rally is expanding from mega-cap to broader indices."
        ),
        "evidence_indicators": ["SPX", "VIX"],
        "transmission": [
            {
                "source": "risk_appetite",
                "target": "SPX",
                "direction": "+",
                "desc": "Risk appetite directly supports equities",
            },
            {
                "source": "risk_appetite",
                "target": "VIX",
                "direction": "-",
                "desc": "Risk appetite suppresses volatility",
            },
        ],
    },
    {
        "id": "rsk_02",
        "dimension": "risk_appetite",
        "direction": "bearish",
        "trigger_themes": ["credit_stress", "liquidity_tightening"],
        "thesis": "Risk appetite is collapsing; volatility will spike and risk assets will sell off.",
        "narrative": (
            "Risk appetite is deteriorating as {signals}. "
            "Rising volatility and declining risk assets create a negative feedback loop. "
            "The VIX term structure inversion signals acute near-term fear."
        ),
        "evidence_indicators": ["VIX", "SPX"],
        "transmission": [
            {
                "source": "risk_appetite",
                "target": "VIX",
                "direction": "+",
                "desc": "Fear drives volatility higher",
            },
            {
                "source": "risk_appetite",
                "target": "SPX",
                "direction": "-",
                "desc": "Risk aversion causes equity selling",
            },
        ],
    },
    {
        "id": "rsk_03",
        "dimension": "risk_appetite",
        "direction": "bullish",
        "trigger_themes": ["risk_on"],
        "thesis": "The AI capex cycle is a structural driver that will sustain risk appetite regardless of rate cycles.",
        "narrative": (
            "While traditional macro signals are mixed as {signals}, "
            "the structural AI capital expenditure cycle creates a persistent bid for semiconductors "
            "and technology that is independent of the rate cycle. This is a multi-year theme."
        ),
        "evidence_indicators": ["SPX", "NASDAQ"],
        "transmission": [
            {
                "source": "risk_appetite",
                "target": "NASDAQ",
                "direction": "+",
                "desc": "Structural tech demand supports NASDAQ",
            },
            {
                "source": "NASDAQ",
                "target": "SPX",
                "direction": "+",
                "desc": "Tech leadership pulls up broad indices",
            },
        ],
    },
    # ═══ INFLATION ═══
    {
        "id": "inf_01",
        "dimension": "inflation",
        "direction": "bearish",
        "trigger_themes": ["inflation_pressure"],
        "thesis": "Inflation is re-accelerating; duration-sensitive assets are vulnerable.",
        "narrative": (
            "Inflation pressures are re-emerging as {signals}. "
            "Rising inflation expectations push long-end yields higher and compress TIPS. "
            "Gold benefits from inflation hedging demand despite higher nominal rates."
        ),
        "evidence_indicators": ["TIPS", "US10Y", "Gold"],
        "transmission": [
            {
                "source": "inflation",
                "target": "US10Y",
                "direction": "+",
                "desc": "Inflation raises nominal yield expectations",
            },
            {
                "source": "inflation",
                "target": "Gold",
                "direction": "+",
                "desc": "Inflation hedging boosts gold demand",
            },
        ],
    },
    {
        "id": "inf_02",
        "dimension": "inflation",
        "direction": "bullish",
        "trigger_themes": [],
        "thesis": "Inflation is moderating; the disinflation trend supports duration and growth assets.",
        "narrative": (
            "Inflation continues to moderate as {signals}. "
            "Disinflation allows the Fed to shift toward easing, which supports both bonds and equities. "
            "The 'soft landing' narrative gains credibility as inflation declines without a growth collapse."
        ),
        "evidence_indicators": ["TIPS", "US10Y"],
        "transmission": [
            {
                "source": "inflation",
                "target": "TIPS",
                "direction": "+",
                "desc": "Disinflation boosts TIPS real return appeal",
            },
            {
                "source": "inflation",
                "target": "US10Y",
                "direction": "-",
                "desc": "Disinflation reduces nominal rate premium",
            },
        ],
    },
    {
        "id": "inf_03",
        "dimension": "inflation",
        "direction": "neutral",
        "trigger_themes": [],
        "thesis": "Inflation is in a 'last mile' phase — sticky but not accelerating, creating policy uncertainty.",
        "narrative": (
            "Inflation has fallen significantly but the 'last mile' to target remains sticky as {signals}. "
            "This creates policy uncertainty: the Fed cannot ease aggressively but also cannot tighten further. "
            "Range-bound rates and choppy equity markets are the expected outcome."
        ),
        "evidence_indicators": ["TIPS", "US10Y"],
        "transmission": [
            {
                "source": "inflation",
                "target": "US10Y",
                "direction": "~",
                "desc": "Sticky inflation keeps rates range-bound",
            },
            {
                "source": "inflation",
                "target": "SPX",
                "direction": "~",
                "desc": "Policy uncertainty limits equity direction",
            },
        ],
    },
]


# ── Generator ────────────────────────────────────────────────────────────────


class CandidateGenerator:
    """Generates candidate hypotheses from macro signal analysis.

    Strategy:
        1. Dimension coverage: generate at least one hypothesis per dimension
        2. Theme-driven: activate templates whose trigger themes match detected themes
        3. Signal-driven: create additional hypotheses from anomalous individual signals
        4. Contrarian: for each dominant theme, generate a counter-thesis hypothesis
    """

    def __init__(self) -> None:
        self._templates = _HYPOTHESIS_TEMPLATES
        self._dimensions = DIMENSIONS
        self._dim_per_direction: dict[str, int] = {}

    def generate(self, signal_report: SignalReport) -> list[CandidateHypothesis]:
        """Generate candidate hypotheses from a signal report.

        Targets ~25-35 candidates through multiple generation strategies.
        """
        candidates: list[CandidateHypothesis] = []
        self._dim_per_direction = {}
        active_themes = {t.name for t in signal_report.themes}
        anomalies = {s.indicator: s for s in signal_report.anomalies}

        # Strategy 1: Theme-driven templates (most hypotheses)
        for template in self._templates:
            triggers = set(template.get("trigger_themes", []))
            # Template with no triggers is always active (baseline coverage)
            # Template with triggers is active if any trigger theme is detected
            if len(triggers) > 0 and not (triggers & active_themes):
                continue

            hyp = self._instantiate_template(template, signal_report, anomalies)
            if hyp is not None:
                candidates.append(hyp)

        # Strategy 2: Signal-driven hypotheses — one per anomalous indicator
        for sig in signal_report.anomalies:
            dim = self._map_indicator_to_dimension(sig.indicator)
            # Only add if we don't already have too many for this dim+direction
            key = f"{dim}:{sig.direction}"
            count = self._dim_per_direction.get(key, 0)
            if count >= 2:
                continue

            hyp = self._build_signal_hypothesis(sig, dim, signal_report)
            if hyp is not None:
                candidates.append(hyp)

        # Strategy 3: Contrarian — for each major theme, add a counter-thesis
        for theme in signal_report.themes[:3]:
            opposing_dir = "bearish" if theme.direction == "bullish" else "bullish"
            dim = self._map_theme_to_dimension(theme)
            key = f"{dim}:{opposing_dir}"
            if self._dim_per_direction.get(key, 0) < 1:
                hyp = self._build_contrarian(theme, dim, signal_report)
                if hyp is not None:
                    candidates.append(hyp)

        # Strategy 4: Dimension coverage — ensure every dimension has at least
        # one bullish and one bearish hypothesis
        for dim in self._dimensions:
            for direction in ["bullish", "bearish"]:
                key = f"{dim}:{direction}"
                if self._dim_per_direction.get(key, 0) == 0:
                    hyp = self._build_dimension_fallback(dim, direction, signal_report)
                    if hyp is not None:
                        candidates.append(hyp)

        # Deduplicate by thesis similarity (simple)
        seen = set()
        unique: list[CandidateHypothesis] = []
        for c in candidates:
            key_terms = frozenset(c.thesis.lower().split()[:8])
            if key_terms not in seen:
                seen.add(key_terms)
                unique.append(c)

        logger.info(
            "candidates_generated total=%d themes=%d signals=%d",
            len(unique),
            len(signal_report.themes),
            len(signal_report.anomalies),
        )
        return unique

    # ── Internal ──────────────────────────────────────────────────────────

    def _instantiate_template(
        self,
        template: dict,
        report: SignalReport,
        anomalies: dict[str, AnomalousSignal],
    ) -> CandidateHypothesis | None:
        """Instantiate a template into a concrete CandidateHypothesis."""
        dim = template["dimension"]
        direction = template["direction"]

        # Track dimension+direction coverage
        key = f"{dim}:{direction}"
        self._dim_per_direction[key] = self._dim_per_direction.get(key, 0) + 1

        # Build evidence claims from indicator data
        evidence: list[EvidenceClaim] = []
        for ind in template.get("evidence_indicators", []):
            sig = anomalies.get(ind)
            if sig:
                evidence.append(
                    EvidenceClaim(
                        indicator=ind,
                        current_value=sig.value,
                        direction=sig.direction,
                        z_score=sig.z_score,
                        claim=sig.interpretation,
                        strength=sig.strength,
                    )
                )
            else:
                # Non-anomalous but still relevant
                evidence.append(
                    EvidenceClaim(
                        indicator=ind,
                        direction=direction if direction != "neutral" else "neutral",
                        claim=f"{ind} in alignment with {dim} {direction} thesis",
                        strength=0.3,
                    )
                )

        # Build transmission chain
        chain = [
            TransmissionSegment(
                source=s["source"],
                target=s["target"],
                direction=s["direction"],
                description=s["desc"],
                reliability=0.5,  # Default; updated in Milestone B
            )
            for s in template.get("transmission", [])
        ]

        # Format narrative with actual signal descriptions
        signal_desc = (
            ", ".join(s.interpretation for s in report.anomalies[:4])
            if report.anomalies
            else "mixed signals"
        )
        narrative = template["narrative"].format(signals=signal_desc)

        # Compute initial competition score (base on evidence strength)
        base_score = 0.5
        if evidence:
            base_score = sum(e.strength for e in evidence) / len(evidence)

        return CandidateHypothesis(
            dimension=dim,
            direction=direction,
            thesis=template["thesis"],
            narrative=narrative,
            evidence=evidence,
            transmission_chain=chain,
            source_template=template["id"],
            competition_score=round(base_score, 4),
            generation_context={"active_themes": [t.name for t in report.themes]},
        )

    def _build_signal_hypothesis(
        self,
        sig: AnomalousSignal,
        dimension: str,
        report: SignalReport,
    ) -> CandidateHypothesis | None:
        """Build a hypothesis driven by a single anomalous signal."""
        key = f"{dimension}:{sig.direction}"
        self._dim_per_direction[key] = self._dim_per_direction.get(key, 0) + 1

        evidence = [
            EvidenceClaim(
                indicator=sig.indicator,
                current_value=sig.value,
                direction=sig.direction,
                z_score=sig.z_score,
                claim=sig.interpretation,
                strength=sig.strength,
            )
        ]

        return CandidateHypothesis(
            dimension=dimension,
            direction=sig.direction,
            thesis=f"{sig.indicator} is sending a strong {sig.direction} signal that will drive the {dimension} outlook.",
            narrative=(
                f"{sig.indicator} at {sig.value:.1f} ({sig.z_score:+.1f}σ) is a significant deviation. "
                f"This {sig.direction} signal for {dimension} suggests {sig.interpretation}."
            ),
            evidence=evidence,
            transmission_chain=[
                TransmissionSegment(
                    source=dimension,
                    target=sig.indicator,
                    direction="+" if sig.direction == "bullish" else "-",
                    description=f"{dimension} drives {sig.indicator} in {sig.direction} direction",
                    reliability=0.4,
                ),
            ],
            source_template="signal_driven",
            competition_score=round(sig.strength * 0.7, 4),
        )

    def _build_contrarian(
        self,
        theme: SignalTheme,
        dimension: str,
        report: SignalReport,
    ) -> CandidateHypothesis | None:
        """Build a contrarian hypothesis opposing a dominant theme."""
        opposing_dir = "bearish" if theme.direction == "bullish" else "bullish"
        key = f"{dimension}:{opposing_dir}"
        self._dim_per_direction[key] = self._dim_per_direction.get(key, 0) + 1

        return CandidateHypothesis(
            dimension=dimension,
            direction=opposing_dir,
            thesis=f"Despite {theme.label}, the {opposing_dir} case for {dimension} cannot be dismissed — watch for a reversal.",
            narrative=(
                f"While the dominant signal is {theme.label} ({theme.direction}), "
                f"contrarian risks exist. The consensus is heavily positioned for {theme.direction} "
                f"outcomes, creating asymmetric reversal risk. Historically, crowded {theme.direction} "
                f"trades have reversed sharply when catalysts emerge."
            ),
            evidence=[
                EvidenceClaim(
                    indicator="positioning",
                    claim=f"Crowded {theme.direction} positioning creates contrarian opportunity",
                    strength=0.35,
                ),
            ],
            transmission_chain=[
                TransmissionSegment(
                    source="positioning",
                    target=dimension,
                    direction="-" if opposing_dir == "bearish" else "+",
                    description=f"Crowded {theme.direction} positioning → {opposing_dir} reversal",
                    reliability=0.3,
                ),
            ],
            source_template="contrarian",
            competition_score=0.35,
        )

    def _build_dimension_fallback(
        self,
        dim: str,
        direction: str,
        report: SignalReport,
    ) -> CandidateHypothesis | None:
        """Generate a fallback hypothesis to ensure dimension coverage."""
        key = f"{dim}:{direction}"
        self._dim_per_direction[key] = self._dim_per_direction.get(key, 0) + 1

        label = DIMENSION_LABELS.get(dim, dim.capitalize())
        return CandidateHypothesis(
            dimension=dim,
            direction=direction,
            thesis=f"{label} may shift {direction} based on underlying macro dynamics, though signals are currently mixed.",
            narrative=(
                f"No strong signal currently confirms a {direction} view on {label.lower()}. "
                f"However, regime dynamics and historical patterns suggest this scenario "
                f"deserves monitoring. The thesis would strengthen if confirming signals emerge."
            ),
            evidence=[],
            transmission_chain=[
                TransmissionSegment(
                    source=dim,
                    target="SPX",
                    direction="+" if direction == "bullish" else "-",
                    description=f"Baseline {dim} → equity transmission",
                    reliability=0.35,
                ),
            ],
            source_template="dimension_fallback",
            competition_score=0.30,
        )

    @staticmethod
    def _map_indicator_to_dimension(indicator: str) -> str:
        """Map an indicator to its primary macro dimension."""
        mapping = {
            "DXY": "liquidity",
            "USD": "liquidity",
            "US02Y": "liquidity",
            "FED_FUNDS": "liquidity",
            "HYG": "credit",
            "SPX": "growth",
            "NASDAQ": "growth",
            "VIX": "risk_appetite",
            "US10Y": "inflation",
            "TIPS": "inflation",
            "Gold": "inflation",
        }
        return mapping.get(indicator, "growth")

    @staticmethod
    def _map_theme_to_dimension(theme: SignalTheme) -> str:
        """Map a signal theme to its primary macro dimension."""
        mapping = {
            "liquidity_tightening": "liquidity",
            "liquidity_easing": "liquidity",
            "dollar_weakness": "liquidity",
            "credit_stress": "credit",
            "growth_slowing": "growth",
            "growth_accelerating": "growth",
            "risk_on": "risk_appetite",
            "inflation_pressure": "inflation",
        }
        return mapping.get(theme.name, "growth")
