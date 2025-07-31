import os
from collections import namedtuple
from enum import Enum

WINDOW_MINUTES = int(os.environ.get("WINDOW_MINUTES", "30"))
LONG_INTERVAL_MULTIPLIER = int(os.environ.get("LONG_INTERVAL_MULTIPLIER", "50"))


class QueryNames(Enum):
    LATENCY_AVG = "latency_avg"
    REQUEST_RATE = "request_rate"
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
        f'histogram_quantile(0.95, rate(activator_request_latencies_bucket{{revision_name="{revision_name}"}}[{WINDOW_MINUTES}m])) '
        f'unless sum(rate(activator_request_count{{revision_name="{revision_name}"}}[1m])) < 10'
    ),
    QueryNames.REQUEST_RATE: lambda revision_name: (
        f'rate(activator_request_count{{revision_name="{revision_name}"}}[{LOW_REQUEST_RATE_SWITCHING_MINUTES}m])'
    ),
}

QUERY_THRESHOLD = namedtuple(
    "QueryThreshold", ["upper_bound", "upper_bound_when_low_request_rate", "lower_bound", "performance_change_gap"]
)

QUERY_THRESHOLDS = {
    QueryNames.LATENCY_AVG:
        QUERY_THRESHOLD(
            upper_bound=int(os.environ.get("THRESHOLD_LATENCY_UPPER", "1000")),
            upper_bound_when_low_request_rate=int(
                os.environ.get("THRESHOLD_LATENCY_UPPER_WHEN_LOW_REQUEST_RATE", "2000")
            ),
            lower_bound=None,
            performance_change_gap=int(os.environ.get("THRESHOLD_LATENCY_PERFORMANCE_CHANGE_GAP", "200"))
        ),
    "latency":
        QUERY_THRESHOLD(
            upper_bound=int(os.environ.get("THRESHOLD_LATENCY_UPPER", "1000")),
            upper_bound_when_low_request_rate=int(
                os.environ.get("THRESHOLD_LATENCY_UPPER_WHEN_LOW_REQUEST_RATE", "2000")
            ),
            lower_bound=None,
            performance_change_gap=int(os.environ.get("THRESHOLD_LATENCY_PERFORMANCE_CHANGE_GAP", "200"))
        ),
    QueryNames.REQUEST_RATE:
        QUERY_THRESHOLD(
            upper_bound=None,
            upper_bound_when_low_request_rate=None,
            lower_bound=float(os.environ.get("THRESHOLD_REQUEST_RATE_LOWER_BOUND", "0.01")),
            performance_change_gap=None
        ),
}
