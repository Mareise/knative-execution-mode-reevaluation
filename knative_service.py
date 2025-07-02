from kubernetes import client, config
from collections import namedtuple


def get_knative_services():
    config.load_incluster_config()

    api = client.CustomObjectsApi()
    kn_objects = api.list_cluster_custom_object(
        group="serving.knative.dev",
        version="v1",
        plural="services"
    )

    KnService = namedtuple("KnService", ["name", "namespace"])
    kn_services = [KnService(item["metadata"]["name"], item["metadata"]["namespace"]) for item in kn_objects["items"]]

    print(kn_services)

    return kn_services

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
