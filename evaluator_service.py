import os

from constants import ExecutionModes
from knative_service import patch_knative_service, KnService
from logger import get_logger
from prometheus_service import ServiceMetricsReporter
from queries import QUERY_THRESHOLDS, QueryNames

logger = get_logger(__name__)

WINDOW_SECONDS = int(os.environ.get("WINDOW_MINUTES", "30"))


def evaluator(service: KnService, reporter: ServiceMetricsReporter):
    latency_query_result = reporter.get_result(QueryNames.LATENCY_AVG)
    if latency_query_result is not None and latency_query_result.query_result_short_interval is not None:

        # TODO do i really need that when i can use the latencies stored in the service itself???
        # If there was an execution mode change in the last window, we check if it got better or not
        # if latency_query_result.new_mode_query_result is not None:
        #     # If the new mode is significantly worse than the old one we switch back
        #     if latency_query_result.new_mode_query_result - QUERY_THRESHOLDS[
        #         QueryNames.LATENCY_AVG].performance_change_gap > latency_query_result.query_result_short_interval:
        #         logger.info(
        #             f"{service.name}: WARNING: The new mode is worse than the old one, switching back"
        #         )
        #         switch_execution_mode(service, reporter)
        #         return
        #
        #     # If the new mode (gpu) is just a bit better than the old one (cpu) we switch back to cpu # TODO maybe use seperate threshold for this?
        #     elif (
        #             latency_query_result.new_mode_query_result + QUERY_THRESHOLDS[
        #         QueryNames.LATENCY_AVG].performance_change_gap > latency_query_result.query_result_short_interval and
        #             service.execution_mode == ExecutionModes.GPU_PREFERRED
        #     ):
        #         logger.info(
        #             f"{service.name}: WARNING: The new mode is just a bit better than the old one, switching back to cpu"
        #         )
        #         switch_execution_mode(service, reporter)
        #         return
        #
        if (
                latency_query_result.query_result_short_interval > QUERY_THRESHOLDS[
            QueryNames.LATENCY_AVG].upper_bound and
                service.execution_mode == ExecutionModes.CPU_PREFERRED
        ):
            logger.info(
                f"{service.name}: WARNING: Result is above upper bound ({QUERY_THRESHOLDS[QueryNames.LATENCY_AVG].upper_bound})"
            )
            switch_execution_mode(service, reporter)
            return

        if (
                service.execution_mode == ExecutionModes.GPU_PREFERRED and
                service.cpu_latency is not None and
                latency_query_result.query_result_short_interval + QUERY_THRESHOLDS[
            QueryNames.LATENCY_AVG].performance_change_gap >= service.cpu_latency
        ):
            logger.info(
                f"{service.name}: WARNING: GPU is not significantly faster than CPU, switching back to CPU"
            )
            switch_execution_mode(service, reporter)
            return

        if (
                service.execution_mode == ExecutionModes.CPU_PREFERRED and
                service.gpu_latency is not None and
                latency_query_result.query_result_short_interval - QUERY_THRESHOLDS[
            QueryNames.LATENCY_AVG].performance_change_gap >= service.gpu_latency
        ):
            logger.info(
                f"{service.name}: WARNING: GPU is significantly faster than CPU, switching to GPU"
            )
            switch_execution_mode(service, reporter)
            return

    # TODO refactor
    if service.execution_mode == ExecutionModes.GPU_PREFERRED:
        if reporter.get_result(QueryNames.REQUEST_RATE) is not None:
            # Checking if the request rate is below the threshold and if so switch to cpu when latency is not too high
            request_rate_query_result = reporter.get_result(QueryNames.REQUEST_RATE).query_result_short_interval
            latency_long_interval_query_result = reporter.get_result(QueryNames.LATENCY_AVG).query_result_long_interval
            if (
                    request_rate_query_result is not None and
                    request_rate_query_result < QUERY_THRESHOLDS[QueryNames.REQUEST_RATE].lower_bound
            ):
                if (
                        latency_long_interval_query_result is not None and
                        latency_long_interval_query_result < QUERY_THRESHOLDS[
                    QueryNames.LATENCY_AVG].upper_bound_when_low_request_rate
                ):
                    logger.info(
                        f"{service.name}: WARNING: Request rate is below lower bound "
                        f"({QUERY_THRESHOLDS[QueryNames.REQUEST_RATE].lower_bound})"
                        f" and the upper_bound_when_low_request_rate is over the threshold. "
                    )
                    switch_execution_mode(service)
                elif latency_long_interval_query_result is None:
                    logger.info(
                        f"{service.name}: WARNING: Request rate is below lower bound "
                        f"({QUERY_THRESHOLDS[QueryNames.REQUEST_RATE].lower_bound})"
                    )
                    switch_execution_mode(service)

        elif reporter.get_result(QueryNames.REQUEST_RATE) is None or reporter.get_result(
                QueryNames.REQUEST_RATE).query_result_short_interval is None:
            logger.info(
                f"{service.name}: WARNING: Request rate is not available, switching to CPU"
            )
            switch_execution_mode(service, reporter)
            return

    # TODO i could make the decision final if service.gpu_latency and service_cpu latencies are signinficantly different


def switch_execution_mode(service: KnService, reporter: ServiceMetricsReporter):
    # TODO maybe it makes sense to set it to CPU and GPU (see tree)
    if service.execution_mode == ExecutionModes.CPU_PREFERRED:
        patch_knative_service(service.name, 1, ExecutionModes.GPU_PREFERRED, None,
                              reporter.get_result(QueryNames.LATENCY_AVG).query_result_short_interval,
                              service.namespace)
        logger.info(f"{service.name}: Switched to GPU_PREFERRED mode")
    elif service.execution_mode == ExecutionModes.GPU_PREFERRED:
        patch_knative_service(service.name, 0, ExecutionModes.CPU_PREFERRED,
                              reporter.get_result(QueryNames.LATENCY_AVG).query_result_short_interval, None,
                              service.namespace)
        logger.info(f"{service.name}: Switched to CPU_PREFERRED mode")
