from datetime import datetime, timezone
import os

from constants import ExecutionModes
from knative_service import patch_knative_service, KnService
from logger import get_logger
from prometheus_service import query_service_metrics, ServiceMetricsReporter
from queries import QUERIES, QUERY_THRESHOLDS, QUERY_RESULT

logger = get_logger(__name__)

WINDOW_SECONDS = int(os.environ.get("WINDOW_MINUTES", "30"))


def evaluator(service: KnService, reporter: ServiceMetricsReporter):
    query_name = "latency_avg"  # TODO only for now
    query_result = reporter.get_result(query_name)
    if query_result.query_result is None:
        return

    if query_result.new_mode_query_result is not None:
        # If the new mode is significantly worse than the old one we switch back
        if query_result.new_mode_query_result - QUERY_THRESHOLDS[
            query_name].performance_change_gap > query_result.query_result:
            logger.info(
                f"{service.name}: WARNING: The new mode is worse than the old one, switching back")
            switch_execution_mode(service)
            return

        # If the new mode (gpu) is just a bit better than the old one (cpu) we switch back to cpu # TODO maybe use seperate threshold for this?
        elif (query_result.new_mode_query_result + QUERY_THRESHOLDS[
            query_name].performance_change_gap > query_result.query_result
              and service.execution_mode == ExecutionModes.GPU_PREFERRED):
            logger.info(
                f"{service.name}: WARNING: The new mode is just a bit better than the old one, switching back to cpu")
            switch_execution_mode(service)
            return

    if query_result.query_result > QUERY_THRESHOLDS[
        query_name].upper_bound and service.execution_mode == ExecutionModes.CPU_PREFERRED:
        logger.info(
            f"{service.name}: WARNING: Result is above upper bound ({QUERY_THRESHOLDS[query_name].upper_bound})")
        switch_execution_mode(service)
        return

    if query_result.query_result < QUERY_THRESHOLDS[
        query_name].lower_bound and service.execution_mode == ExecutionModes.GPU_PREFERRED:
        logger.info(
            f"{service.name}: WARNING: Result is below lower bound ({QUERY_THRESHOLDS[query_name].upper_bound})")
        switch_execution_mode(service)
        return


def switch_execution_mode(service: KnService):
    # TODO maybe it makes sense to set it to CPU and GPU (see tree)
    if service.execution_mode == ExecutionModes.CPU_PREFERRED:
        patch_knative_service(service.name, 1, ExecutionModes.GPU_PREFERRED, service.namespace)
    elif service.execution_mode == ExecutionModes.GPU_PREFERRED:
        patch_knative_service(service.name, 0, ExecutionModes.CPU_PREFERRED, service.namespace)
