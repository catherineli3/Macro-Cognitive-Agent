"""V6.1 Event Scheduler — Smart scheduling for information source polling.

Determines when each source should be checked based on:
- Release calendars (economic data, FOMC meetings, earnings)
- Expected event frequency per source
- Market hours / timezone awareness
- Critical event windows
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from src.live_intelligence.schemas import SourceType


class ScheduleFrequency(str, Enum):
    """How often to poll a source."""

    CONTINUOUS = "continuous"  # Real-time streaming
    EVERY_MINUTE = "every_minute"
    EVERY_5_MINUTES = "every_5_minutes"
    EVERY_15_MINUTES = "every_15_minutes"
    EVERY_HOUR = "every_hour"
    EVERY_4_HOURS = "every_4_hours"
    EVERY_DAY = "every_day"
    EVERY_WEEK = "every_week"
    ON_EVENT = "on_event"  # Only on known release time
    ON_DEMAND = "on_demand"  # Manual trigger


@dataclass
class SourceSchedule:
    """Schedule configuration for a single source."""

    source: SourceType
    source_name: str
    frequency: ScheduleFrequency = ScheduleFrequency.EVERY_DAY

    # Active windows (UTC hours)
    active_start_hour: int = 0
    active_end_hour: int = 23

    # Trading hours aware
    market_hours_only: bool = False
    timezone_offset: int = 0  # Hours from UTC

    # Release calendar
    known_release_times: list[str] = field(default_factory=list)
    # ISO format: ["2026-07-22T12:30:00Z", ...]

    # Priority
    priority: int = 1  # Higher = check first
    requires_immediate_processing: bool = False

    # State
    last_polled: str = ""
    next_poll_due: str = ""
    consecutive_failures: int = 0
    is_active: bool = True


class EventScheduler:
    """Smart scheduler for multi-source information polling.

    Knows when to check each source for new information:
    - Economic calendars (BLS 8:30 ET, FOMC 2pm ET, etc.)
    - Central bank schedules
    - Market hours
    - Breaking news windows
    """

    # Default schedules for each source type
    DEFAULT_SCHEDULES: dict[SourceType, SourceSchedule] = {
        # Wire services — high frequency
        SourceType.REUTERS: SourceSchedule(
            source=SourceType.REUTERS,
            source_name="Reuters",
            frequency=ScheduleFrequency.EVERY_MINUTE,
            priority=10,
            requires_immediate_processing=True,
        ),
        SourceType.BLOOMBERG: SourceSchedule(
            source=SourceType.BLOOMBERG,
            source_name="Bloomberg Terminal",
            frequency=ScheduleFrequency.EVERY_MINUTE,
            priority=10,
            requires_immediate_processing=True,
        ),
        # Central bank speeches — event-driven with monitoring
        SourceType.FED_SPEECH: SourceSchedule(
            source=SourceType.FED_SPEECH,
            source_name="Fed Speeches",
            frequency=ScheduleFrequency.EVERY_15_MINUTES,
            active_start_hour=13,
            active_end_hour=21,  # US business hours UTC
            priority=8,
        ),
        SourceType.ECB_SPEECH: SourceSchedule(
            source=SourceType.ECB_SPEECH,
            source_name="ECB Speeches",
            frequency=ScheduleFrequency.EVERY_15_MINUTES,
            active_start_hour=7,
            active_end_hour=17,  # European hours UTC
            priority=7,
        ),
        SourceType.BOJ_SPEECH: SourceSchedule(
            source=SourceType.BOJ_SPEECH,
            source_name="BOJ Speeches",
            frequency=ScheduleFrequency.EVERY_HOUR,
            active_start_hour=0,
            active_end_hour=8,  # Japan hours UTC
            priority=6,
        ),
        # Policy statements — event-driven
        SourceType.FOMC_STATEMENT: SourceSchedule(
            source=SourceType.FOMC_STATEMENT,
            source_name="FOMC Statements",
            frequency=ScheduleFrequency.ON_EVENT,
            priority=10,
            requires_immediate_processing=True,
        ),
        SourceType.FOMC_MINUTES: SourceSchedule(
            source=SourceType.FOMC_MINUTES,
            source_name="FOMC Minutes",
            frequency=ScheduleFrequency.ON_EVENT,
            priority=8,
        ),
        # Economic data — scheduled releases
        SourceType.BLS: SourceSchedule(
            source=SourceType.BLS,
            source_name="Bureau of Labor Statistics",
            frequency=ScheduleFrequency.ON_EVENT,
            priority=9,
            requires_immediate_processing=True,
        ),
        SourceType.BEA: SourceSchedule(
            source=SourceType.BEA,
            source_name="Bureau of Economic Analysis",
            frequency=ScheduleFrequency.ON_EVENT,
            priority=7,
        ),
        # Market data — continuous during trading hours
        SourceType.ETF_FLOW: SourceSchedule(
            source=SourceType.ETF_FLOW,
            source_name="ETF Flow Monitor",
            frequency=ScheduleFrequency.EVERY_4_HOURS,
            priority=4,
        ),
        SourceType.CME_FEDWATCH: SourceSchedule(
            source=SourceType.CME_FEDWATCH,
            source_name="CME FedWatch",
            frequency=ScheduleFrequency.EVERY_HOUR,
            priority=6,
        ),
        SourceType.INSTITUTIONAL_13F: SourceSchedule(
            source=SourceType.INSTITUTIONAL_13F,
            source_name="13F Filings",
            frequency=ScheduleFrequency.EVERY_DAY,
            priority=3,
        ),
        # Government
        SourceType.TREASURY: SourceSchedule(
            source=SourceType.TREASURY,
            source_name="US Treasury",
            frequency=ScheduleFrequency.EVERY_DAY,
            priority=5,
        ),
        # International organizations
        SourceType.IMF: SourceSchedule(
            source=SourceType.IMF,
            source_name="IMF",
            frequency=ScheduleFrequency.EVERY_WEEK,
            priority=2,
        ),
        SourceType.BIS: SourceSchedule(
            source=SourceType.BIS,
            source_name="BIS",
            frequency=ScheduleFrequency.EVERY_WEEK,
            priority=2,
        ),
        SourceType.WORLD_BANK: SourceSchedule(
            source=SourceType.WORLD_BANK,
            source_name="World Bank",
            frequency=ScheduleFrequency.EVERY_WEEK,
            priority=1,
        ),
    }

    def __init__(self, custom_schedules: dict[SourceType, SourceSchedule] | None = None):
        self.schedules: dict[SourceType, SourceSchedule] = dict(self.DEFAULT_SCHEDULES)
        if custom_schedules:
            self.schedules.update(custom_schedules)

        self._poll_history: list[tuple[str, str, str]] = []  # (ts, source, result)
        self._known_release_times: list[str] = []  # Key dates we know about

    def get_due_sources(self, current_time: datetime | None = None) -> list[SourceType]:
        """Return list of sources that should be polled now."""
        now = current_time or datetime.now(UTC)
        due = []

        for source, schedule in self.schedules.items():
            if not schedule.is_active:
                continue

            # Check active window
            if not self._is_in_active_window(schedule, now):
                continue

            # Check if it's time to poll
            if self._is_due(schedule, now):
                due.append(source)

        # Sort by priority (highest first)
        due.sort(key=lambda s: self.schedules[s].priority, reverse=True)
        return due

    def record_poll(
        self, source: SourceType, success: bool = True, poll_time: datetime | None = None
    ):
        """Record a completed poll attempt."""
        now = poll_time or datetime.now(UTC)

        if source in self.schedules:
            schedule = self.schedules[source]
            schedule.last_polled = now.isoformat()

            if not success:
                schedule.consecutive_failures += 1
            else:
                schedule.consecutive_failures = 0

            # Set next poll time based on frequency
            schedule.next_poll_due = self._compute_next_poll(schedule, now).isoformat()

        self._poll_history.append(
            (
                now.isoformat(),
                source.value if isinstance(source, SourceType) else str(source),
                "success" if success else "failed",
            )
        )

        # Trim history to last 1000
        if len(self._poll_history) > 1000:
            self._poll_history = self._poll_history[-1000:]

    def add_release_event(self, source: SourceType, release_time: str, description: str = ""):
        """Register a known upcoming release (e.g., CPI at 8:30 ET on July 12)."""
        if source in self.schedules:
            self.schedules[source].known_release_times.append(release_time)
        self._known_release_times.append(f"{source.value}:{release_time}:{description}")

    def get_upcoming_releases(self, lookahead_hours: int = 24) -> list[dict]:
        """Get all upcoming scheduled releases within the lookahead window."""
        now = datetime.now(UTC)
        cutoff = now + timedelta(hours=lookahead_hours)
        upcoming = []

        for source, schedule in self.schedules.items():
            for rt in schedule.known_release_times:
                try:
                    rt_dt = datetime.fromisoformat(rt.replace("Z", "+00:00"))
                    if now <= rt_dt <= cutoff:
                        upcoming.append(
                            {
                                "source": source.value,
                                "source_name": schedule.source_name,
                                "release_time": rt,
                                "priority": schedule.priority,
                            }
                        )
                except (ValueError, TypeError):
                    continue

        upcoming.sort(key=lambda x: x["release_time"])
        return upcoming

    def get_source_status(self) -> dict[str, dict]:
        """Get status for all sources."""
        return {
            source.value if isinstance(source, SourceType) else str(source): {
                "frequency": schedule.frequency.value,
                "active": schedule.is_active,
                "last_polled": schedule.last_polled,
                "next_poll_due": schedule.next_poll_due,
                "failures": schedule.consecutive_failures,
                "priority": schedule.priority,
            }
            for source, schedule in self.schedules.items()
        }

    def get_health(self) -> dict:
        """Get scheduler health metrics."""
        total = len(self.schedules)
        active = sum(1 for s in self.schedules.values() if s.is_active)
        failing = sum(1 for s in self.schedules.values() if s.consecutive_failures > 3)

        return {
            "total_sources": total,
            "active_sources": active,
            "failing_sources": failing,
            "is_healthy": failing < total * 0.3,
            "upcoming_releases": len(self.get_upcoming_releases(24)),
        }

    # ── Internal Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _is_in_active_window(schedule: SourceSchedule, now: datetime) -> bool:
        """Check if current time is within the source's active window."""
        hour = now.hour
        if schedule.active_start_hour <= schedule.active_end_hour:
            return schedule.active_start_hour <= hour <= schedule.active_end_hour
        else:
            # Wraps around midnight (e.g., 22–06)
            return hour >= schedule.active_start_hour or hour <= schedule.active_end_hour

    @staticmethod
    def _is_due(schedule: SourceSchedule, now: datetime) -> bool:
        """Check if source is due for polling."""
        if schedule.frequency == ScheduleFrequency.CONTINUOUS:
            return True

        if not schedule.last_polled:
            return True  # Never polled

        try:
            last = datetime.fromisoformat(schedule.last_polled.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return True

        # Check frequency interval
        interval_map = {
            ScheduleFrequency.EVERY_MINUTE: timedelta(minutes=1),
            ScheduleFrequency.EVERY_5_MINUTES: timedelta(minutes=5),
            ScheduleFrequency.EVERY_15_MINUTES: timedelta(minutes=15),
            ScheduleFrequency.EVERY_HOUR: timedelta(hours=1),
            ScheduleFrequency.EVERY_4_HOURS: timedelta(hours=4),
            ScheduleFrequency.EVERY_DAY: timedelta(days=1),
            ScheduleFrequency.EVERY_WEEK: timedelta(weeks=1),
        }

        interval = interval_map.get(schedule.frequency)
        if interval and now - last >= interval:
            return True

        # Check known release times
        for rt in schedule.known_release_times:
            try:
                rt_dt = datetime.fromisoformat(rt.replace("Z", "+00:00"))
                # Due if within 5 minutes of release
                if abs((now - rt_dt).total_seconds()) < 300:
                    return True
            except (ValueError, TypeError):
                pass

        return False

    @staticmethod
    def _compute_next_poll(schedule: SourceSchedule, now: datetime) -> datetime:
        """Compute the next poll time based on frequency."""
        interval_map = {
            ScheduleFrequency.EVERY_MINUTE: timedelta(minutes=1),
            ScheduleFrequency.EVERY_5_MINUTES: timedelta(minutes=5),
            ScheduleFrequency.EVERY_15_MINUTES: timedelta(minutes=15),
            ScheduleFrequency.EVERY_HOUR: timedelta(hours=1),
            ScheduleFrequency.EVERY_4_HOURS: timedelta(hours=4),
            ScheduleFrequency.EVERY_DAY: timedelta(days=1),
            ScheduleFrequency.EVERY_WEEK: timedelta(weeks=1),
        }
        interval = interval_map.get(schedule.frequency, timedelta(days=1))
        return now + interval


# ── Key Economic Release Calendar ────────────────────────────────────────────

KEY_US_RELEASES = {
    "CPI": {
        "source": SourceType.BLS,
        "time_et": "08:30",
        "frequency": "monthly",
        "importance": "critical",
    },
    "PPI": {
        "source": SourceType.BLS,
        "time_et": "08:30",
        "frequency": "monthly",
        "importance": "high",
    },
    "NFP": {
        "source": SourceType.BLS,
        "time_et": "08:30",
        "frequency": "monthly",
        "importance": "critical",
    },
    "Unemployment Rate": {
        "source": SourceType.BLS,
        "time_et": "08:30",
        "frequency": "monthly",
        "importance": "high",
    },
    "GDP (Advance)": {
        "source": SourceType.BEA,
        "time_et": "08:30",
        "frequency": "quarterly",
        "importance": "critical",
    },
    "PCE": {
        "source": SourceType.BEA,
        "time_et": "08:30",
        "frequency": "monthly",
        "importance": "high",
    },
    "Retail Sales": {
        "source": SourceType.BEA,
        "time_et": "08:30",
        "frequency": "monthly",
        "importance": "high",
    },
    "ISM Manufacturing": {
        "source": SourceType.BLS,
        "time_et": "10:00",
        "frequency": "monthly",
        "importance": "high",
    },
    "FOMC Decision": {
        "source": SourceType.FOMC_STATEMENT,
        "time_et": "14:00",
        "frequency": "8x/year",
        "importance": "critical",
    },
    "FOMC Minutes": {
        "source": SourceType.FOMC_MINUTES,
        "time_et": "14:00",
        "frequency": "8x/year",
        "importance": "medium",
    },
}

KEY_GLOBAL_RELEASES = {
    "ECB Decision": {
        "source": SourceType.ECB_SPEECH,
        "time_utc": "12:15",
        "frequency": "8x/year",
        "importance": "critical",
    },
    "BOJ Decision": {
        "source": SourceType.BOJ_SPEECH,
        "time_utc": "03:00",
        "frequency": "8x/year",
        "importance": "critical",
    },
    "China GDP": {
        "source": SourceType.PBOC,
        "time_utc": "02:00",
        "frequency": "quarterly",
        "importance": "high",
    },
    "China CPI": {
        "source": SourceType.PBOC,
        "time_utc": "01:30",
        "frequency": "monthly",
        "importance": "medium",
    },
}
