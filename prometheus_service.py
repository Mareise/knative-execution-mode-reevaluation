import os
import requests
from datetime import datetime, timezone

from constants import ExecutionModes
from knative_service import KnService
from logger import get_logger
from queries import QUERY_RESULT, LONG_INTERVAL_MULTIPLIER

logger = get_logger(__name__)
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")


class ServiceMetricsReporter:
    def __init__(self, service: KnService, window_minutes):
        self.service = service
        self.window = window_minutes
        self.results: dict[str, QUERY_RESULT | None] = {}

    def run_queries(self, query_functions: dict):
        for name, query_fn in query_functions.items():
            try:
                long_interval_query_window = f"{self.window * LONG_INTERVAL_MULTIPLIER}m"
                short_interval_query_window = f"{self.window}m"

                # Check for recent execution mode update
                # last_update = self.service.last_execution_mode_update_time
                # if last_update:
                #     last_modified_window = int(
                #         (datetime.now(timezone.utc) - datetime.fromisoformat(last_update)).total_seconds() / 60
                #     )
                #     logger.debug(f"Last modified window: {last_modified_window}")
                #     if last_modified_window < self.window:
                #         # Query for new mode when there was a change in the window interval
                #         new_mode_query = query_fn(self.service.revision_name, short_interval_query_window)
                #         new_mode_query_result = query_service_metrics(self.service.revision_name, new_mode_query)
                #
                #         self.results[name] = QUERY_RESULT(new_mode_query_result, new_mode_query_result)
                #         return

                # Query for long interval
                long_query = query_fn(self.service.revision_name, long_interval_query_window)
                long_query_result = query_service_metrics(self.service.revision_name, long_query)

                # Query for short interval
                short_query = query_fn(self.service.revision_name, short_interval_query_window)
                short_query_result = query_service_metrics(self.service.revision_name, short_query)

                result = QUERY_RESULT(short_query_result, long_query_result)
                self.results[name] = result

            except Exception as e:
                logger.error(
                    f"Error running query '{name}' for service '{self.service.revision_name}': {e}",
                    exc_info=True
                )
                self.results[name] = None

    def get_result(self, query_name) -> QUERY_RESULT:
        return self.results.get(query_name)

    def all_results(self):
        return self.results

    def __str__(self):
        lines = [f"Service: {self.service.revision_name}"]
        for name, value in self.results.items():
            if isinstance(value, QUERY_RESULT):
                lines.append(f"  {name}:")
                for field_name, field_value in value._asdict().items():
                    if isinstance(field_value, float):
                        lines.append(f"    {field_name}: {field_value:.2f}")
                    else:
                        lines.append(f"    {field_name}: {field_value}")
            else:
                lines.append(f"  {name}: {value}")
        return "\n".join(lines)


def query_service_metrics(service_name, query):
    logger.debug(f"{service_name}: Executing query: {query}")
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query}
    )
    response.raise_for_status()
    result = response.json()
    if result.get("data", {}).get("result"):
        result_value = float(result["data"]["result"][0]["value"][1])
        logger.debug(f"{service_name}: Executed query: {query} with result: {result_value}")
        return result_value

    logger.debug(f"{service_name}: No data found")
    return None
