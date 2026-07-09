import os
import json
import secrets
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/retrain", tags=["retraining"])
logger = logging.getLogger("ARGUS_Retraining_API")

STATE_FILE = os.getenv("RETRAINING_STATE_FILE", "data/retraining_state.json")

# X-User-Role alone is just a caller-supplied header — anyone can set it, so
# it can't carry authorization on its own. Approval additionally requires a
# shared-secret API key so only callers holding that secret can approve
# retraining compute. Configured out-of-band (not in source control).
RETRAINING_APPROVAL_API_KEY = os.getenv("RETRAINING_APPROVAL_API_KEY")


def _check_approval_authorized(x_user_role: Optional[str], x_api_key: Optional[str]) -> None:
    if not RETRAINING_APPROVAL_API_KEY:
        # Fail closed: an approval endpoint with no configured secret would
        # otherwise accept the role header alone, which is unauthenticated.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retraining approval is not configured (RETRAINING_APPROVAL_API_KEY unset).",
        )
    if x_user_role != "Lead Data Scientist" or not x_api_key or not secrets.compare_digest(
        x_api_key, RETRAINING_APPROVAL_API_KEY
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Only Lead Data Scientist is authorized to approve retraining compute.",
        )


class DriftPayload(BaseModel):
    psi: float
    drift_detected: bool


class RetrainRequest(BaseModel):
    request_id: str
    status: str  # PENDING_APPROVAL, APPROVED
    psi: float
    drift_detected: bool
    submitted_at: str
    resolved_at: Optional[str] = None
    approved_by: Optional[str] = None
    dispatched: bool


def load_state() -> List[dict]:
    if not os.path.exists(STATE_FILE):
        return []
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read retraining state file: {e}")
        return []


def save_state(state: List[dict]):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(STATE_FILE)), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write retraining state file: {e}")


def check_rate_limit(requests: List[dict]) -> bool:
    now = datetime.now(timezone.utc)
    one_week_ago = now - timedelta(days=7)
    for r in requests:
        if r["status"] == "APPROVED" and r.get("resolved_at"):
            try:
                resolved_time = datetime.fromisoformat(
                    r["resolved_at"].replace("Z", "+00:00")
                )
                if resolved_time >= one_week_ago:
                    return True
            except (ValueError, TypeError) as e:
                # A malformed timestamp in state history shouldn't block
                # the rate-limit check for every other entry; skip it but
                # don't swallow it silently.
                logger.warning(f"Skipping unparseable resolved_at timestamp: {e}")
    return False


def trigger_workflow(request_id: str) -> bool:
    """
    Triggers the external Airflow or GitHub Actions workflow.
    Dispatches a real HTTP call if target URLs are configured, otherwise falls back to simulated/mock log dispatch.
    """
    workflow_url = os.getenv("RETRAINING_WORKFLOW_URL")
    if not workflow_url:
        logger.info(
            f"RETRAINING_WORKFLOW_URL not set. Simulating pipeline dispatch for request {request_id} (SUCCESS)."
        )
        return True

    # Real HTTP POST call (e.g. to Airflow or GitHub API)
    try:
        import urllib.request
        import urllib.error
        import urllib.parse

        # RETRAINING_WORKFLOW_URL is operator-configured, not end-user
        # input, but urllib.request.urlopen will happily follow file:// and
        # other non-HTTP schemes if given one — restrict to http(s) so a
        # misconfigured URL can't turn this into a local file read.
        scheme = urllib.parse.urlsplit(workflow_url).scheme
        if scheme not in ("http", "https"):
            logger.error(
                f"Refusing to dispatch workflow to non-HTTP(S) URL scheme: {scheme!r}"
            )
            return False

        headers = {"Content-Type": "application/json"}
        token = os.getenv("RETRAINING_WORKFLOW_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload_data = json.dumps({"request_id": request_id, "ref": "main"}).encode(
            "utf-8"
        )
        req = urllib.request.Request(
            workflow_url, data=payload_data, headers=headers, method="POST"
        )

        with urllib.request.urlopen(req, timeout=10) as response:  # nosec B310 - scheme checked above
            status_code = response.getcode()
            logger.info(
                f"Successfully dispatched workflow to {workflow_url}, status: {status_code}"
            )
            return status_code in (200, 201, 202)
    except Exception as e:
        logger.error(f"Failed to dispatch external retraining workflow: {e}")
        return False


@router.post("", response_model=RetrainRequest, status_code=status.HTTP_201_CREATED)
def request_retraining(payload: DriftPayload):
    # 1. Validation check
    if not payload.drift_detected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Retraining can only be initiated when model drift is detected.",
        )

    state = load_state()

    # 2. Rate-limiting check: At most once per week
    if check_rate_limit(state):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Retraining rate limit exceeded. Retraining is allowed at most once per week.",
        )

    # 3. Check if there's already a pending request to prevent duplicates
    for r in state:
        if r["status"] == "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A retraining request is already pending approval (ID: {r['request_id']}).",
            )

    # 4. Create new pending request
    new_request = {
        "request_id": str(uuid.uuid4()),
        "status": "PENDING_APPROVAL",
        "psi": payload.psi,
        "drift_detected": payload.drift_detected,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
        "approved_by": None,
        "dispatched": False,
    }

    state.append(new_request)
    save_state(state)
    logger.info(f"Created pending retraining request: {new_request['request_id']}")
    return new_request


@router.post("/{request_id}/approve", response_model=RetrainRequest)
def approve_retraining(
    request_id: str,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    # 1. Enforce Role-Based Access Control (RBAC): role header plus a shared
    # secret, since the role header by itself is just caller-asserted state.
    _check_approval_authorized(x_user_role, x_api_key)

    state = load_state()

    # 2. Find request
    request_idx = -1
    for i, r in enumerate(state):
        if r["request_id"] == request_id:
            request_idx = i
            break

    if request_idx == -1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Retraining request with ID {request_id} not found.",
        )

    req = state[request_idx]

    # 3. Check status
    if req["status"] != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Retraining request is already {req['status']}.",
        )

    # 4. Re-check rate limit before launching compute, to enforce safety strictly
    if check_rate_limit(state):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Retraining rate limit exceeded. Retraining is allowed at most once per week.",
        )

    # 5. Approve and trigger the workflow
    req["status"] = "APPROVED"
    req["resolved_at"] = datetime.now(timezone.utc).isoformat()
    req["approved_by"] = x_user_role

    # Call trigger/dispatch
    dispatched = trigger_workflow(req["request_id"])
    req["dispatched"] = dispatched

    state[request_idx] = req
    save_state(state)
    logger.info(
        f"Retraining request {request_id} approved and dispatched: {dispatched}"
    )
    return req


@router.get("/requests", response_model=List[RetrainRequest])
def list_requests(status: Optional[str] = None):
    state = load_state()
    if status:
        return [r for r in state if r["status"].upper() == status.upper()]
    return state
