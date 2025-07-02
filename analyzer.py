import requests
import os
from kubernetes import client, config
import time

from app.queries import QUERIES

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
    query = QUERIES["latency_avg"](service_name, window="5m")

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
            print(f"Average execution time for {service} over last 5m: {value:.3f} ms")

            time.sleep(30)
            patch_knative_service(service, 1, "gpu_preferred")
            if value > 100:
                print("WARNING: Execution time is above 100ms")
                patch_knative_service(service, 1, "gpu_preferred")
        else:
            print(f"No data found for {service}")


def patch_knative_service(service_name, gpu_number, execution_mode, namespace="default"):
    config.load_incluster_config()
    api = client.CustomObjectsApi()

    current_service = api.get_namespaced_custom_object(
        group="serving.knative.dev",
        version="v1",
        namespace=namespace,
        plural="services",
        name=service_name
    )

    current_image = current_service["spec"]["template"]["spec"]["containers"][0]["image"]

    patch_body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "executionMode": execution_mode
                    }
                },
                "spec": {
                    "containers": [
                        {
                            "image": current_image,
                            "resources": {
                                "limits": {
                                    "cpu": "500m",
                                    "nvidia.com/gpu": str(gpu_number)
                                },
                            }
                        }
                    ]
                }
            }
        }
    }

    try:
        api.patch_namespaced_custom_object(
            group="serving.knative.dev",
            version="v1",
            namespace=namespace,
            plural="services",
            name=service_name,
            body=patch_body
        )
        print(f"Patched service {service_name}")
    except Exception as e:
        print(f"Failed to patch {service_name}: {e}")


if __name__ == "__main__":
    # services = get_knative_services() #todo uncomment when commiting
    services = ["wasgeht", "gpu-function"]  # for testing
    query_prometheus(services)
    
