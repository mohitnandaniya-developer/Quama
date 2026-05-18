"""Portfolio history schema."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class PortfolioHistoryResponse(BaseModel):
    """Historical portfolio values for one selected period."""

    model_config = ConfigDict(extra="forbid")

    period: str
    history: list[dict[str, Any]]
