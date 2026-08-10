"""MarketSource — Domain model for external data source definition.

Represents the capabilities and configuration of a market data provider
(e.g., Yahoo Finance, FRED, Bloomberg, Wind) as a domain entity.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Type of data source connection."""

    REST_API = "rest_api"
    WEBSOCKET = "websocket"
    LIBRARY = "library"       # e.g. yfinance
    FILE = "file"              # CSV / Parquet import
    SDK = "sdk"                # Bloomberg API, Wind SDK


class AuthType(str, Enum):
    """Authentication method."""

    NONE = "none"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    CERTIFICATE = "certificate"


class MarketSource(BaseModel):
    """Defines a market data provider and its configuration.

    Examples:
        >>> yahoo = MarketSource(
        ...     name="Yahoo",
        ...     source_type=SourceType.LIBRARY,
        ...     library_name="yfinance",
        ...     enabled=True,
        ... )
    """

    name: str = Field(..., min_length=1, description="Unique source name, e.g. 'Yahoo', 'FRED'")
    source_type: SourceType = Field(..., description="Connection type")
    base_url: Optional[str] = Field(default=None, description="API base URL (for REST sources)")
    library_name: Optional[str] = Field(default=None, description="Python library name (for library sources)")
    auth_type: AuthType = Field(default=AuthType.NONE, description="Authentication method")
    auth_env_var: Optional[str] = Field(default=None, description="Env var holding credential")
    rate_limit_rpm: int = Field(default=60, ge=1, description="Max requests per minute")
    enabled: bool = Field(default=True, description="Whether this source is active")
    description: Optional[str] = Field(default=None, description="Free-text description")

    model_config = {"frozen": True}

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"<MarketSource {self.name} [{self.source_type.value}] {status}>"
