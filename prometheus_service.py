import os
import requests
from datetime import datetime, timezone

from knative_service import KnService
from logger import get_logger
from queries import QUERY_RESULT

logger = get_logger(__name__)
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")


class ServiceMetricsReporter:
    def __init__(self, service: KnService, window_minutes):
        self.service = service
        self.window = window_minutes
        self.results = {}

    def run_queries(self, query_functions: dict):
        for name, query_fn in query_functions.items():
            try:
                query_window = f"{self.window}m"
                query = query_fn(self.service.name, query_window)
                query_result = query_service_metrics(self.service.name, query)

                result = QUERY_RESULT(query_result, None)

                # Check for recent execution mode update
                last_update = self.service.last_execution_mode_update_time
                if last_update:
                    last_modified_window = int(
                        (datetime.now(timezone.utc) - datetime.fromisoformat(last_update)).total_seconds() / 60
                    )
                    if last_modified_window < self.window:
                        new_mode_query = query_fn(self.service.name, f"{last_modified_window}m")
                        new_mode_query_result = query_service_metrics(self.service.name, new_mode_query)
                        result = QUERY_RESULT(query_result, new_mode_query_result)

                self.results[name] = result

            except Exception as e:
                logger.error(f"Error running query '{name}' for service '{self.service.name}': {e}")
                self.results[name] = None

    def get_result(self, query_name) -> QUERY_RESULT:
        return self.results.get(query_name)

    def all_results(self):
        return self.results

    def __str__(self):
        lines = [f"Service: {self.service.name}"]
        for name, value in self.results.items():
            lines.append(f"  {name}: {value}")
        return "\n".join(lines)


def query_service_metrics(service_name, query):
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query}
    )
    response.raise_for_status()
    result = response.json()
    if result.get("data", {}).get("result"):
        return float(result["data"]["result"][0]["value"][1])

    logger.debug(f"{service_name}: No data found")
    return None
