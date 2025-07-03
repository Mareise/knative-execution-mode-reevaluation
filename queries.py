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

QUERY_THRESHOLD = namedtuple("QueryThreshold", ["upper_bound", "lower_bound"])

QUERY_THRESHOLDS = {
    "latency_avg": QUERY_THRESHOLD(upper_bound=100, lower_bound=0.5),
    "request_rate": QUERY_THRESHOLD(upper_bound=100, lower_bound=10),
}
