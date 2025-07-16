from collections import namedtuple
from enum import Enum


class QueryNames(Enum):
    LATENCY_AVG = "latency_avg"
    REQUEST_RATE = "request_rate"


QUERIES = {
    # TODO pod waiting time
    QueryNames.LATENCY_AVG: lambda service_name, window="5m": (
        f'rate(activator_request_latencies_sum{{service_name="{service_name}"}}[{window}]) / '
        f'rate(activator_request_latencies_count{{service_name="{service_name}"}}[{window}])'
    ),
    QueryNames.REQUEST_RATE: lambda service_name, window="5m": (
        f'rate(activator_request_count{{service_name="{service_name}"}}[{window}])'
    ),
}

QUERY_RESULT = namedtuple("QueryResult",
                          ["query_result_short_interval", "query_result_long_interval", "new_mode_query_result"])

# TODO different performance_change_gap dependent on current execution mode
QUERY_THRESHOLD = namedtuple("QueryThreshold", ["upper_bound", "upper_bound_when_low_request_rate", "lower_bound",
                                                "performance_change_gap"])

# TODO Upper bound sollte glaub ich höher sein (cold start ziemlich lange (model fetching))
QUERY_THRESHOLDS = {
    QueryNames.LATENCY_AVG: QUERY_THRESHOLD(upper_bound=30, upper_bound_when_low_request_rate=100, lower_bound=None,
                                            performance_change_gap=10),
    QueryNames.REQUEST_RATE: QUERY_THRESHOLD(upper_bound=None, upper_bound_when_low_request_rate=None, lower_bound=0.01,
                                             performance_change_gap=None),
}

LONG_INTERVAL_MULTIPLIER = 50
