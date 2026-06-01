"""Angel One SDK wrapper tests."""

from __future__ import annotations

import logging

from app.integrations.angel_one.sdk import _SensitiveSDKLogFilter


def test_sensitive_sdk_log_filter_drops_secret_bearing_request_records() -> None:
    """SDK request dumps include credentials and must never reach handlers."""
    log_filter = _SensitiveSDKLogFilter()
    sensitive_record = logging.LogRecord(
        name="logzero-default",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Error occurred while making a POST request with headers and token",
        args=(),
        exc_info=None,
    )
    safe_record = logging.LogRecord(
        name="logzero-default",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Angel One request failed.",
        args=(),
        exc_info=None,
    )

    assert log_filter.filter(sensitive_record) is False
    assert log_filter.filter(safe_record) is True
