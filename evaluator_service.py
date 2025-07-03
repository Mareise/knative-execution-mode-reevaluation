import os

from knative_service import patch_knative_service
from logger import get_logger
from prometheus_service import query_service_metrics
from queries import QUERIES, THRESHOLDS

logger = get_logger(__name__)

WINDOW_SECONDS = os.environ.get("WINDOW_SECONDS", "30m")


def evaluator(services, query_name):
    for service in services:
        logger.info(f"Querying {query_name} metrics for service: {service.name}")
        # TODO if we change the execution mode, check if the latency is similar to the latency with a window of maybe 5m (check for lastExecutionModeUpdateTime)
        value = query_service_metrics(service, QUERIES[query_name](service.name, WINDOW_SECONDS))

        if value is not None:
            logger.info(
                f"Result of query {query_name} for service {service.name} over last {WINDOW_SECONDS}: {value:.3f} ms")
            if value > THRESHOLDS[query_name]:
                logger.info(f"WARNING: Result is above threshold ({THRESHOLDS[query_name]})")
                patch_knative_service(service.name, 1, "gpu_preferred", service.namespace)
