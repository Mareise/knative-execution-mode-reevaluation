from datetime import datetime, timezone
import os

from constants import ExecutionModes
from knative_service import patch_knative_service, KnService
from logger import get_logger
from prometheus_service import query_service_metrics
from queries import QUERIES, QUERY_THRESHOLDS

logger = get_logger(__name__)

WINDOW_SECONDS = int(os.environ.get("WINDOW_MINUTES", "30"))


def evaluator(services: list[KnService], query_name):
    for service in services:
        logger.debug(f"{service.name}: Querying {query_name}")

        query_result = query_service_metrics(service, QUERIES[query_name](service.name, str(WINDOW_SECONDS) + "m"))
        if query_result is not None:
            logger.info(
                f"{service.name}: Result of query {query_name} over last {WINDOW_SECONDS}m: {query_result:.3f} ms"
            )

            if service.last_execution_mode_update_time is not None:
                last_modified_window = int((datetime.now(timezone.utc) - datetime.fromisoformat(
                    service.last_execution_mode_update_time)).total_seconds() / 60)
                if last_modified_window < WINDOW_SECONDS:
                    new_mode_query_result = query_service_metrics(
                        service, QUERIES[query_name](service.name, str(last_modified_window) + "m")
                    )

                    if new_mode_query_result is not None:
                        logger.info(
                            f"{service.name}: Result of query {query_name} for newly created service over last {last_modified_window}: {new_mode_query_result:.3f} ms"
                        )
                        # If the new mode is significantly worse than the old one we switch back
                        if new_mode_query_result - QUERY_THRESHOLDS[query_name].performance_change_gap > query_result:
                            logger.info(
                                f"{service.name}: WARNING: The new mode is worse than the old one, switching back")
                            switch_execution_mode(service)

                        # If the new mode (gpu) is just a bit better than the old one (cpu) we switch back to cpu # TODO maybe use seperate threshold for this?
                        elif (new_mode_query_result + QUERY_THRESHOLDS[query_name].performance_change_gap > query_result
                              and service.execution_mode == ExecutionModes.GPU_PREFERRED):
                            switch_execution_mode(service)

            elif query_result > QUERY_THRESHOLDS[
                query_name].upper_bound and service.execution_mode == ExecutionModes.CPU_PREFERRED:
                logger.info(
                    f"{service.name}: WARNING: Result is above threshold ({QUERY_THRESHOLDS[query_name].upper_bound})")
                patch_knative_service(service.name, 1, ExecutionModes.GPU_PREFERRED, service.namespace)


def switch_execution_mode(service: KnService):
    # TODO maybe it makes sense to set it to CPU and GPU (see tree)
    if service.execution_mode == ExecutionModes.CPU_PREFERRED:
        patch_knative_service(service.name, 1, ExecutionModes.GPU_PREFERRED, service.namespace)
    elif service.execution_mode == ExecutionModes.GPU_PREFERRED:
        patch_knative_service(service.name, 0, ExecutionModes.CPU_PREFERRED, service.namespace)
