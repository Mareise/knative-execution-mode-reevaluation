from kubernetes import client, config
from collections import namedtuple
from logger import get_logger
from datetime import datetime, timezone

logger = get_logger(__name__)
KnService = namedtuple("KnService",
                       ["name", "revision_name", "namespace", "execution_mode", "last_execution_mode_update_time"])


def get_knative_services():
    logger.debug("Getting Knative services")
    config.load_incluster_config()

    api = client.CustomObjectsApi()
    kn_objects = api.list_cluster_custom_object(
        group="serving.knative.dev",
        version="v1",
        plural="services"
    )

    kn_services = [
        KnService(
            item["metadata"]["name"],
            item["status"]["latestCreatedRevisionName"],
            item["metadata"]["namespace"],
            item["metadata"]["annotations"]["executionMode"],
            item["metadata"]["annotations"].get("lastExecutionModeUpdateTime", None)
        ) for item in kn_objects["items"]]

    logger.debug(kn_services)

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
        "metadata": {
            "annotations": {
                "executionMode": execution_mode,
                "lastExecutionModeUpdateTime": datetime.now(timezone.utc).isoformat()
            },
        },
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "executionMode": execution_mode,
                    },
                    "lastExecutionModeUpdateTime": datetime.now(timezone.utc).isoformat()
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
        logger.info(f"{service_name}: Patched with execution mode {execution_mode} and GPU number {gpu_number}")
    except Exception as e:
        logger.error(f"{service_name}: Failed to patch: {e}")
