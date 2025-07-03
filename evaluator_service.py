import os

from knative_service import patch_knative_service, KnService
from logger import get_logger
from prometheus_service import query_service_metrics
from queries import QUERIES, QUERY_THRESHOLDS

logger = get_logger(__name__)

WINDOW_SECONDS = os.environ.get("WINDOW_SECONDS", "30m")


def evaluator(services: list[KnService], query_name):
    for service in services:
        logger.info(f"Querying {query_name} metrics for service: {service.name}")

        query_result = query_service_metrics(service, QUERIES[query_name](service.name, WINDOW_SECONDS))
        if query_result is not None:
            logger.info(
                f"Result of query {query_name} for service {service.name} over last {WINDOW_SECONDS}: {query_result:.3f} ms"
            )

            if service.last_execution_mode_update_time is not None and service.last_execution_mode_update_time < WINDOW_SECONDS:
                new_mode_query_result = query_service_metrics(
                    service, QUERIES[query_name](service.name, service.last_execution_mode_update_time)
                )

                if new_mode_query_result is not None:
                    logger.info(
                        f"Result of query {query_name} for newly created service {service.name} over last {service.last_execution_mode_update_time}: {new_mode_query_result:.3f} ms"
                    )
                    if new_mode_query_result > query_result:
                        logger.info("WARNING: The new mode is worse than the old one, switching back")
                        switch_execution_mode(service)

            elif query_result > QUERY_THRESHOLDS[query_name].upper_bound:
                logger.info(f"WARNING: Result is above threshold ({QUERY_THRESHOLDS[query_name].upper_bound})")
                patch_knative_service(service.name, 1, "gpu_preferred", service.namespace)


def switch_execution_mode(service: KnService):
    # TODO maybe it makes sense to set it to CPU and GPU (see tree)
    if service.execution_mode == "cpu_preferred":
        patch_knative_service(service.name, 1, "gpu_preferred", service.namespace)
    elif service.execution_mode == "gpu_preferred":
        patch_knative_service(service.name, 0, "cpu_preferred", service.namespace)
