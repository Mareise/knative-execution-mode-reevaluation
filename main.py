import os
import time

from evaluator_service import evaluator
from knative_service import get_knative_services
from logger import get_logger

logger = get_logger(__name__)
INTERVAL_SECONDS = int(os.environ.get("INTERVAL_SECONDS", "60"))

if __name__ == "__main__":
    logger.info("Starting reevaluator")
    while True:
        kn_services = get_knative_services()
        evaluator(kn_services, "latency_avg")
        time.sleep(INTERVAL_SECONDS)
