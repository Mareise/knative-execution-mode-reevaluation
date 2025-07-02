from knative_service import get_knative_services, patch_knative_service
from prometheus_service import query_service_metrics
from queries import QUERIES


def reevaluate(services):
    for service in services:
        print(f"\nQuerying metrics for service: {service.name}")
        value = query_service_metrics(service, QUERIES["latency_avg"](service.name, window="5m"))

        print(f"Average execution time for {service.name} over last 5m: {value:.3f} ms")
        if value > 100:
            print("WARNING: Execution time is above 100ms")
            patch_knative_service(service.name, 1, "gpu_preferred", service.namespace)


if __name__ == "__main__":
    kn_services = get_knative_services()
    reevaluate(kn_services)
    
