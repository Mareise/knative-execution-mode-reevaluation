import requests
import os
from kubernetes import client, config

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")


def get_knative_services():
    config.load_incluster_config()

    api = client.CustomObjectsApi()
    kn_objects = api.list_cluster_custom_object(
        group="serving.knative.dev",
        version="v1",
        plural="services"
    )

    names = [item["metadata"]["name"] for item in kn_objects["items"]]
    print(names)

    return names


def query_service_metrics(service_name):
    query = f'avg_over_time(function_execution_duration_seconds{{function_name="{service_name}"}}[10m])'


    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query}
    )
    response.raise_for_status()
    return response.json()


def query_prometheus(service_names):
    for service in service_names:
        print(f"\nQuerying metrics for service: {service}")
        result = query_service_metrics(service)
        print("Raw Prometheus response:")
        print(result)

        if result["data"]["result"]:
            value = float(result["data"]["result"][0]["value"][1])
            print(f"Average execution time for {service} over last 10m: {value:.3f} seconds")
        else:
            print(f"No data found for {service}")


if __name__ == "__main__":
    services = get_knative_services()
    query_prometheus(services)
