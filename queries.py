from collections import namedtuple

QUERIES = {
    # TODO pod waiting time
    "latency_avg": lambda service_name, window="5m": (
        f'rate(activator_request_latencies_sum{{service_name="{service_name}"}}[{window}]) / '
        f'rate(activator_request_latencies_count{{service_name="{service_name}"}}[{window}])'
    ),
    "request_rate": lambda service_name, window="1m": (
        f'rate(activator_requests_total{{service_name="{service_name}"}}[{window}])'
    ),
}

# TODO different performance_change_gap dependent on current execution mode
QUERY_THRESHOLD = namedtuple("QueryThreshold", ["upper_bound", "lower_bound", "performance_change_gap"])

# TODO Upper bound sollte glaub ich höher sein (cold start ziemlich lange (model fetching))
QUERY_THRESHOLDS = {
    "latency_avg": QUERY_THRESHOLD(upper_bound=100, lower_bound=0.5, performance_change_gap=20),
    "request_rate": QUERY_THRESHOLD(upper_bound=100, lower_bound=10, performance_change_gap=20),
}
