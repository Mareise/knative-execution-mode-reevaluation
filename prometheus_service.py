import os
import requests

from knative_service import KnService
from logger import get_logger

logger = get_logger(__name__)
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")


class ServiceMetricsReporter:
    def __init__(self, service: KnService):
        self.service = service
        self.results: dict[str, str | None] = {}

    def run_queries(self, query_functions: dict):
        for name, query_fn in query_functions.items():
            try:
                query = query_fn(self.service.revision_name)
                query_result = query_service_metrics(self.service.revision_name, query)

                self.results[name] = query_result

            except Exception as e:
                logger.error(
                    f"Error running query '{name}' for service '{self.service.revision_name}': {e}",
                    exc_info=True
                )
                self.results[name] = None

    def get_result(self, query_name) -> str | None:
        return self.results.get(query_name)

    def all_results(self):
        return self.results

    def __str__(self):
        lines = [f"Service: {self.service.revision_name}"]
        for name, value in self.results.items():
            if isinstance(value, float):
                lines.append(f"    {name}: {value:.4f}")
            else:
                lines.append(f"    {name}: {value}")
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
