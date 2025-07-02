import os
import time

from knative_service import get_knative_services, patch_knative_service
from prometheus_service import query_service_metrics
from queries import QUERIES
from logger import get_logger

logger = get_logger(__name__)
INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "60"))

def reevaluate(services):
    for service in services:
        logger.info(f"\nQuerying metrics for service: {service.name}")
        window = "5m"
        value = query_service_metrics(service, QUERIES["latency_avg"](service.name, window))

        if value is not None:
            logger.info(f"Average execution time for {service.name} over last {window}: {value:.3f} ms")
            if value > 100:
                logger.info("WARNING: Execution time is above 100ms")
                patch_knative_service(service.name, 1, "gpu_preferred", service.namespace)


if __name__ == "__main__":
    logger.info("Starting reevaluator")
    while True:
        kn_services = get_knative_services()
        reevaluate(kn_services)
        time.sleep(INTERVAL_SECONDS)
    
