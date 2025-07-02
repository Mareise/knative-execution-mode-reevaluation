QUERIES = {
    "latency_avg": lambda service_name, window="5m": (
        f'rate(activator_request_latencies_sum{{service_name="{service_name}"}}[{window}]) / '
        f'rate(activator_request_latencies_count{{service_name="{service_name}"}}[{window}])'
    ),
    "request_rate": lambda service_name, window="1m": (
        f'rate(activator_requests_total{{service_name="{service_name}"}}[{window}])'
    ),
}