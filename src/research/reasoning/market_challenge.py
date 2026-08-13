"""V10 Sprint 4.5 — Task 2: Market Challenge.

NOT: Check grammar or writing quality.
BUT: Check TRADING VALUE.

The MarketChallenge module takes a Research Memo and asks HARD trading questions:

    1. CONSENSUS?     — Is this already consensus? If yes, limited alpha.
    2. CROWDED?       — Is the trade crowded? Who's already in it?
    3. POSITIONING?   — How is the market positioned? Same side = dangerous.
    4. CATALYST?      — What's the specific catalyst? Timeline? Pre-positioned?
    5. MARKET REACTION? — If right, what's the PnL? If wrong, what's the stop?

This is NOT a quality review. It's a TRADING DESK review.
The output is a MarketChallengeScore: 0-100, where > 70 means "tradeable".

Architecture:
    Memo → MarketChallenge → (Consensus, Crowded, Positioning, Catalyst, Reaction)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ConsensusCheck:
    """Is this view already consensus? Consensus = limited alpha."""

    is_consensus: bool = False
    consensus_level: float = 0.0  # 0 = contrarian, 1 = full consensus
    consensus_signals: list[str] = field(default_factory=list)
    contrarian_signals: list[str] = field(default_factory=list)
    net_consensus: str = ""  # "contrarian" / "consensus" / "balanced"
    score: float = 0.0  # 0-100, higher = better (more contrarian)
    summary: str = ""


@dataclass
class CrowdedCheck:
    """Is the trade crowded? Crowded = positioning risk."""

    is_crowded: bool = False
    crowdedness: float = 0.0  # 0 = uncrowded, 1 = extremely crowded
    who_is_in: list[str] = field(default_factory=list)  # Who's already positioned
    who_is_out: list[str] = field(default_factory=list)  # Who could still enter
    flow_signals: list[str] = field(default_factory=list)
    positioning_risk: str = ""  # Description of positioning risk
    score: float = 0.0  # 0-100, higher = better (less crowded)
    summary: str = ""


@dataclass
class PositioningCheck:
    """Market positioning assessment.

    Key question: Is the market already positioned FOR this trade?
    If yes, who is the marginal buyer/seller? Is there a positioning squeeze risk?
    """

    net_positioning: str = ""  # "long" / "short" / "flat" / "unknown"
    speculative_positioning: str = (
        ""  # "extreme_long" / "long" / "neutral" / "short" / "extreme_short"
    )
    institutional_flows: str = ""  # "buying" / "selling" / "balanced"
    retail_sentiment: str = ""  # "bullish" / "bearish" / "neutral"
    cot_signal: str = ""  # Commitment of Traders implied signal
    positioning_mismatch: bool = False  # Positioning at odds with fundamentals
    squeeze_risk: str = ""  # "long_squeeze" / "short_squeeze" / "none"
    score: float = 0.0  # 0-100
    summary: str = ""


@dataclass
class CatalystCheck:
    """Is there a specific, dateable catalyst with asymmetric payoff?"""

    has_catalyst: bool = False
    catalysts: list[str] = field(default_factory=list)
    catalyst_type: str = ""  # "data" / "event" / "flow" / "technical" / "unknown"
    catalyst_timeline: str = ""  # "imminent" / "near_term" / "medium_term" / "distant" / "none"
    is_pre_positioned: bool = False  # Is the market already pricing the catalyst?
    asymmetric_payoff: bool = False  # Is payoff asymmetric?
    known_unknowns: list[str] = field(default_factory=list)
    score: float = 0.0
    summary: str = ""


@dataclass
class ReactionCheck:
    """How will the market react? What's the expected PnL path?"""

    expected_pnl_pct: float = 0.0  # Expected return if thesis correct
    stop_loss_pct: float = 0.0  # Where to stop out
    risk_reward_ratio: float = 0.0  # Reward/Risk
    liquidity_concern: bool = False  # Can you size the trade?
    correlation_risk: str = ""  # What correlation risk exists?
    reaction_mechanism: str = ""  # How market will react (repricing channel)
    time_decay: str = ""  # Does the trade have negative carry?
    fat_tail_risk: str = ""  # Low-probability catastrophic outcome
    score: float = 0.0
    summary: str = ""


@dataclass
class MarketChallengeResult:
    """Complete market challenge assessment.

    This is the core output: a trading-desk-quality viability assessment
    of the research memo's trade idea.

    Score interpretation:
        90-100: Exceptional setup — asymmetric, contrarian, uncrowded, imminent catalyst
        75-89:  Good trade — most boxes checked
        60-74:  Decent trade — some concerns
        40-59:  Marginal — significant issues
        <40:    Untradeable — consensus, crowded, no catalyst
    """

    consensus: ConsensusCheck = field(default_factory=ConsensusCheck)
    crowded: CrowdedCheck = field(default_factory=CrowdedCheck)
    positioning: PositioningCheck = field(default_factory=PositioningCheck)
    catalyst: CatalystCheck = field(default_factory=CatalystCheck)
    reaction: ReactionCheck = field(default_factory=ReactionCheck)

    overall_score: float = 0.0  # Weighted composite
    tradeable: bool = False  # > 60 threshold
    grade: str = ""  # A/B/C/D/F
    key_concern: str = ""
    key_strength: str = ""
    sizing_recommendation: str = ""  # "full" / "half" / "quarter" / "tracking" / "pass"

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "tradeable": self.tradeable,
            "grade": self.grade,
            "key_concern": self.key_concern,
            "key_strength": self.key_strength,
            "sizing_recommendation": self.sizing_recommendation,
            "consensus": {
                "score": self.consensus.score,
                "is_consensus": self.consensus.is_consensus,
                "net_consensus": self.consensus.net_consensus,
                "summary": self.consensus.summary,
            },
            "crowded": {
                "score": self.crowded.score,
                "is_crowded": self.crowded.is_crowded,
                "crowdedness": self.crowded.crowdedness,
                "summary": self.crowded.summary,
            },
            "positioning": {
                "score": self.positioning.score,
                "net_positioning": self.positioning.net_positioning,
                "squeeze_risk": self.positioning.squeeze_risk,
                "summary": self.positioning.summary,
            },
            "catalyst": {
                "score": self.catalyst.score,
                "has_catalyst": self.catalyst.has_catalyst,
                "asymmetric_payoff": self.catalyst.asymmetric_payoff,
                "summary": self.catalyst.summary,
            },
            "reaction": {
                "score": self.reaction.score,
                "risk_reward_ratio": self.reaction.risk_reward_ratio,
                "expected_pnl_pct": self.reaction.expected_pnl_pct,
                "summary": self.reaction.summary,
            },
        }


# ═══════════════════════════════════════════════════════════════════════════
# Deterministic Pattern Matchers
# ═══════════════════════════════════════════════════════════════════════════

# Consensus language patterns — if memo uses these, it's likely consensus
_CONSENSUS_PATTERNS = [
    r"everyone\s+(knows|agrees|expects|believes|thinks)",
    r"market\s+(is\s+)?pricing\s+in",
    r"widely\s+(expected|anticipated|held|believed)",
    r"consensus\s+(view|estimate|forecast|expectation)",
    r"fed\s+will\s+cut",
    r"soft\s+landing",
    r"no\s+recession",
    r"goldilocks",
    r"everything\s+bubble",
    r"don't\s+fight\s+the\s+fed",
    r"this\s+time\s+is\s+different",
    r"buy\s+the\s+dip",
    r"fed\s+put",
]

# Contrarian language — memo challenges consensus
_CONTRARIAN_PATTERNS = [
    r"contrarian",
    r"against\s+(the\s+)?consensus",
    r"market\s+is\s+(wrong|misreading|underestimating)",
    r"not\s+pricing\s+in",
    r"mispric",
    r"dislocation",
    r"asymmetric",
    r"tail\s+risk",
    r"black\s+swan",
    r"non-consensus",
    r"underappreciated",
    r"overlooked",
    r"under-the-radar",
]

# Crowded trade language
_CROWDED_PATTERNS = [
    r"crowded",
    r"positioning\s+(is\s+)?extreme",
    r"everyone\s+is\s+(long|short)",
    r"record\s+(long|short|position)",
    r"consensus\s+(long|short)",
    r"over-owned",
    r"over-positioned",
    r"crowding",
    r"herding",
    r"one-sided",
    r"all-in",
]

# Catalyst language
_CATALYST_PATTERNS = [
    r"cataly",
    r"trigger",
    r"inflection\s+point",
    r"turning\s+point",
    r"(upcoming|next|this)\s+(week|month|quarter)",
    r"fomc",
    r"cpi\s+(print|release|report)",
    r"earnings",
    r"election",
    r"decision",
    r"announcement",
    r"data\s+(release|print|report|dependent)",
]

# Directional words — bullish
_BULLISH_WORDS = [
    "long",
    "buy",
    "bullish",
    "overweight",
    "upside",
    "rally",
    "recovery",
    "acceleration",
    "expansion",
    "rate cut",
    "easing",
    "stimulus",
]

# Directional words — bearish
_BEARISH_WORDS = [
    "short",
    "sell",
    "bearish",
    "underweight",
    "downside",
    "selloff",
    "correction",
    "crash",
    "recession",
    "tightening",
    "hawkish",
    "decelerating",
    "contraction",
]

# Hedge fund / institution names for "who is in"
_INSTITUTION_NAMES = [
    "hedge fund",
    "cta",
    "risk parity",
    "pension",
    "retail",
    "mutual fund",
    "etf",
    "systematic",
    "discretionary",
    "macro fund",
    "quant",
    "real money",
    "fast money",
    "dealer",
    "bank",
    "asset manager",
    "insurance",
]


# ═══════════════════════════════════════════════════════════════════════════
# MarketChallenge
# ═══════════════════════════════════════════════════════════════════════════


class MarketChallenge:
    """V10 Sprint 4.5: Market viability assessment.

    Takes a Research Memo and the surrounding evidence, and answers
    5 hard trading questions. This is deterministic — no LLM.
    It works entirely from the memo text and structured evidence.

    The key insight: a B+ quality memo can still be an A+ trade,
    and an A-quality memo can be untradeable (consensus, crowded).
    """

    # Score weights (sums to 1.0)
    _WEIGHTS = {
        "consensus": 0.25,  # Is it contrarian?
        "crowded": 0.20,  # Is positioning clean?
        "positioning": 0.20,  # Is positioning aligned?
        "catalyst": 0.20,  # Is there an edge catalyst?
        "reaction": 0.15,  # Is PnL asymmetric?
    }

    def challenge(
        self,
        memo_text: str,
        memo_json: dict | None = None,
        step_outputs: dict | None = None,
        market_context: dict | None = None,
    ) -> MarketChallengeResult:
        """Run the full market challenge assessment.

        Args:
            memo_text: Full memo text.
            memo_json: Structured memo data (if available).
            step_outputs: Pipeline step outputs for context.
            market_context: Optional market data for cross-reference.

        Returns:
            MarketChallengeResult with scores and trading viability.
        """
        if not memo_text:
            return self._empty_result()

        text_lower = memo_text.lower()

        # 1. Consensus check
        consensus = self._check_consensus(text_lower, memo_json)

        # 2. Crowded check
        crowded = self._check_crowded(text_lower, memo_json, market_context)

        # 3. Positioning check
        positioning = self._check_positioning(text_lower, memo_json, step_outputs)

        # 4. Catalyst check
        catalyst = self._check_catalyst(text_lower, memo_json, step_outputs)

        # 5. Market reaction check
        reaction = self._check_reaction(text_lower, memo_json, market_context)

        # Composite score
        overall = (
            consensus.score * self._WEIGHTS["consensus"]
            + crowded.score * self._WEIGHTS["crowded"]
            + positioning.score * self._WEIGHTS["positioning"]
            + catalyst.score * self._WEIGHTS["catalyst"]
            + reaction.score * self._WEIGHTS["reaction"]
        )

        # Grade
        grade = self._compute_grade(overall)

        # Tradeable threshold
        tradeable = overall >= 60.0

        # Sizing
        sizing = self._compute_sizing(overall, consensus, crowded, catalyst)

        # Key concern and strength
        scores = [
            ("Consensus", consensus.score),
            ("Crowded", crowded.score),
            ("Positioning", positioning.score),
            ("Catalyst", catalyst.score),
            ("Reaction", reaction.score),
        ]
        key_concern = min(scores, key=lambda x: x[1])
        key_strength = max(scores, key=lambda x: x[1])

        return MarketChallengeResult(
            consensus=consensus,
            crowded=crowded,
            positioning=positioning,
            catalyst=catalyst,
            reaction=reaction,
            overall_score=round(overall, 1),
            tradeable=tradeable,
            grade=grade,
            key_concern=f"{key_concern[0]} (score: {key_concern[1]:.0f})",
            key_strength=f"{key_strength[0]} (score: {key_strength[1]:.0f})",
            sizing_recommendation=sizing,
        )

    # ── Individual Checks ──────────────────────────────────────────────

    def _check_consensus(self, text: str, memo_json: dict | None) -> ConsensusCheck:
        """Check if the memo's view is consensus or contrarian."""
        # Split into sentences for negation-aware matching
        sentences = re.split(r"(?<=[.;!?])\s+", text)

        consensus_hits = []
        for sentence in sentences:
            for pattern in _CONSENSUS_PATTERNS:
                matches = re.findall(pattern, sentence)
                for m in matches:
                    hit_text = str(m[0]) if isinstance(m, tuple) and m else str(m)
                    # Check if the sentence contains negation before the match
                    negated = self._is_negated(sentence, pattern)
                    if not negated:
                        consensus_hits.append(hit_text)

        contrarian_hits = []
        for pattern in _CONTRARIAN_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                contrarian_hits.append(
                    str(matches[0]) if isinstance(matches[0], str) else str(matches)
                )

        # Calculate consensus level
        total_hits = len(consensus_hits) + len(contrarian_hits)
        if total_hits > 0:
            consensus_level = len(consensus_hits) / total_hits
        else:
            # No clear signals — check memo_json for consensus indicators
            consensus_level = 0.5

        # Also check from memo_json
        if memo_json:
            belief_data = memo_json.get("belief_state", memo_json.get("beliefs", []))
            if isinstance(belief_data, list):
                consensus_beliefs = sum(
                    1
                    for b in belief_data
                    if isinstance(b, dict) and b.get("consensus_level", 0) > 0.6
                )
                if belief_data:
                    consensus_level = max(consensus_level, consensus_beliefs / len(belief_data))

        is_consensus = consensus_level > 0.6

        # Score: more contrarian = higher score
        # Contrarian (low consensus) = excellent
        if consensus_level < 0.2:
            score = 100.0  # Deeply contrarian
        elif consensus_level < 0.35:
            score = 85.0  # Non-consensus
        elif consensus_level < 0.5:
            score = 70.0  # Slightly contrarian
        elif consensus_level < 0.65:
            score = 50.0  # Borderline consensus
        elif consensus_level < 0.8:
            score = 30.0  # Consensus
        else:
            score = 10.0  # Deeply consensus — limited alpha

        if consensus_level < 0.35:
            net_consensus = "contrarian"
        elif consensus_level > 0.65:
            net_consensus = "consensus"
        else:
            net_consensus = "balanced"

        summary = (
            f"{'Consensus' if is_consensus else 'Contrarian'} view "
            f"(level: {consensus_level:.0%}). "
            f"{len(consensus_hits)} consensus signals, {len(contrarian_hits)} contrarian signals."
        )

        return ConsensusCheck(
            is_consensus=is_consensus,
            consensus_level=round(consensus_level, 2),
            consensus_signals=consensus_hits[:5],
            contrarian_signals=contrarian_hits[:5],
            net_consensus=net_consensus,
            score=score,
            summary=summary,
        )

    def _check_crowded(
        self, text: str, memo_json: dict | None, market_context: dict | None
    ) -> CrowdedCheck:
        """Check if the trade is crowded."""
        crowded_hits = []
        for pattern in _CROWDED_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                crowded_hits.append(
                    str(matches[0]) if isinstance(matches[0], str) else str(matches)
                )

        # Check for directional concentration language
        bullish_count = sum(1 for w in _BULLISH_WORDS if w in text)
        bearish_count = sum(1 for w in _BEARISH_WORDS if w in text)

        # Who is in the trade
        who_is_in = []
        for inst in _INSTITUTION_NAMES:
            if inst in text:
                # Check if mentioned in context of already positioned
                idx = text.find(inst)
                context = text[max(0, idx - 50) : idx + 50]
                if any(
                    w in context
                    for w in ["positioned", "already", "long", "short", "holding", "owns"]
                ):
                    who_is_in.append(inst)

        # Who is NOT in yet (potential marginal buyer)
        who_is_out = [inst for inst in _INSTITUTION_NAMES[:6] if inst not in who_is_in]

        # Flow signals from market_context
        flow_signals = []
        if market_context:
            if market_context.get("positioning_extreme"):
                flow_signals.append("Extreme positioning detected in market data")
            if market_context.get("sentiment_extreme"):
                flow_signals.append("Sentiment at extreme levels")

        # Calculate crowdedness
        base_crowded = min(len(crowded_hits) * 0.2, 0.6)
        concentration_crowded = 0.0
        total_directional = bullish_count + bearish_count
        if total_directional > 0:
            concentration_crowded = max(bullish_count, bearish_count) / total_directional * 0.4

        crowdedness = min(base_crowded + concentration_crowded, 1.0)
        is_crowded = crowdedness > 0.5

        # Score: less crowded = better
        if crowdedness < 0.15:
            score = 100.0  # Completely uncrowded
        elif crowdedness < 0.3:
            score = 85.0
        elif crowdedness < 0.5:
            score = 65.0
        elif crowdedness < 0.7:
            score = 40.0
        else:
            score = 15.0  # Extremely crowded

        # Positioning risk narrative
        if is_crowded:
            positioning_risk = (
                f"Trade is crowded ({crowdedness:.0%} estimated). "
                f"Who is in: {', '.join(who_is_in[:3]) if who_is_in else 'multiple participants'}. "
                f"Risk of unwind/stop-out if narrative breaks."
            )
        else:
            positioning_risk = (
                f"Trade is not crowded ({crowdedness:.0%} estimated). "
                f"Still room for marginal buyers."
            )

        return CrowdedCheck(
            is_crowded=is_crowded,
            crowdedness=round(crowdedness, 2),
            who_is_in=who_is_in[:5],
            who_is_out=who_is_out[:3],
            flow_signals=flow_signals,
            positioning_risk=positioning_risk,
            score=score,
            summary=(
                f"{'Crowded' if is_crowded else 'Not crowded'} "
                f"({crowdedness:.0%}). {len(crowded_hits)} crowding signals. "
                f"{positioning_risk}"
            ),
        )

    def _check_positioning(
        self, text: str, memo_json: dict | None, step_outputs: dict | None
    ) -> PositioningCheck:
        """Assess market positioning relative to the trade idea."""
        bullish_count = sum(1 for w in _BULLISH_WORDS if w in text)
        bearish_count = sum(1 for w in _BEARISH_WORDS if w in text)

        # Determine net positioning from step outputs
        net_pos = "unknown"
        spec_pos = "neutral"
        inst_flow = "balanced"
        retail_sent = "neutral"

        if step_outputs:
            portfolio = step_outputs.get("portfolio", {})
            if isinstance(portfolio, dict):
                pos_signal = portfolio.get("positioning_signal", "")
                if "overweight" in str(pos_signal).lower():
                    net_pos = "long"
                elif "underweight" in str(pos_signal).lower():
                    net_pos = "short"

        if memo_json:
            trade = memo_json.get(
                "trade_recommendation", memo_json.get("portfolio_implication", "")
            )
            trade_str = str(trade).lower() if trade else ""
            if any(w in trade_str for w in ["long", "buy", "overweight", "bullish"]):
                net_pos = "long"
            elif any(w in trade_str for w in ["short", "sell", "underweight", "bearish"]):
                net_pos = "short"

        # Determine if positioning is extreme
        if bullish_count > bearish_count * 3:
            spec_pos = "extreme_long"
            retail_sent = "bullish"
        elif bearish_count > bullish_count * 3:
            spec_pos = "extreme_short"
            retail_sent = "bearish"
        elif bullish_count > bearish_count * 1.5:
            spec_pos = "long"
            retail_sent = "bullish"
        elif bearish_count > bullish_count * 1.5:
            spec_pos = "short"
            retail_sent = "bearish"

        # Positioning mismatch check
        positioning_mismatch = False
        squeeze_risk = "none"

        trade_direction = memo_json.get("direction", "") if memo_json else ""
        trade_direction = str(trade_direction).lower()

        if net_pos == "long" and trade_direction in ("bearish", "short", "sell"):
            positioning_mismatch = True
            squeeze_risk = "short_squeeze"
        elif net_pos == "short" and trade_direction in ("bullish", "long", "buy"):
            positioning_mismatch = True
            squeeze_risk = "long_squeeze"

        # Score
        if positioning_mismatch:
            score = 85.0  # Positioning against trade = pain trade = asymmetric opportunity
        elif spec_pos in ("extreme_long", "extreme_short"):
            score = 30.0  # Extreme positioning in same direction = crowded, risky
        elif net_pos == "unknown":
            score = 50.0
        else:
            score = 60.0

        return PositioningCheck(
            net_positioning=net_pos,
            speculative_positioning=spec_pos,
            institutional_flows=inst_flow,
            retail_sentiment=retail_sent,
            cot_signal="",
            positioning_mismatch=positioning_mismatch,
            squeeze_risk=squeeze_risk,
            score=score,
            summary=(
                f"Net positioning: {net_pos}, Spec: {spec_pos}. "
                f"{'PAIN TRADE — positioning mismatch' if positioning_mismatch else 'Aligned positioning'}"
                + (f" — squeeze risk: {squeeze_risk}" if squeeze_risk != "none" else "")
            ),
        )

    def _check_catalyst(
        self, text: str, memo_json: dict | None, step_outputs: dict | None
    ) -> CatalystCheck:
        """Check for specific, dateable catalysts."""
        catalysts = []
        for pattern in _CATALYST_PATTERNS:
            matches = re.findall(pattern, text[:3000])  # Check first 3000 chars
            for m in matches:
                catalysts.append(str(m).strip())

        # Also extract from memo JSON
        if memo_json:
            cat_field = memo_json.get("catalyst", memo_json.get("catalysts", ""))
            if isinstance(cat_field, str) and cat_field:
                catalysts.append(cat_field)
            elif isinstance(cat_field, list):
                catalysts.extend(cat_field)

            risks = memo_json.get("key_risks", memo_json.get("risks", []))
            known_unknowns = []
            if isinstance(risks, list):
                for r in risks[:3]:
                    if isinstance(r, dict):
                        known_unknowns.append(r.get("title", str(r)[:80]))
                    else:
                        known_unknowns.append(str(r)[:80])

        has_catalyst = len(catalysts) > 0

        # Classify catalyst type
        cat_text = " ".join(catalysts).lower()
        if any(w in cat_text for w in ["fomc", "fed", "ecb", "central bank"]):
            catalyst_type = "event"
        elif any(w in cat_text for w in ["cpi", "ppi", "nFp", "gdp", "data", "print"]):
            catalyst_type = "data"
        elif any(w in cat_text for w in ["flow", "rebalancing", "expiry", "option"]):
            catalyst_type = "flow"
        elif any(w in cat_text for w in ["level", "breakout", "support", "resistance"]):
            catalyst_type = "technical"
        else:
            catalyst_type = "unknown" if has_catalyst else "none"

        # Timeline classification
        if any(w in cat_text for w in ["this week", "tomorrow", "today", "imminent"]):
            catalyst_timeline = "imminent"
        elif any(w in cat_text for w in ["this month", "next", "upcoming", "near"]):
            catalyst_timeline = "near_term"
        elif any(w in cat_text for w in ["next quarter", "h2", "later", "eventually"]):
            catalyst_timeline = "medium_term"
        elif has_catalyst:
            catalyst_timeline = "distant"
        else:
            catalyst_timeline = "none"

        # Pre-positioning check
        is_pre_positioned = any(
            w in text for w in ["priced in", "already pricing", "market expects"]
        )

        # Asymmetric payoff check
        asymmetric_payoff = any(
            w in text
            for w in [
                "asymmetric",
                "tails",
                "convex",
                "optionality",
                "low risk high reward",
                "heads i win",
            ]
        )

        # Score computation
        if not has_catalyst:
            score = 10.0  # No catalyst = not tradeable
        elif catalyst_timeline == "imminent" and asymmetric_payoff and not is_pre_positioned:
            score = 100.0  # Perfect: imminent catalyst, asymmetric, not priced
        elif catalyst_timeline == "imminent":
            score = 85.0
        elif catalyst_timeline == "near_term" and asymmetric_payoff:
            score = 80.0
        elif catalyst_timeline == "near_term":
            score = 65.0
        elif catalyst_timeline == "medium_term":
            score = 45.0
        elif is_pre_positioned:
            score = 20.0  # Catalyst already priced in
        else:
            score = 30.0

        return CatalystCheck(
            has_catalyst=has_catalyst,
            catalysts=catalysts[:5],
            catalyst_type=catalyst_type,
            catalyst_timeline=catalyst_timeline,
            is_pre_positioned=is_pre_positioned,
            asymmetric_payoff=asymmetric_payoff,
            known_unknowns=known_unknowns if memo_json else [],
            score=score,
            summary=(
                f"{'Has' if has_catalyst else 'No'} catalyst ({catalyst_type}, {catalyst_timeline}). "
                + ("ASYMMETRIC PAYOFF. " if asymmetric_payoff else "")
                + ("Pre-positioned — already priced. " if is_pre_positioned else "")
            ),
        )

    def _check_reaction(
        self, text: str, memo_json: dict | None, market_context: dict | None
    ) -> ReactionCheck:
        """Assess expected market reaction and PnL path."""
        # Extract PnL expectations from text
        pnl_pct = 0.0
        stop_loss = 0.0
        rr_ratio = 0.0

        # Look for percentage targets
        pct_matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
        percentages = [float(p) for p in pct_matches]

        if len(percentages) >= 2:
            # First two percentages might be target and stop
            positive = [p for p in percentages if p > 0]
            if positive:
                pnl_pct = max(positive[:2])
        elif len(percentages) == 1:
            pnl_pct = percentages[0]

        # Risk/reward from text or JSON
        rr_matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*:?\s*(\d+(?:\.\d+)?)\s*(?:risk.?reward|r/?r)", text
        )
        if rr_matches:
            try:
                reward_part = float(rr_matches[0][0])
                risk_part = float(rr_matches[0][1])
                if risk_part > 0:
                    rr_ratio = reward_part / risk_part
            except (ValueError, ZeroDivisionError):
                pass

        if memo_json:
            rr = memo_json.get("risk_reward", memo_json.get("risk_reward_ratio", 0))
            if rr and isinstance(rr, (int, float)):
                rr_ratio = float(rr)
            sl = memo_json.get("stop_loss", memo_json.get("stop_loss_pct", 0))
            if sl and isinstance(sl, (int, float)):
                stop_loss = float(sl)

        # Liquidity concern
        liquidity_concern = any(
            w in text
            for w in [
                "illiquid",
                "liquidity risk",
                "thin",
                "wide spread",
                "small cap",
                "frontier",
                "capacity",
            ]
        )

        # Correlation risk
        correlation_risk = ""
        if "correlated" in text or "correlation" in text:
            correlation_risk = "Correlation risk explicitly noted in memo"
        elif any(w in text for w in ["risk-on", "risk-off", "beta"]):
            correlation_risk = (
                "Beta/correlation risk implied — trade may be market-direction dependent"
            )

        # Time decay
        if any(w in text for w in ["carry", "contango", "backwardation", "theta", "option"]):
            time_decay = "Derivative/options involved — check for time decay"
        elif "hold" in text and any(w in text for w in ["until", "wait for", "patience"]):
            time_decay = "Trade may require patience — opportunity cost / negative carry risk"
        else:
            time_decay = "No obvious time decay concern"

        # Fat tail risk
        fat_tail_risk = ""
        if any(w in text for w in ["black swan", "tail risk", "fat tail", "extreme event"]):
            fat_tail_risk = "Fat tail risk explicitly acknowledged"
        elif "crisis" in text or "crash" in text:
            fat_tail_risk = "Systemic risk scenario mentioned but not priced"

        # Score
        if rr_ratio >= 3.0:
            score = 95.0  # Exceptional risk/reward
        elif rr_ratio >= 2.0:
            score = 85.0  # Good risk/reward
        elif rr_ratio >= 1.5:
            score = 70.0  # Acceptable
        elif rr_ratio >= 1.0:
            score = 55.0  # Marginal
        elif pnl_pct > 5:
            score = 60.0  # Has target but no RR — assume OK
        else:
            score = 35.0  # Unknown PnL expectations

        if liquidity_concern:
            score -= 20
        if correlation_risk and "risk" in correlation_risk.lower():
            score -= 10

        score = max(0.0, min(100.0, score))

        return ReactionCheck(
            expected_pnl_pct=round(pnl_pct, 1),
            stop_loss_pct=round(stop_loss, 1),
            risk_reward_ratio=round(rr_ratio, 1),
            liquidity_concern=liquidity_concern,
            correlation_risk=correlation_risk,
            reaction_mechanism="Price discovery through primary market mechanism",
            time_decay=time_decay,
            fat_tail_risk=fat_tail_risk,
            score=score,
            summary=(
                f"Expected PnL: {pnl_pct:.1f}% | R/R: {rr_ratio:.1f}:1. "
                + ("LIQUIDITY CONCERN. " if liquidity_concern else "")
            ),
        )

    # ── Scoring Helpers ────────────────────────────────────────────────

    def _is_negated(self, sentence: str, pattern: str) -> bool:
        """Check if a consensus pattern match is negated in the sentence.

        E.g., "Soft landing is wrong" should NOT count as consensus.
        Checks negation markers both BEFORE and AFTER the pattern match.
        """
        negators = [
            r"\bnot\b",
            r"\bwrong\b",
            r"\bno\b",
            r"\bwon['']t\b",
            r"\bcan['']t\b",
            r"\bshouldn['']t\b",
            r"\bunlikely\b",
            r"\bfalse\b",
            r"\bmis(pricing|reading|taken|guided)\b",
            r"\bagainst\b",
            r"\breject\b",
            r"\bdisagree\b",
            r"\bisn['']t\b",
            r"\bfail\b",
            r"\bdoubt\b",
            r"\bmistake",
            r"\bover(blown|hyped|stated)\b",
        ]

        # Find the pattern match position
        match = re.search(pattern, sentence)
        if not match:
            return False

        # Check text BEFORE the match (within 5 words)
        prefix = sentence[: match.start()].lower()
        prefix_words = prefix.split()[-5:]
        for negator in negators:
            if re.search(negator, " ".join(prefix_words)):
                return True

        # Check text AFTER the match (within 5 words after the match)
        suffix = sentence[match.end() :].lower()
        suffix_words = suffix.split()[:5]
        for negator in negators:
            if re.search(negator, " ".join(suffix_words)):
                return True

        return False

    def _compute_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"

    def _compute_sizing(
        self,
        score: float,
        consensus: ConsensusCheck,
        crowded: CrowdedCheck,
        catalyst: CatalystCheck,
    ) -> str:
        """Recommend position sizing based on market challenge results."""
        if score >= 90:
            return "full"
        elif score >= 75:
            # Check if consensus or crowded knocks it down
            if consensus.is_consensus or crowded.is_crowded:
                return "half"
            return "full"
        elif score >= 60:
            return "half"
        elif score >= 45:
            if catalyst.has_catalyst and catalyst.catalyst_timeline in ("imminent", "near_term"):
                return "quarter"
            return "tracking"
        else:
            return "pass"

    def _empty_result(self) -> MarketChallengeResult:
        """Return empty/failed result."""
        return MarketChallengeResult(
            overall_score=0.0,
            tradeable=False,
            grade="F",
            key_concern="Empty memo — no analysis possible",
            key_strength="N/A",
            sizing_recommendation="pass",
        )


# ═══════════════════════════════════════════════════════════════════════════
# Convenience function
# ═══════════════════════════════════════════════════════════════════════════


def market_challenge(
    memo_text: str,
    memo_json: dict | None = None,
    step_outputs: dict | None = None,
    market_context: dict | None = None,
) -> MarketChallengeResult:
    """Convenience function: run market challenge assessment."""
    mc = MarketChallenge()
    return mc.challenge(memo_text, memo_json, step_outputs, market_context)
