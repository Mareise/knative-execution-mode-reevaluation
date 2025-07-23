import os
import time

from constants import ExecutionModes
from evaluator_service import evaluator
from knative_service import get_knative_services
from logger import get_logger
from prometheus_service import ServiceMetricsReporter
from queries import QUERIES

logger = get_logger(__name__)
INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "60"))
WINDOW_MINUTES = int(os.environ.get("WINDOW_MINUTES", "30"))

if __name__ == "__main__":
    logger.info("Starting reevaluator")
    while True:
        logger.info("\n-------------------------\n")
        kn_services = get_knative_services()

        for service in kn_services:
            reporter = ServiceMetricsReporter(service, WINDOW_MINUTES)
            reporter.run_queries(QUERIES)
            logger.info(reporter)
            if service.execution_mode != ExecutionModes.CPU and service.execution_mode != ExecutionModes.GPU:  # TODO on final handover move up to exclude reporter
                evaluator(service, reporter)
        time.sleep(INTERVAL_SECONDS)
