from kubernetes import client, config
from collections import namedtuple
from logger import get_logger
from datetime import datetime, timezone

logger = get_logger(__name__)
KnService = namedtuple(
    "KnService", [
        "name",
        "revision_name",
        "namespace",
        "execution_mode",
        "last_execution_mode_update_time",
        "gpu_latency",
        "cpu_latency"
    ]
)


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
            item["status"].get("latestReadyRevisionName"),
            item["metadata"]["namespace"],
            item["metadata"]["annotations"].get("executionMode"),
            item["metadata"]["annotations"].get("lastExecutionModeUpdateTime"),
            float(item["metadata"]["annotations"]["gpuLatency"]) if item["metadata"]["annotations"].get(
                "gpuLatency") is not None else None,
            float(item["metadata"]["annotations"]["cpuLatency"]) if item["metadata"]["annotations"].get(
                "cpuLatency") is not None else None,
        )
        for item in kn_objects["items"]
    ]

    logger.debug(kn_services)

    return kn_services


def patch_knative_service(service_name, gpu_number, execution_mode, gpu_latency, cpu_latency, namespace="default"):
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

    annotations = current_service["metadata"].get("annotations", {})
    given_gpu_latency = float(annotations["gpuLatency"]) if "gpuLatency" in annotations else None
    given_cpu_latency = float(annotations["cpuLatency"]) if "cpuLatency" in annotations else None

    new_gpu_latency = (
        max(gpu_latency, given_gpu_latency)  # TODO really max??
        if gpu_latency is not None and given_gpu_latency is not None
        else gpu_latency if gpu_latency is not None
        else given_gpu_latency
    )

    new_cpu_latency = (
        max(cpu_latency, given_cpu_latency)
        if cpu_latency is not None and given_cpu_latency is not None
        else cpu_latency if cpu_latency is not None
        else given_cpu_latency
    )

    annotations = {
        "executionMode": execution_mode,
        "lastExecutionModeUpdateTime": datetime.now(timezone.utc).isoformat(),
    }

    # Conditionally add latencies
    if new_gpu_latency is not None:
        annotations["gpuLatency"] = str(new_gpu_latency)
    if new_cpu_latency is not None:
        annotations["cpuLatency"] = str(new_cpu_latency)

    patch_body = {
        "metadata": {
            "annotations": annotations,
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
