import os

from constants import ExecutionModes
from knative_service import patch_knative_service, KnService
from logger import get_logger
from prometheus_service import ServiceMetricsReporter
from queries import QUERY_THRESHOLDS, QueryNames
from datetime import datetime, timezone

logger = get_logger(__name__)

WINDOW_MINUTES = int(os.environ.get("WINDOW_MINUTES", "30"))


def evaluator(service: KnService, reporter: ServiceMetricsReporter):
    latency_query_result = reporter.get_result(QueryNames.LATENCY_P95)
    if latency_query_result is not None and latency_query_result.query_result_short_interval is not None:

        # TODO do i really need that when i can use the latencies stored in the service itself???
        # If there was an execution mode change in the last window, we check if it got better or not
        # if latency_query_result.new_mode_query_result is not None:
        #     # If the new mode is significantly worse than the old one we switch back
        #     if latency_query_result.new_mode_query_result - QUERY_THRESHOLDS[
        #         QueryNames.LATENCY_P95].performance_change_gap > latency_query_result.query_result_short_interval:
        #         logger.info(
        #             f"{service.name}: WARNING: The new mode is worse than the old one, switching back"
        #         )
        #         switch_execution_mode(service, reporter)
        #         return
        #
        #     # If the new mode (gpu) is just a bit better than the old one (cpu) we switch back to cpu # TODO maybe use seperate threshold for this?
        #     elif (
        #             latency_query_result.new_mode_query_result + QUERY_THRESHOLDS[
        #         QueryNames.LATENCY_P95].performance_change_gap > latency_query_result.query_result_short_interval and
        #             service.execution_mode == ExecutionModes.GPU_PREFERRED
        #     ):
        #         logger.info(
        #             f"{service.name}: WARNING: The new mode is just a bit better than the old one, switching back to cpu"
        #         )
        #         switch_execution_mode(service, reporter)
        #         return
        #

        # Case 1: Cpu is too slow
        if (
                service.execution_mode == ExecutionModes.CPU_PREFERRED and
                latency_query_result.query_result_short_interval > QUERY_THRESHOLDS[QueryNames.LATENCY_P95].upper_bound
        ):
            logger.info(
                f"{service.name}: WARNING: Result is above upper bound ({QUERY_THRESHOLDS[QueryNames.LATENCY_P95].upper_bound})"
            )
            switch_execution_mode(service, reporter)
            return

        # Case 2: If there was a recent change # TODO have to check if this makes sense
        if is_recent_update(service.last_execution_mode_update_time, WINDOW_MINUTES):
            # Case 2.1: Function was executed on a cpu already, and gpu is not much faster
            if (
                    service.execution_mode == ExecutionModes.GPU_PREFERRED and
                    service.cpu_latency is not None and
                    latency_query_result.query_result_short_interval + QUERY_THRESHOLDS[
                QueryNames.LATENCY_P95].performance_change_gap >= service.cpu_latency
            ):
                logger.info(
                    f"{service.name}: WARNING: GPU is not significantly faster than CPU, switching back to CPU"
                )
                switch_execution_mode(service, reporter)
                return

            # Case 2.2: Function was executed on a gpu already, and gpu is significantly faster than cpu
            if (
                    service.execution_mode == ExecutionModes.CPU_PREFERRED and
                    service.gpu_latency is not None and
                    latency_query_result.query_result_short_interval - QUERY_THRESHOLDS[
                QueryNames.LATENCY_P95].performance_change_gap >= service.gpu_latency
            ):
                logger.info(
                    f"{service.name}: WARNING: GPU is significantly faster than CPU, switching to GPU"
                )
                switch_execution_mode(service, reporter)
                return

    # Case 4: GPU_PREFERRED mode - consider switching to CPU based on request rate and latency (only when there was no recent update)
    if (
            service.execution_mode == ExecutionModes.GPU_PREFERRED and
            not is_recent_update(service.last_execution_mode_update_time, WINDOW_MINUTES)
    ):
        request_rate_result = reporter.get_result(QueryNames.REQUEST_RATE)
        latency_result = reporter.get_result(QueryNames.LATENCY_P95)

        request_rate_value = request_rate_result.query_result_long_interval if request_rate_result else None
        latency_value = latency_result.query_result_long_interval if latency_result else None

        # Case 4.1: Request rate not available
        if request_rate_value is None:
            logger.info(f"{service.name}: WARNING: Request rate is not available, switching to CPU")
            switch_execution_mode(service, reporter)
            return

        # Case 4.2: Request rate is below lower bound
        request_rate_threshold = QUERY_THRESHOLDS[QueryNames.REQUEST_RATE].lower_bound
        if request_rate_value < request_rate_threshold:
            latency_threshold = QUERY_THRESHOLDS[QueryNames.LATENCY_P95].upper_bound_when_low_request_rate

            # Case 4.2.1: Latency is available and within acceptable range
            if latency_value is not None:
                if latency_value < latency_threshold:
                    logger.info(
                        f"{service.name}: WARNING: Request rate ({request_rate_value}) is below threshold "
                        f"({request_rate_threshold}) and latency ({latency_value}) is within acceptable range "
                        f"({latency_threshold}). Switching to CPU."
                    )
                    switch_execution_mode(service, reporter)
                    return
            # Case 4.2.2: Latency is not available
            else:
                logger.info(
                    f"{service.name}: WARNING: Request rate ({request_rate_value}) is below threshold "
                    f"({request_rate_threshold}) and latency is not available. Switching to CPU."
                )
                switch_execution_mode(service, reporter)
                return

        # Case 5: When both modes are saved in the service and cpu mode is slower than gpu
        # and cpu mode is the highest bucket boundary defined in the histogram, make a final decision and change to GPU
        if (
                service.cpu_latency is not None and
                service.gpu_latency is not None and
                service.cpu_latency == 100000.0 and
                service.cpu_latency > service.gpu_latency * QUERY_THRESHOLDS[
            QueryNames.REQUEST_RATE].performance_change_factor
        ):
            patch_knative_service(service.name, 1, ExecutionModes.GPU,
                                  None, None,
                                  service.namespace)
            logger.info(f"{service.name}: Switched to final GPU mode")


def switch_execution_mode(service: KnService, reporter: ServiceMetricsReporter):
    latency_result = reporter.get_result(QueryNames.LATENCY_P95)

    latency_value = latency_result.query_result_long_interval if latency_result else None

    if service.execution_mode == ExecutionModes.CPU_PREFERRED:
        patch_knative_service(service.name, 1, ExecutionModes.GPU_PREFERRED, None,
                              latency_value,
                              service.namespace)
        logger.info(f"{service.name}: Switched to GPU_PREFERRED mode")
    elif service.execution_mode == ExecutionModes.GPU_PREFERRED:
        patch_knative_service(service.name, 0, ExecutionModes.CPU_PREFERRED,
                              latency_value, None,
                              service.namespace)
        logger.info(f"{service.name}: Switched to CPU_PREFERRED mode")


def is_recent_update(last_update: str, window_minutes: int) -> bool:
    if last_update is None:
        return False
    last_modified_window = int(
        (datetime.now(timezone.utc) - datetime.fromisoformat(last_update)).total_seconds() / 60
    )
    logger.debug(f"Last modified window: {last_modified_window}")
    return last_modified_window < window_minutes
