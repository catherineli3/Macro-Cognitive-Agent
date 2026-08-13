"""MacroIndicator — Domain model for a macro-economic indicator definition.

This is a metadata/definition entity, NOT an observation value.
For observation data, see schemas/macro_data.py → MacroDataSchema.
"""

from enum import Enum

from pydantic import BaseModel, Field


class HypothesisDimension(str, Enum):
    """Macro hypothesis dimensions for automated categorization.

    Eliminates hardcoded mappings in Analyzer (Sprint 3+).
    Every indicator belongs to exactly one dimension.
    """

    LIQUIDITY = "Liquidity"  # Monetary conditions: DXY, Fed Funds, US10Y
    CREDIT = "Credit"  # Credit markets: HYG, IG Spread, CDX
    GROWTH = "Growth"  # Real economy: GDP, PMI, Industrial Production
    RISK_APPETITE = "Risk_Appetite"  # Market sentiment: VIX, Copper/Gold ratio, EM Flows
    INFLATION = "Inflation"  # Price levels: CPI, PPI, Breakevens
    AI_CAPEX = "AI_Capex"  # AI investment cycle: NVDA, TSMC, ASML, SMH
    DOLLAR = "Dollar"  # USD strength: DXY, rate differentials
    EMPLOYMENT = "Employment"  # Labor market: Claims, Payrolls, Participation
    POLICY = "Policy"  # Monetary policy: Fed stance, rate expectations


class Frequency(str, Enum):
    """Observation frequency for an indicator."""

    INTRADAY = "Intraday"
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    ANNUAL = "Annual"


class MacroIndicator(BaseModel):
    """Defines the metadata of a macro-economic indicator.

    This is the canonical definition used across the system.
    Each indicator is registered once; observations flow through MacroDataSchema.

    Examples:
        >>> dxy = MacroIndicator(
        ...     symbol="DXY",
        ...     name="US Dollar Index",
        ...     category="Currency",
        ...     frequency=Frequency.DAILY,
        ...     unit="Index",
        ...     source="Yahoo",
        ...     hypothesis_dimension=HypothesisDimension.LIQUIDITY,
        ... )
    """

    symbol: str = Field(
        ..., min_length=1, max_length=20, description="Unique ticker/series identifier"
    )
    name: str = Field(..., min_length=1, description="Human-readable name")
    category: str = Field(
        ..., description="Asset class category, e.g. 'Currency', 'Rates', 'Commodities'"
    )
    frequency: Frequency = Field(..., description="Observation frequency")
    unit: str = Field(default="Index", description="Unit of measurement")
    source: str = Field(default="Yahoo", description="Primary data source")
    hypothesis_dimension: HypothesisDimension = Field(
        ...,
        description="Macro hypothesis dimension — prevents hardcoded mappings in Analyzer",
    )
    currency: str = Field(default="USD", description="Currency denomination")
    description: str | None = Field(default=None, description="Free-text description")
    enabled: bool = Field(default=True, description="Whether this indicator is actively collected")

    model_config = {"frozen": True}  # Immutable — indicators don't change at runtime

    def __repr__(self) -> str:
        return f"<MacroIndicator {self.symbol} [{self.hypothesis_dimension.value}]>"
