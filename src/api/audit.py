import json
import logging
import sys
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match


# 1. Custom JSON Formatter for Flat Audit Logging
class AuditJSONFormatter(logging.Formatter):
    """
    Custom formatter that prints log records as single-line flat JSON objects.
    If the record message is a dictionary, it merges it directly to the top level.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
        }
        if isinstance(record.msg, dict):
            log_data.update(record.msg)
        else:
            log_data["message"] = record.getMessage()
        return json.dumps(log_data)


# 2. Configure Dedicated Audit Logger
audit_logger = logging.getLogger("ARGUS_AUDIT")
audit_logger.setLevel(logging.INFO)
# Prevent propagation to root logger to avoid duplicate/incorrect formatting
audit_logger.propagate = False

# Setup StreamHandler printing to stdout
stream_handler = logging.StreamHandler(sys.stdout)
formatter = AuditJSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z")
stream_handler.setFormatter(formatter)
audit_logger.addHandler(stream_handler)


# 3. Audit Logging Middleware
class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that intercepts requests and logs inference & request metadata.
    Strictly strips any PII, biometric data, or raw image binary data.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Resolve route path to prevent high cardinality metric/logging issues
        endpoint = "unknown"
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                endpoint = route.path
                break

        # Exclude metrics and health endpoints from audit logs
        if endpoint in {"/metrics", "/health"}:
            return await call_next(request)

        # Retrieve request ID or use a placeholder
        request_id = request.headers.get("X-Request-ID") or "unknown"
        method = request.method
        start_time = time.perf_counter()

        # Initialize audit state on request
        request.state.audit_log = None

        status_code = 500
        exception_occurred = False
        exception_msg = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            exception_occurred = True
            exception_msg = str(e)
            raise e
        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Base audit record
            audit_record = {
                "request_id": request_id,
                "method": method,
                "endpoint": endpoint,
                "status_code": status_code,
                "latency_ms": round(latency_ms, 2),
            }

            # Merge model metadata if route handler populated request.state.audit_log
            state_audit = getattr(request.state, "audit_log", None)
            if isinstance(state_audit, dict):
                # Ensure the request ID matches
                if "request_id" in state_audit:
                    audit_record["request_id"] = state_audit["request_id"]

                # Merge permitted audit fields (no PII, no raw images)
                permitted_fields = {
                    "model_version",
                    "result",
                    "fraud_score",
                    "confidence",
                    "requires_human_review",
                }
                for field in permitted_fields:
                    if field in state_audit:
                        audit_record[field] = state_audit[field]

            if exception_occurred:
                audit_record["error"] = exception_msg

            # Write the structured JSON audit log line
            audit_logger.info(audit_record)
