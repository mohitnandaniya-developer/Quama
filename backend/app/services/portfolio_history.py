"""Shared portfolio-history range definitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

_ALL_HISTORY_START_YEAR = 2000
_PERIOD_DELTAS = {
    "1H": timedelta(hours=1),
    "1D": timedelta(days=1),
    "1M": timedelta(days=30),
    "6M": timedelta(days=183),
    "1Y": timedelta(days=365),
    "3Y": timedelta(days=365 * 3),
    "5Y": timedelta(days=365 * 5),
}
SUPPORTED_PORTFOLIO_HISTORY_PERIODS = (*_PERIOD_DELTAS, "ALL")


@dataclass(frozen=True)
class PortfolioHistoryWindow:
    """Normalized range requested from a broker's candle API."""

    period: str
    start_at: datetime
    end_at: datetime


def resolve_portfolio_history_window(
    period: str,
    *,
    end_at: datetime,
) -> PortfolioHistoryWindow:
    """Normalize one UI range into concrete candle API timestamps."""
    normalized_period = period.strip().upper()
    if normalized_period not in SUPPORTED_PORTFOLIO_HISTORY_PERIODS:
        supported = ", ".join(SUPPORTED_PORTFOLIO_HISTORY_PERIODS)
        raise ValueError(
            f"Unsupported portfolio history period. Use one of: {supported}."
        )

    if normalized_period == "ALL":
        start_at = datetime(_ALL_HISTORY_START_YEAR, 1, 1, tzinfo=end_at.tzinfo)
    else:
        start_at = end_at - _PERIOD_DELTAS[normalized_period]

    return PortfolioHistoryWindow(
        period=normalized_period,
        start_at=start_at,
        end_at=end_at,
    )
