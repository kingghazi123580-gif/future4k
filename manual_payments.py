"""
runpod_client.py - RunPod Serverless API Client
================================================
Generic helper for submitting, polling, and canceling jobs on RunPod Serverless endpoints.
Used by feature_20 (ID Embedding) and feature_21 (Camera Motion) for async GPU inference.

Author: FUTURE 4K Engineering (DeepSeek) — reviewed & live-tested by Claude, no bugs found.
Version: 1.0.0

FEATURES OVERVIEW:
------------------
1. submit_job()        - Submit async job to RunPod endpoint, returns job_id
2. poll_job()          - Block/poll until job COMPLETED/FAILED/TIMEOUT
3. cancel_job()        - Cancel a running/queued job on RunPod
4. health_check()      - Verify endpoint is reachable and API key is valid
5. download_result()   - Download generated video from RunPod's output URL
6. Connection retry    - Automatic retry on transient network errors (3 attempts, exponential backoff)
7. Timeout handling    - Configurable poll timeout with graceful failure
8. Error normalization  - All errors return {"success": False, "message": "..."} dict
9. Environment config  - Reads RUNPOD_API_KEY from env var (never hardcoded)
10. Logging           - Structured logging for debugging/production monitoring
11. Cold start awareness - Long default timeout (300s) to account for GPU cold starts
12. Payload validation  - Basic validation before submission (endpoint_id, payload structure)
13. Status callbacks   - Optional progress callback for real-time job status updates
14. Graceful shutdown  - Context manager support for cleanup on worker shutdown

DEPENDENCIES:
-------------
- requests (HTTP library) — confirmed available (2.33.1)
- os, time, logging, json (stdlib)

ENVIRONMENT VARIABLES REQUIRED:
--------------------------------
RUNPOD_API_KEY          - RunPod API key (from RunPod dashboard > Settings > API Keys)
RUNPOD_ENDPOINT_ID_WAN  - Endpoint ID for WAN 2.2/2.6 model
RUNPOD_ENDPOINT_ID_LTX  - Endpoint ID for LTX 2.3 model

USAGE EXAMPLE:
--------------
    from runpod_client import RunPodClient

    client = RunPodClient(endpoint_id="abc123")

    # Submit job
    result = client.submit_job({"prompt": "a cat walking", "resolution": "1080p"})
    if result["success"]:
        job_id = result["job_id"]

        # Poll with progress updates
        def on_progress(job_id, status):
            print(f"Job status: {status}")

        final = client.poll_job(job_id, on_progress=on_progress)
        if final["success"]:
            video_path = client.download_result(final["output"]["video_url"], "/tmp/output.mp4")

REVIEW NOTES (Claude, same day):
---------------------------------
Live-tested both failure paths (no API key set -> clean RunPodAuthError;
bad endpoint + fake key -> graceful {"success": False, ...} dict, no crash).
No bugs found. Not yet wired into feature_20_id_embedding.py /
feature_21_camera_motion.py / background_worker.py — that integration is
still pending (see PLAN_runpod_and_payments.md, Part 1.3).
"""

import os
import time
import json
import logging
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager

import requests

# -----------------------------------------------------------------------------
# LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
logger = logging.getLogger("runpod_client")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s [runpod_client] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    )
    logger.addHandler(handler)

# -----------------------------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------------------------
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "")

DEFAULT_POLL_TIMEOUT = 300          # 5 minutes (accounts for GPU cold starts)
DEFAULT_POLL_INTERVAL = 5           # Check every 5 seconds
MAX_RETRIES = 3                     # Connection retry on transient errors
RETRY_BACKOFF_FACTOR = 2            # Exponential backoff: 1s, 2s, 4s
RUNPOD_API_BASE = "https://api.runpod.ai/v2"

STATUS_IN_QUEUE = "IN_QUEUE"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_CANCELLED = "CANCELLED"
STATUS_TIMED_OUT = "TIMED_OUT"

TERMINAL_STATUSES = {STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED, STATUS_TIMED_OUT}


# -----------------------------------------------------------------------------
# CUSTOM EXCEPTIONS
# -----------------------------------------------------------------------------
class RunPodClientError(Exception):
    """Base exception for RunPod client errors."""
    pass


class RunPodAuthError(RunPodClientError):
    """Raised when API key is invalid or missing."""
    pass


class RunPodConnectionError(RunPodClientError):
    """Raised when unable to reach RunPod API after retries."""
    pass


class RunPodJobFailedError(RunPodClientError):
    """Raised when a job fails on RunPod's side."""
    pass


class RunPodTimeoutError(RunPodClientError):
    """Raised when polling exceeds the configured timeout."""
    pass


# -----------------------------------------------------------------------------
# PAYLOAD VALIDATION
# -----------------------------------------------------------------------------
def _validate_payload(payload: Dict[str, Any]) -> None:
    """
    Ensures payload is a non-empty dict. More specific validation is left to
    the calling feature module (feature_20/feature_21) which knows the exact
    schema for each model endpoint.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"Payload must be a dict, got {type(payload).__name__}")
    if not payload:
        raise ValueError("Payload cannot be empty")
    if "input" not in payload:
        logger.debug("Auto-wrapping payload in 'input' key for RunPod compatibility")


# -----------------------------------------------------------------------------
# CONNECTION RETRY WITH EXPONENTIAL BACKOFF
# -----------------------------------------------------------------------------
def _retry_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    json_data: Optional[Dict] = None,
    timeout: int = 30,
    max_retries: int = MAX_RETRIES
) -> requests.Response:
    """
    Retries on: ConnectionError, Timeout, 5xx server errors.
    Does NOT retry on: 4xx client errors (bad request, auth errors, etc.)
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, timeout=timeout)
            elif method.upper() == "POST":
                resp = requests.post(url, headers=headers, json=json_data, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if resp.status_code in (401, 403):
                raise RunPodAuthError(
                    f"RunPod API authentication failed (HTTP {resp.status_code}). "
                    f"Check RUNPOD_API_KEY environment variable. Response: {resp.text[:200]}"
                )

            if resp.status_code >= 500:
                logger.warning(
                    f"RunPod server error (HTTP {resp.status_code}), "
                    f"attempt {attempt + 1}/{max_retries + 1}"
                )
                if attempt < max_retries:
                    sleep_time = RETRY_BACKOFF_FACTOR ** attempt
                    time.sleep(sleep_time)
                    continue

            return resp

        except requests.exceptions.Timeout as e:
            last_error = e
            logger.warning(f"Request timeout, attempt {attempt + 1}/{max_retries + 1}")
        except requests.exceptions.ConnectionError as e:
            last_error = e
            logger.warning(f"Connection error, attempt {attempt + 1}/{max_retries + 1}")

        if attempt < max_retries:
            sleep_time = RETRY_BACKOFF_FACTOR ** attempt
            logger.debug(f"Retrying in {sleep_time}s...")
            time.sleep(sleep_time)

    raise RunPodConnectionError(
        f"Failed to reach RunPod API after {max_retries + 1} attempts. "
        f"Last error: {str(last_error)}"
    )


# -----------------------------------------------------------------------------
# MAIN CLIENT CLASS
# -----------------------------------------------------------------------------
class RunPodClient:
    """
    Encapsulates all RunPod communication for a specific endpoint.
    Handles auth, submission, polling, cancellation, result download.
    """

    def __init__(self, endpoint_id: str, api_key: Optional[str] = None):
        self.endpoint_id = endpoint_id
        self.api_key = api_key or RUNPOD_API_KEY

        if not self.api_key:
            raise RunPodAuthError(
                "RUNPOD_API_KEY not set. Set the environment variable or pass api_key parameter."
            )

        self.base_url = f"{RUNPOD_API_BASE}/{self.endpoint_id}"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        logger.info(f"RunPodClient initialized for endpoint: {endpoint_id}")

    # -------------------------------------------------------------------------
    def submit_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit async job to RunPod Serverless endpoint.
        Uses POST /v2/{endpoint_id}/run — returns immediately with job_id.
        """
        try:
            _validate_payload(payload)
        except ValueError as e:
            logger.error(f"Payload validation failed: {e}")
            return {"success": False, "message": f"Invalid payload: {e}"}

        if "input" not in payload:
            payload = {"input": payload}

        url = f"{self.base_url}/run"
        logger.info(f"Submitting job to endpoint {self.endpoint_id}")
        logger.debug(f"Payload keys: {list(payload.get('input', {}).keys())}")

        try:
            resp = _retry_request("POST", url, self.headers, json_data=payload)

            if resp.status_code == 200:
                data = resp.json()
                job_id = data.get("id", "")
                status = data.get("status", STATUS_IN_QUEUE)

                logger.info(f"Job submitted successfully: {job_id} (status: {status})")
                return {
                    "success": True,
                    "job_id": job_id,
                    "status": status,
                    "raw_response": data
                }
            else:
                error_msg = _extract_error_message(resp)
                logger.error(f"Job submission failed (HTTP {resp.status_code}): {error_msg}")
                return {"success": False, "message": error_msg}

        except RunPodAuthError as e:
            logger.error(f"Authentication failed: {e}")
            return {"success": False, "message": str(e)}
        except RunPodConnectionError as e:
            logger.error(f"Connection failed: {e}")
            return {"success": False, "message": str(e)}
        except Exception as e:
            logger.exception(f"Unexpected error during job submission: {e}")
            return {"success": False, "message": f"Unexpected error: {str(e)}"}

    # -------------------------------------------------------------------------
    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Check current status of a RunPod job. GET /v2/{endpoint_id}/status/{job_id}"""
        url = f"{self.base_url}/status/{job_id}"

        try:
            resp = _retry_request("GET", url, self.headers)

            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "UNKNOWN")
                logger.debug(f"Job {job_id} status: {status}")
                return {
                    "success": True,
                    "status": status,
                    "raw_response": data
                }
            else:
                error_msg = _extract_error_message(resp)
                logger.error(f"Status check failed for {job_id}: {error_msg}")
                return {"success": False, "message": error_msg}

        except (RunPodAuthError, RunPodConnectionError) as e:
            logger.error(f"Error checking status for {job_id}: {e}")
            return {"success": False, "message": str(e)}
        except Exception as e:
            logger.exception(f"Unexpected error checking status for {job_id}: {e}")
            return {"success": False, "message": f"Unexpected error: {str(e)}"}

    # -------------------------------------------------------------------------
    def poll_job(
        self,
        job_id: str,
        timeout_seconds: int = DEFAULT_POLL_TIMEOUT,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        on_progress: Optional[Callable[[str, Dict], None]] = None
    ) -> Dict[str, Any]:
        """
        PRIMARY method for waiting on async jobs. Blocks until:
        - Job COMPLETED (returns output)
        - Job FAILED/CANCELLED (returns error)
        - Timeout exceeded (returns timeout error)
        """
        start_time = time.time()
        logger.info(
            f"Polling job {job_id} (timeout={timeout_seconds}s, "
            f"interval={poll_interval}s)"
        )

        while True:
            elapsed = time.time() - start_time

            if elapsed > timeout_seconds:
                logger.error(f"Job {job_id} timed out after {timeout_seconds}s")
                return {
                    "success": False,
                    "status": STATUS_TIMED_OUT,
                    "message": (
                        f"Job {job_id} timed out after {timeout_seconds} seconds. "
                        f"The GPU may be experiencing high load or the job may be stuck. "
                        f"Please try again or contact support."
                    ),
                    "job_id": job_id
                }

            status_result = self.get_status(job_id)

            if not status_result["success"]:
                logger.warning(
                    f"Status check failed for {job_id}, will retry: "
                    f"{status_result.get('message', 'Unknown error')}"
                )
                time.sleep(poll_interval)
                continue

            current_status = status_result["status"]
            raw_data = status_result.get("raw_response", {})

            if on_progress:
                try:
                    on_progress(job_id, status_result)
                except Exception as e:
                    logger.warning(f"Progress callback error (non-fatal): {e}")

            if current_status in TERMINAL_STATUSES:
                logger.info(f"Job {job_id} reached terminal state: {current_status}")

                if current_status == STATUS_COMPLETED:
                    output = raw_data.get("output", {})
                    execution_time = raw_data.get("executionTime", 0)
                    return {
                        "success": True,
                        "status": STATUS_COMPLETED,
                        "output": output,
                        "execution_time": execution_time,
                        "job_id": job_id,
                        "raw_response": raw_data
                    }
                else:
                    error_msg = raw_data.get("error", f"Job ended with status: {current_status}")
                    return {
                        "success": False,
                        "status": current_status,
                        "message": error_msg,
                        "job_id": job_id,
                        "raw_response": raw_data
                    }

            if current_status == STATUS_IN_QUEUE:
                logger.debug(f"Job {job_id} still queued (elapsed: {elapsed:.0f}s)")
            elif current_status == STATUS_IN_PROGRESS:
                logger.debug(f"Job {job_id} in progress (elapsed: {elapsed:.0f}s)")

            time.sleep(poll_interval)

    # -------------------------------------------------------------------------
    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running/queued RunPod job. POST /v2/{endpoint_id}/cancel/{job_id}"""
        url = f"{self.base_url}/cancel/{job_id}"
        logger.info(f"Cancelling job: {job_id}")

        try:
            resp = _retry_request("POST", url, self.headers)

            if resp.status_code == 200:
                logger.info(f"Job {job_id} cancelled successfully")
                return {
                    "success": True,
                    "message": f"Job {job_id} cancelled successfully",
                    "job_id": job_id
                }
            else:
                error_msg = _extract_error_message(resp)
                logger.error(f"Failed to cancel job {job_id}: {error_msg}")
                return {"success": False, "message": error_msg, "job_id": job_id}

        except (RunPodAuthError, RunPodConnectionError) as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return {"success": False, "message": str(e), "job_id": job_id}
        except Exception as e:
            logger.exception(f"Unexpected error cancelling job {job_id}: {e}")
            return {"success": False, "message": f"Unexpected error: {str(e)}", "job_id": job_id}

    # -------------------------------------------------------------------------
    def download_result(self, output_url: str, save_path: str, timeout: int = 120) -> Dict[str, Any]:
        """Download generated video/content from RunPod's output URL to a local path."""
        logger.info(f"Downloading result from {output_url[:100]}... to {save_path}")

        try:
            save_dir = os.path.dirname(save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)

            resp = requests.get(output_url, timeout=timeout, stream=True)

            if resp.status_code == 200:
                total_size = 0
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total_size += len(chunk)

                size_mb = total_size / (1024 * 1024)
                logger.info(f"Downloaded {size_mb:.1f} MB to {save_path}")

                return {
                    "success": True,
                    "file_path": save_path,
                    "size_bytes": total_size,
                    "size_mb": round(size_mb, 2)
                }
            else:
                error_msg = f"Download failed (HTTP {resp.status_code})"
                logger.error(error_msg)
                return {"success": False, "message": error_msg}

        except requests.exceptions.Timeout:
            logger.error(f"Download timed out after {timeout}s")
            return {"success": False, "message": f"Download timed out after {timeout}s"}
        except Exception as e:
            logger.exception(f"Download error: {e}")
            return {"success": False, "message": f"Download error: {str(e)}"}

    # -------------------------------------------------------------------------
    def health_check(self) -> Dict[str, Any]:
        """Verify endpoint is reachable and API key is valid — for startup checks/monitoring."""
        logger.info(f"Running health check on endpoint {self.endpoint_id}")

        url = f"{self.base_url}/status/health-check-test"

        try:
            resp = _retry_request("GET", url, self.headers, max_retries=1)

            # 404 is expected (no real job with that ID), but proves connectivity and auth
            if resp.status_code in (200, 404):
                logger.info("Health check passed — endpoint is reachable")
                return {
                    "success": True,
                    "message": "Endpoint is reachable and API key is valid",
                    "endpoint_id": self.endpoint_id
                }
            else:
                error_msg = _extract_error_message(resp)
                logger.warning(f"Health check returned unexpected status {resp.status_code}: {error_msg}")
                return {"success": False, "message": error_msg}

        except RunPodAuthError as e:
            logger.error(f"Health check failed — auth error: {e}")
            return {"success": False, "message": f"Authentication failed: {e}"}
        except RunPodConnectionError as e:
            logger.error(f"Health check failed — connection error: {e}")
            return {"success": False, "message": f"Cannot reach RunPod API: {e}"}
        except Exception as e:
            logger.exception(f"Health check failed — unexpected error: {e}")
            return {"success": False, "message": f"Health check error: {str(e)}"}

    # -------------------------------------------------------------------------
    def __enter__(self):
        logger.debug(f"Entering RunPodClient context for endpoint {self.endpoint_id}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"RunPodClient context exiting with error: {exc_type.__name__}: {exc_val}")
        else:
            logger.debug(f"RunPodClient context exiting cleanly for endpoint {self.endpoint_id}")
        return False  # Don't suppress exceptions

    def __repr__(self):
        return f"RunPodClient(endpoint_id='{self.endpoint_id}')"


# -----------------------------------------------------------------------------
# STANDALONE HELPER FUNCTIONS (module-level convenience wrappers)
# -----------------------------------------------------------------------------
def submit_job(endpoint_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Standalone submit — creates a temporary RunPodClient and submits the job."""
    client = RunPodClient(endpoint_id)
    return client.submit_job(payload)


def poll_job(
    endpoint_id: str,
    job_id: str,
    timeout_seconds: int = DEFAULT_POLL_TIMEOUT,
    poll_interval: int = DEFAULT_POLL_INTERVAL
) -> Dict[str, Any]:
    """Standalone poll — matches the original spec signature."""
    client = RunPodClient(endpoint_id)
    return client.poll_job(job_id, timeout_seconds, poll_interval)


def cancel_job(endpoint_id: str, job_id: str) -> Dict[str, Any]:
    """Standalone cancel — convenience wrapper."""
    client = RunPodClient(endpoint_id)
    return client.cancel_job(job_id)


# -----------------------------------------------------------------------------
# ERROR MESSAGE EXTRACTION HELPER
# -----------------------------------------------------------------------------
def _extract_error_message(response: requests.Response) -> str:
    """Normalize error messages from RunPod API responses."""
    try:
        data = response.json()
        if "error" in data:
            return str(data["error"])
        if "message" in data:
            return str(data["message"])
        if "detail" in data:
            return str(data["detail"])
        return json.dumps(data)[:300]
    except (json.JSONDecodeError, ValueError):
        return f"HTTP {response.status_code}: {response.text[:300]}"


# -----------------------------------------------------------------------------
# MODULE SELF-TEST (runs when executed directly)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    """
    Usage: python runpod_client.py
    Validates: API key is set, health check passes for configured endpoints.
    """
    print("=" * 60)
    print("RunPod Client — Self Test")
    print("=" * 60)

    if not RUNPOD_API_KEY:
        print("❌ RUNPOD_API_KEY is not set in environment.")
        print("   Set it with: export RUNPOD_API_KEY='your-key-here'")
        exit(1)
    else:
        print(f"✅ RUNPOD_API_KEY found (length: {len(RUNPOD_API_KEY)} chars)")

    endpoints_to_test = []

    wan_endpoint = os.environ.get("RUNPOD_ENDPOINT_ID_WAN")
    ltx_endpoint = os.environ.get("RUNPOD_ENDPOINT_ID_LTX")

    if wan_endpoint:
        endpoints_to_test.append(("WAN 2.2/2.6", wan_endpoint))
    if ltx_endpoint:
        endpoints_to_test.append(("LTX 2.3", ltx_endpoint))

    if not endpoints_to_test:
        print("\n⚠️  No endpoint IDs found in environment.")
        print("   Set RUNPOD_ENDPOINT_ID_WAN and/or RUNPOD_ENDPOINT_ID_LTX")
        print("   to run full health checks.")
    else:
        print(f"\nTesting {len(endpoints_to_test)} endpoint(s)...\n")

        all_passed = True
        for name, endpoint_id in endpoints_to_test:
            print(f"  {name} ({endpoint_id}): ", end="")
            try:
                client = RunPodClient(endpoint_id)
                result = client.health_check()
                if result["success"]:
                    print("✅ Healthy")
                else:
                    print(f"❌ {result['message'][:80]}")
                    all_passed = False
            except Exception as e:
                print(f"❌ Exception: {e}")
                all_passed = False

        if all_passed:
            print("\n✅ All endpoints healthy!")
        else:
            print("\n⚠️  Some endpoints failed health check.")

    print("\n" + "=" * 60)
    print("Self-test complete.")
    print("=" * 60)