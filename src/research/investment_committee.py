"""V8.1 Investment Committee — Multi-perspective macro debate.

The agent convenes an investment committee with distinct personas:
    - PTJ (Paul Tudor Jones) — Macro trader, momentum-aware
    - Dalio (Ray Dalio) — Machine/systematic, long-term debt cycles
    - Soros (George Soros) — Reflexivity, boom-bust
    - Bridgewater — Risk parity, all-weather
    - Macro PM — Practical portfolio management
    - Risk Manager — Pure risk perspective

The committee debates: "Should we change positioning?"

Output: structured meeting minutes with votes and rationale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


class CommitteeRole(str, Enum):
    CHAIR = "chair"  # Runs the meeting, synthesizes
    MACRO_TRADER = "macro_trader"  # PTJ-style: momentum, technicals
    SYSTEMATIC = "systematic"  # Dalio-style: cycles, machines
    REFLEXIVITY = "reflexivity"  # Soros-style: feedback loops
    RISK_PARITY = "risk_parity"  # Bridgewater-style: balanced risk
    PORTFOLIO_MANAGER = "pm"  # Practical PM
    RISK_MANAGER = "risk"  # Pure risk perspective


class Vote(str, Enum):
    INCREASE = "increase"  # Add to position
    DECREASE = "decrease"  # Reduce position
    HOLD = "hold"  # Maintain current
    HEDGE = "hedge"  # Add hedges
    EXIT = "exit"  # Close entirely


@dataclass
class CommitteeStatement:
    """A single statement from a committee member."""

    role: CommitteeRole
    member_name: str
    statement: str
    vote: Vote
    conviction: float  # 0–1

    # Supporting reasoning
    key_points: list[str] = field(default_factory=list)
    evidence_cited: list[str] = field(default_factory=list)
    risks_highlighted: list[str] = field(default_factory=list)

    # Disagreements
    disagrees_with: list[CommitteeRole] = field(default_factory=list)
    alternative_view: str = ""


@dataclass
class MeetingMinutes:
    """Complete investment committee meeting record."""

    meeting_id: str = field(default_factory=lambda: uuid4().hex[:8])
    topic: str = ""
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    convened_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Opening
    agenda: str = ""
    market_context: str = ""
    current_positioning: str = ""

    # Debate
    statements: list[CommitteeStatement] = field(default_factory=list)

    # Vote tally
    votes: dict[Vote, int] = field(default_factory=dict)
    consensus_reached: bool = False

    # Decision
    decision: str = ""
    decision_rationale: str = ""
    action_items: list[str] = field(default_factory=list)

    # Dissent
    dissenting_views: list[str] = field(default_factory=list)

    # Follow-up
    next_meeting: str = ""
    items_to_monitor: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Render meeting minutes as readable document."""
        lines = [
            "# Investment Committee Meeting",
            f"**Meeting ID**: {self.meeting_id}",
            f"**Date**: {self.date}",
            f"**Topic**: {self.topic}",
            "",
            "---",
            "",
            "## Agenda",
            self.agenda,
            "",
            "## Market Context",
            self.market_context,
            "",
            "## Current Positioning",
            self.current_positioning,
            "",
            "---",
            "",
            "## Committee Discussion",
            "",
        ]

        for stmt in self.statements:
            lines.extend(
                [
                    f"### {stmt.member_name} ({stmt.role.value})",
                    f"**Vote**: {stmt.vote.value.upper()} | **Conviction**: {stmt.conviction:.0%}",
                    "",
                    stmt.statement,
                    "",
                    "**Key Points**:",
                ]
            )
            for kp in stmt.key_points:
                lines.append(f"- {kp}")
            lines.append("")

        lines.extend(
            [
                "---",
                "",
                "## Vote Tally",
            ]
        )
        for vote, count in self.votes.items():
            lines.append(f"- **{vote.value}**: {count}")
        lines.extend(
            [
                "",
                f"**Consensus**: {'Reached ✅' if self.consensus_reached else 'Not Reached ⚠️'}",
                "",
                "## Decision",
                self.decision,
                "",
                f"**Rationale**: {self.decision_rationale}",
                "",
            ]
        )

        if self.dissenting_views:
            lines.append("## Dissenting Views")
            for d in self.dissenting_views:
                lines.append(f"- {d}")
            lines.append("")

        lines.extend(
            [
                "## Action Items",
            ]
        )
        for ai in self.action_items:
            lines.append(f"- [ ] {ai}")

        lines.extend(
            [
                "",
                "## Items to Monitor",
            ]
        )
        for item in self.items_to_monitor:
            lines.append(f"- {item}")

        lines.extend(
            [
                "",
                f"**Next Meeting**: {self.next_meeting or 'TBD'}",
                "",
                "---",
                "*Minutes generated by Macro Research Agent Investment Committee (V8.1)*",
            ]
        )

        return "\n".join(lines)


class InvestmentCommittee:
    """Convene and run an investment committee debate.

    The committee brings together multiple macro perspectives to debate
    positioning changes. Each member has a distinct investment philosophy.
    """

    # Member profiles with their philosophies
    MEMBERS = {
        CommitteeRole.MACRO_TRADER: {
            "name": "PTJ Macro Trader",
            "philosophy": """
Focus on momentum, technical levels, and positioning extremes.
Key questions: Where is the pain trade? What's the crowded position?
When does the trend break? The last 20% of a move is always the hardest.
""",
            "default_vote": Vote.HOLD,
        },
        CommitteeRole.SYSTEMATIC: {
            "name": "Dalio Systematic",
            "philosophy": """
Focus on long-term debt cycles, productivity, and political economy.
Key questions: Where are we in the long-term debt cycle?
What's the productivity trend? Are we in a beautiful deleveraging?
Diversification is the holy grail.
""",
            "default_vote": Vote.HOLD,
        },
        CommitteeRole.REFLEXIVITY: {
            "name": "Soros Reflexivity",
            "philosophy": """
Focus on feedback loops between fundamentals and market prices.
Key questions: Is there a reflexivity loop? Is the market affecting
fundamentals? Is this a boom-bust process? What's the far-from-equilibrium state?
""",
            "default_vote": Vote.HOLD,
        },
        CommitteeRole.RISK_PARITY: {
            "name": "Bridgewater Risk Parity",
            "philosophy": """
Focus on balanced risk allocation across economic environments.
Key questions: Are risks properly balanced? What environment are we in?
Is growth rising or falling? Is inflation rising or falling?
""",
            "default_vote": Vote.HOLD,
        },
        CommitteeRole.PORTFOLIO_MANAGER: {
            "name": "Macro Portfolio Manager",
            "philosophy": """
Focus on practical implementation, liquidity, and sizing.
Key questions: Can we actually put this trade on? What's the cost?
What's the liquidity? How does this fit with current positions?
""",
            "default_vote": Vote.HOLD,
        },
        CommitteeRole.RISK_MANAGER: {
            "name": "Chief Risk Officer",
            "philosophy": """
Focus on downside risk, correlation shifts, and tail events.
Key questions: What's the worst case? Are correlations shifting?
What's the VaR impact? What's the stress test result?
""",
            "default_vote": Vote.HOLD,
        },
    }

    def __init__(self):
        self.meetings: list[MeetingMinutes] = []
        self._last_decision: str | None = None

    def convene(
        self,
        topic: str,
        agenda: str = "",
        market_context: str = "",
        current_positioning: str = "",
        research_data: dict | None = None,
        beliefs: list[dict] | None = None,
        narratives: list[str] | None = None,
        risks: list[dict] | None = None,
    ) -> MeetingMinutes:
        """Convene an investment committee meeting."""

        minutes = MeetingMinutes(
            topic=topic,
            agenda=agenda or f"Review positioning on: {topic}",
            market_context=market_context or "Current market conditions under review.",
            current_positioning=current_positioning or "Positioning to be determined.",
        )

        # Each member provides their perspective
        for role in [
            CommitteeRole.MACRO_TRADER,
            CommitteeRole.SYSTEMATIC,
            CommitteeRole.REFLEXIVITY,
            CommitteeRole.RISK_PARITY,
            CommitteeRole.PORTFOLIO_MANAGER,
            CommitteeRole.RISK_MANAGER,
        ]:
            stmt = self._generate_member_view(
                role, topic, research_data, beliefs, narratives, risks
            )
            minutes.statements.append(stmt)
            minutes.votes[stmt.vote] = minutes.votes.get(stmt.vote, 0) + 1

        # Tally and decide
        minutes.consensus_reached = self._check_consensus(minutes.votes)
        minutes.decision, minutes.decision_rationale = self._synthesize_decision(
            minutes.statements, minutes.votes
        )

        # Action items and monitoring
        minutes.action_items = self._generate_action_items(minutes.decision)
        minutes.items_to_monitor = self._extract_monitoring_items(minutes.statements)
        minutes.dissenting_views = self._extract_dissents(minutes.statements)

        self.meetings.append(minutes)
        self._last_decision = minutes.decision

        return minutes

    def get_last_decision(self) -> str | None:
        return self._last_decision

    def get_last_meeting(self) -> MeetingMinutes | None:
        if self.meetings:
            return self.meetings[-1]
        return None

    def get_meeting_history(self) -> list[MeetingMinutes]:
        return list(self.meetings)

    def get_stats(self) -> dict:
        if not self.meetings:
            return {"total_meetings": 0}

        decisions = [m.decision for m in self.meetings]
        consensus_rate = sum(1 for m in self.meetings if m.consensus_reached) / len(self.meetings)

        return {
            "total_meetings": len(self.meetings),
            "consensus_rate": consensus_rate,
            "recent_decisions": decisions[-5:],
            "last_decision": self._last_decision,
        }

    # ── Internal ─────────────────────────────────────────────────────────

    def _generate_member_view(
        self,
        role: CommitteeRole,
        topic: str,
        research_data: dict | None,
        beliefs: list[dict] | None,
        narratives: list[str] | None,
        risks: list[dict] | None,
    ) -> CommitteeStatement:
        """Generate a committee member's perspective."""
        member_info = self.MEMBERS.get(role, {"name": role.value})

        # Generate role-specific analysis
        if role == CommitteeRole.MACRO_TRADER:
            statement = self._ptj_view(topic, research_data, beliefs)
            vote = self._ptj_vote(beliefs, narratives)
        elif role == CommitteeRole.SYSTEMATIC:
            statement = self._dalio_view(topic, research_data, beliefs)
            vote = Vote.HOLD
        elif role == CommitteeRole.REFLEXIVITY:
            statement = self._soros_view(topic, research_data, narratives)
            vote = Vote.HOLD
        elif role == CommitteeRole.RISK_PARITY:
            statement = self._bridgewater_view(topic, research_data)
            vote = Vote.HOLD
        elif role == CommitteeRole.PORTFOLIO_MANAGER:
            statement = self._pm_view(topic, research_data, beliefs)
            vote = Vote.HOLD
        elif role == CommitteeRole.RISK_MANAGER:
            statement = self._risk_view(topic, risks)
            vote = Vote.HEDGE
        else:
            statement = f"Analysis of {topic} from {role.value} perspective."
            vote = Vote.HOLD

        return CommitteeStatement(
            role=role,
            member_name=member_info["name"],
            statement=statement,
            vote=vote,
            conviction=0.6,
            key_points=[f"Analysis from {role.value} framework applied to {topic}"],
            evidence_cited=[],
            risks_highlighted=[],
        )

    def _ptj_view(self, topic: str, research: dict | None, beliefs: list[dict] | None) -> str:
        return (
            f"From a macro trader perspective on {topic}: "
            f"The key question is momentum and positioning. "
            f"What is the trend, where is the pain trade, and what is the crowded position? "
            f"The last part of any move is always the hardest. "
            f"We should focus on the asymmetric payoff — where is the 5:1 risk/reward?"
        )

    def _dalio_view(self, topic: str, research: dict | None, beliefs: list[dict] | None) -> str:
        return (
            f"From a systematic/cyclical framework on {topic}: "
            f"We need to understand where we are in the long-term debt cycle, "
            f"the business cycle, and the political cycle. "
            f"Productivity growth and debt service are the key structural drivers. "
            f"Diversification across uncorrelated return streams is essential."
        )

    def _soros_view(self, topic: str, research: dict | None, narratives: list[str] | None) -> str:
        return (
            f"From a reflexivity perspective on {topic}: "
            f"The critical question is whether market prices are affecting fundamentals. "
            f"Is there a self-reinforcing feedback loop? "
            f"Boom-bust processes begin with a trend that becomes self-validating, "
            f"then eventually unsustainable. Where are we in that cycle?"
        )

    def _bridgewater_view(self, topic: str, research: dict | None) -> str:
        return (
            f"From an all-weather risk parity perspective on {topic}: "
            f"The key framework is growth above/below expectations and inflation above/below. "
            f"Each quadrant favors different assets. "
            f"We need balanced risk allocation across economic environments, "
            f"not concentrated bets on a single outcome."
        )

    def _pm_view(self, topic: str, research: dict | None, beliefs: list[dict] | None) -> str:
        return (
            f"From a practical PM perspective on {topic}: "
            f"Implementation matters. Can we size this appropriately? "
            f"What's the liquidity and transaction cost? "
            f"How does this interact with the existing portfolio? "
            f"What's the correlation matrix in stress scenarios?"
        )

    def _risk_view(self, topic: str, risks: list[dict] | None) -> str:
        risk_count = len(risks) if risks else 0
        return (
            f"From a risk management perspective on {topic}: "
            f"We have identified {risk_count} key risks. "
            f"The primary concern is asymmetric downside — "
            f"what scenario causes the most damage? "
            f"Correlation assumptions break under stress. "
            f"We should size for the worst case, not the base case."
        )

    def _ptj_vote(self, beliefs: list[dict] | None, narratives: list[str] | None) -> Vote:
        # PTJ: vote based on momentum/trend signals
        return Vote.HOLD  # Default conservative

    def _check_consensus(self, votes: dict[Vote, int]) -> bool:
        total = sum(votes.values())
        if total == 0:
            return False
        max_votes = max(votes.values())
        return max_votes / total >= 0.67  # 2/3 majority

    def _synthesize_decision(
        self, statements: list[CommitteeStatement], votes: dict[Vote, int]
    ) -> tuple[str, str]:
        """Synthesize committee decision from all perspectives."""
        total = sum(votes.values())
        if total == 0:
            return "No decision reached", "Insufficient votes."

        # Find plurality vote
        winning_vote = max(votes, key=votes.get)
        majority_pct = votes[winning_vote] / total

        if majority_pct >= 0.67:
            decision = f"Committee recommends: {winning_vote.value.upper()} position"
            rationale = (
                f"Strong consensus ({majority_pct:.0%}) with {votes[winning_vote]}/{total} votes."
            )
        elif majority_pct >= 0.5:
            decision = f"Committee leans: {winning_vote.value.upper()}"
            rationale = f"Simple majority ({majority_pct:.0%}), close monitoring warranted."
        else:
            decision = "Committee split — maintain current position"
            rationale = (
                f"No majority ({majority_pct:.0%}). Chair holds decision pending further evidence."
            )

        return decision, rationale

    def _generate_action_items(self, decision: str) -> list[str]:
        items = [
            "Review risk limits and position sizing",
            "Monitor key data releases for invalidation signals",
            "Update stop levels based on committee discussion",
        ]
        if "INCREASE" in decision:
            items.insert(0, "Prepare increase orders with staggered entry")
        elif "DECREASE" in decision:
            items.insert(0, "Plan reduction schedule with market impact analysis")
        elif "HEDGE" in decision:
            items.insert(0, "Evaluate hedging instruments and costs")
        return items

    def _extract_monitoring_items(self, statements: list[CommitteeStatement]) -> list[str]:
        items = []
        for stmt in statements:
            if stmt.risks_highlighted:
                items.extend(stmt.risks_highlighted)
        if not items:
            items = [
                "Key economic data releases",
                "Central bank communications",
                "Market technical levels",
                "Positioning and flow data",
                "Correlation regime shifts",
            ]
        return list(set(items))[:8]

    def _extract_dissents(self, statements: list[CommitteeStatement]) -> list[str]:
        dissents = []
        winning = self._get_winning_vote(statements)

        for stmt in statements:
            if stmt.vote != winning:
                dissents.append(
                    f"{stmt.member_name} dissents ({stmt.vote.value}): {stmt.statement[:150]}"
                )
        return dissents[:3]

    def _get_winning_vote(self, statements: list[CommitteeStatement]) -> Vote:
        vote_counts: dict[Vote, int] = {}
        for s in statements:
            vote_counts[s.vote] = vote_counts.get(s.vote, 0) + 1
        if vote_counts:
            return max(vote_counts, key=vote_counts.get)
        return Vote.HOLD
