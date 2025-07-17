import os
from collections import namedtuple
from enum import Enum


class QueryNames(Enum):
    LATENCY_AVG = "latency_avg"
    REQUEST_RATE = "request_rate"


QUERIES = {
    # TODO pod waiting time
    QueryNames.LATENCY_AVG: lambda revision_name, window="5m": (
        f'rate(activator_request_latencies_sum{{revision_name="{revision_name}"}}[{window}]) / '
        f'rate(activator_request_latencies_count{{revision_name="{revision_name}"}}[{window}])'
    ),
    QueryNames.REQUEST_RATE: lambda revision_name, window="5m": (
        f'rate(activator_request_count{{revision_name="{revision_name}"}}[{window}])'
    ),
}

QUERY_RESULT = namedtuple(
    "QueryResult", ["query_result_short_interval", "query_result_long_interval", "new_mode_query_result"]
)

# TODO different performance_change_gap dependent on current execution mode
QUERY_THRESHOLD = namedtuple(
    "QueryThreshold", ["upper_bound", "upper_bound_when_low_request_rate", "lower_bound", "performance_change_gap"]
)

# TODO Upper bound sollte glaub ich höher sein (cold start ziemlich lange (model fetching))
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
    QueryNames.REQUEST_RATE:
        QUERY_THRESHOLD(
            upper_bound=None,
            upper_bound_when_low_request_rate=None,
            lower_bound=float(os.environ.get("THRESHOLD_REQUEST_RATE_LOWER_BOUND", "0.01")),
            performance_change_gap=None
        ),
}

LONG_INTERVAL_MULTIPLIER = int(os.environ.get("LONG_INTERVAL_MULTIPLIER", "50"))
