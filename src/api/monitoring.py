import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match
from prometheus_client import Counter, Histogram

# 1. Prometheus Metrics Definitions
argus_api_requests_total = Counter(
    "argus_api_requests_total",
    "Total number of HTTP requests processed by the ARGUS API.",
    ["method", "endpoint", "status"],
)

argus_api_request_duration_seconds = Histogram(
    "argus_api_request_duration_seconds",
    "Histogram of HTTP request durations (seconds).",
    ["endpoint"],
    buckets=(0.05, 0.1, 0.25, 0.5, 0.75, 0.8, 0.9, 1.0, 2.5, 5.0, 10.0),
)

argus_api_fraud_score_distribution = Histogram(
    "argus_api_fraud_score_distribution",
    "Histogram of predicted fraud scores from the classifier.",
    ["result"],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)


class PrometheusMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically instrument FastAPI endpoints.
    Tracks total request counts and endpoint execution latency.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Resolve route to prevent high cardinality metric explosion on undefined/404 paths
        endpoint = "unknown"
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                endpoint = route.path
                break

        # Exclude metrics and health endpoints from telemetry tracking to avoid loops
        if endpoint in {"/metrics", "/health"}:
            return await call_next(request)

        method = request.method
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
        except Exception as e:
            status_code = "500"
            raise e
        finally:
            latency = time.perf_counter() - start_time
            # Increment request counter
            argus_api_requests_total.labels(
                method=method, endpoint=endpoint, status=status_code
            ).inc()
            # Record request latency
            argus_api_request_duration_seconds.labels(endpoint=endpoint).observe(
                latency
            )

