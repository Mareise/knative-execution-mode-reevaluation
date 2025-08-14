from constants import ExecutionModes
from knative_service import patch_knative_service, KnService
from logger import get_logger
from prometheus_service import ServiceMetricsReporter
from queries import QUERY_THRESHOLDS, QueryNames, WINDOW_MINUTES, LATENCY_QUERY_THRESHOLD_NAME
from datetime import datetime, timezone

logger = get_logger(__name__)


def evaluator(service: KnService, reporter: ServiceMetricsReporter):
    # Case 0: When both modes are saved in the service and cpu mode is slower than gpu
    # and cpu mode is the highest bucket boundary defined in the histogram, make a final decision and change to GPU
    if (
            service.cpu_latency is not None and
            service.gpu_latency is not None and
            service.cpu_latency >= 100000 and
            service.cpu_latency - QUERY_THRESHOLDS[
        LATENCY_QUERY_THRESHOLD_NAME].performance_change_gap > service.gpu_latency
    ):
        patch_knative_service(
            service.name,
            1,
            ExecutionModes.GPU,
            None,
            None,
            service.namespace
        )
        logger.info(f"{service.name}: Switched to final GPU mode")
        return

    # Case 1: When the request rate is too low, don't make a decision on latency
    request_rate_result_short = reporter.get_result(QueryNames.REQUEST_RATE_short)

    if request_rate_result_short is None or request_rate_result_short < QUERY_THRESHOLDS[
        QueryNames.REQUEST_RATE_short].lower_bound:
        logger.info(f"{service.name}: The request rate is too low to make a decision based on latency alone.")
    else:
        latency_query_result = reporter.get_result(QueryNames.LATENCY_P95_short)
        if latency_query_result is not None:
            # Case 2: Cpu is too slow
            if (
                    service.execution_mode == ExecutionModes.CPU_PREFERRED and
                    latency_query_result > QUERY_THRESHOLDS[
                LATENCY_QUERY_THRESHOLD_NAME].upper_bound
            ):
                logger.info(
                    f"{service.name}: WARNING: Result is above upper bound ({QUERY_THRESHOLDS[LATENCY_QUERY_THRESHOLD_NAME].upper_bound})"
                )
                switch_execution_mode(service, reporter)
                return

            # Case 3: If there was a recent change
            if is_recent_update_with_cold_start_wait_time(service.last_execution_mode_update_time, WINDOW_MINUTES):
                # Case 3.1: Function was executed on a cpu already, and gpu is not much faster
                if (
                        service.execution_mode == ExecutionModes.GPU_PREFERRED and
                        service.cpu_latency is not None and
                        latency_query_result + QUERY_THRESHOLDS[
                    LATENCY_QUERY_THRESHOLD_NAME].performance_change_gap >= service.cpu_latency
                ):
                    logger.info(
                        f"{service.name}: WARNING: GPU ({latency_query_result}) is not significantly faster than CPU ({service.cpu_latency}), switching back to CPU"
                    )
                    switch_execution_mode(service, reporter)
                    return

                # Case 3.2: Function was executed on a gpu already, and gpu is significantly faster than cpu
                if (
                        service.execution_mode == ExecutionModes.CPU_PREFERRED and
                        service.gpu_latency is not None and
                        latency_query_result - QUERY_THRESHOLDS[
                    LATENCY_QUERY_THRESHOLD_NAME].performance_change_gap >= service.gpu_latency
                ):
                    logger.info(
                        f"{service.name}: WARNING: GPU ({service.gpu_latency}) is significantly faster than CPU ({latency_query_result}), switching to GPU"
                    )
                    switch_execution_mode(service, reporter)
                    return

    # Case 4: GPU_PREFERRED mode - consider switching to CPU based on request rate and latency (only when there was no recent update)
    if (
            service.execution_mode == ExecutionModes.GPU_PREFERRED and
            not is_recent_update(service.last_execution_mode_update_time, WINDOW_MINUTES)
    ):
        request_rate_result_long = reporter.get_result(QueryNames.REQUEST_RATE_long)
        latency_threshold = QUERY_THRESHOLDS[LATENCY_QUERY_THRESHOLD_NAME].upper_bound_when_low_request_rate

        # Case 4.1: Request rate not available
        if request_rate_result_long is None:
            if service.cpu_latency is None:
                logger.info(
                    f"{service.name}: WARNING: Request rate cpu latency is not available. Switching to CPU."
                )
                switch_execution_mode(service, reporter)
                return

            if service.cpu_latency < latency_threshold:
                logger.info(
                    f"{service.name}: WARNING: Request rate is not available "
                    f"and cpu latency ({service.cpu_latency}) is within acceptable range "
                    f"({latency_threshold}). Switching to CPU."
                )
                switch_execution_mode(service, reporter)
                return

        # Case 4.2: Request rate is available and below lower bound
        request_rate_threshold = QUERY_THRESHOLDS[QueryNames.REQUEST_RATE_long].lower_bound
        if request_rate_result_long < request_rate_threshold:
            if service.cpu_latency is None:
                logger.info(
                    f"{service.name}: WARNING: Request rate ({request_rate_result_long}) is below threshold "
                    f"({request_rate_threshold}) and cpu latency is not available. Switching to CPU."
                )
                switch_execution_mode(service, reporter)
                return

            if service.cpu_latency < latency_threshold:
                logger.info(
                    f"{service.name}: WARNING: Request rate ({request_rate_result_long}) is below threshold "
                    f"({request_rate_threshold}) and cpu latency ({service.cpu_latency}) is within acceptable range "
                    f"({latency_threshold}). Switching to CPU."
                )
                switch_execution_mode(service, reporter)
                return


def switch_execution_mode(service: KnService, reporter: ServiceMetricsReporter):
    latency_result = reporter.get_result(QueryNames.LATENCY_P95_long)

    if service.execution_mode == ExecutionModes.CPU_PREFERRED:
        patch_knative_service(service.name, 1, ExecutionModes.GPU_PREFERRED, None,
                              latency_result,
                              service.namespace)
        logger.info(f"{service.name}: Switched to GPU_PREFERRED mode")
    elif service.execution_mode == ExecutionModes.GPU_PREFERRED:
        patch_knative_service(service.name, 0, ExecutionModes.CPU_PREFERRED,
                              latency_result, None,
                              service.namespace)
        logger.info(f"{service.name}: Switched to CPU_PREFERRED mode")


def is_recent_update_with_cold_start_wait_time(last_update: str, window_minutes: int) -> bool:
    if last_update is None:
        return False
    last_modified_window = int(
        (datetime.now(timezone.utc) - datetime.fromisoformat(last_update)).total_seconds() / 60
    )
    logger.debug(f"Last modified window: {last_modified_window}")
    if last_modified_window < 2: return False  # Because of cold start we wait for 2 minutes before making a decision
    return last_modified_window < window_minutes


def is_recent_update(last_update: str, window_minutes: int) -> bool:
    if last_update is None:
        return False
    last_modified_window = int(
        (datetime.now(timezone.utc) - datetime.fromisoformat(last_update)).total_seconds() / 60
    )
    logger.debug(f"Last modified window: {last_modified_window}")
    return last_modified_window < window_minutes
