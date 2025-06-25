import requests

PROMETHEUS_URL = "http://prometheus-kube-prometheus-prometheus:9090/api/v1/query"
FUNCTION_NAME = "myfunc"

def query_prometheus():
    print("Haaallloooo")
    query = f'avg_over_time(function_execution_duration_seconds{{function_name="{FUNCTION_NAME}"}}[10m])'
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query}
    )
    response.raise_for_status()
    result = response.json()
    print("Raw Prometheus response:")
    print(result)

    if result["data"]["result"]:
        value = float(result["data"]["result"][0]["value"][1])
        print(f"\nAverage execution time for {FUNCTION_NAME} over last 10m: {value:.3f} seconds")
    else:
        print(f"\nNo data found for {FUNCTION_NAME}")

if __name__ == "__main__":
    query_prometheus()