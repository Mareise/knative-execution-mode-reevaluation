import os
from collections import namedtuple
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from constants import LATENCY_QUERY_THRESHOLD_NAME, REQUEST_RATE_QUERY_THRESHOLD_NAME

WINDOW_MINUTES = int(os.environ.get("WINDOW_MINUTES", "30"))
LONG_INTERVAL_MULTIPLIER = int(os.environ.get("LONG_INTERVAL_MULTIPLIER", "50"))


class QueryNames(Enum):
    LATENCY_AVG = "latency_avg"
    REQUEST_RATE_long = "REQUEST_RATE_long"
    REQUEST_RATE_short = "REQUEST_RATE_short"
    LATENCY_P95_long = "LATENCY_P95_long"
    LATENCY_P95_short = "LATENCY_P95_short"


LOW_REQUEST_RATE_SWITCHING_MINUTES = os.environ.get(
    "LOW_REQUEST_RATE_SWITCHING_MINUTES", "30")

QUERIES = {
    # QueryNames.LATENCY_AVG: lambda revision_name, window="5m": (
    #     f'rate(activator_request_latencies_sum{{revision_name="{revision_name}"}}[{window}]) / '
    #     f'rate(activator_request_latencies_count{{revision_name="{revision_name}"}}[{window}])'
    # ),
    QueryNames.LATENCY_P95_long: lambda revision_name: (
        f'histogram_quantile(0.95, rate(activator_request_latencies_bucket{{revision_name="{revision_name}"}}[{WINDOW_MINUTES * LONG_INTERVAL_MULTIPLIER}m])) '
    ),
    QueryNames.LATENCY_P95_short: lambda revision_name: (
        f'histogram_quantile(0.95, rate(activator_request_latencies_bucket{{revision_name="{revision_name}"}}[{WINDOW_MINUTES}m]))'
    ),
    QueryNames.REQUEST_RATE_long: lambda revision_name: (
        f'rate(activator_request_count{{revision_name="{revision_name}"}}[{LOW_REQUEST_RATE_SWITCHING_MINUTES}m])'
    ),
    QueryNames.REQUEST_RATE_short: lambda revision_name: (
        f'rate(activator_request_count{{revision_name="{revision_name}"}}[1m])'
    ),
}


@dataclass
class QueryThreshold:
    upper_bound: Optional[int] = None
    upper_bound_when_low_request_rate: Optional[int] = None
    lower_bound: Optional[float] = None
    performance_change_gap: Optional[int] = None


QUERY_THRESHOLDS = {
    QueryNames.LATENCY_AVG:
        QueryThreshold(
            upper_bound=int(os.environ.get("THRESHOLD_LATENCY_UPPER", "1000")),
            upper_bound_when_low_request_rate=int(
                os.environ.get("THRESHOLD_LATENCY_UPPER_WHEN_LOW_REQUEST_RATE", "2000")
            ),
            performance_change_gap=int(os.environ.get("THRESHOLD_LATENCY_PERFORMANCE_CHANGE_GAP", "200"))
        ),
    LATENCY_QUERY_THRESHOLD_NAME:
        QueryThreshold(
            upper_bound=int(os.environ.get("THRESHOLD_LATENCY_UPPER", "1000")),
            upper_bound_when_low_request_rate=int(
                os.environ.get("THRESHOLD_LATENCY_UPPER_WHEN_LOW_REQUEST_RATE", "2000")
            ),
            performance_change_gap=int(os.environ.get("THRESHOLD_LATENCY_PERFORMANCE_CHANGE_GAP", "200"))
        ),
    QueryNames.REQUEST_RATE_long:
        QueryThreshold(
            lower_bound=float(os.environ.get("THRESHOLD_REQUEST_RATE_LOWER_BOUND", "0.01")),
        ),
    QueryNames.REQUEST_RATE_short:
        QueryThreshold(
            lower_bound=float(os.environ.get("THRESHOLD_REQUEST_RATE_COLD_START_MITIGATION", "0.2")),
        ),
}
