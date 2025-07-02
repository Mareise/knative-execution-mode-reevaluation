import os
import requests


PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

def query_service_metrics(service_name, query):
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query}
    )
    response.raise_for_status()
    result = response.json()
    if result["data"]["result"]:
        return float(result["data"]["result"][0]["value"][1])

    print(f"No data found for {service_name}")
    return None
