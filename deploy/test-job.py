#!/usr/bin/env python3
"""
deploy/test-job.py
Send a test job directly to a RunPod serverless endpoint and poll for the result.

Usage:
    RUNPOD_API_KEY=xxx RUNPOD_ENDPOINT=https://api.runpod.ai/v2/<id> python deploy/test-job.py

Optional env vars (override defaults):
    TEST_ROOM_ID   — fake room UUID to pass in job input
    TEST_MODE      — processing mode: real | staged | both  (default: real)
    TEST_STYLE     — style preset: modern | scandinavian | luxury  (default: modern)
"""

import os
import sys
import json
import time
import uuid
import httpx

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("RUNPOD_API_KEY")
ENDPOINT = os.environ.get("RUNPOD_ENDPOINT")  # e.g. https://api.runpod.ai/v2/abc123

if not API_KEY:
    print("ERROR: RUNPOD_API_KEY environment variable is not set")
    sys.exit(1)
if not ENDPOINT:
    print("ERROR: RUNPOD_ENDPOINT environment variable is not set")
    sys.exit(1)

ENDPOINT = ENDPOINT.rstrip("/")

TEST_ROOM_ID   = os.environ.get("TEST_ROOM_ID",  str(uuid.uuid4()))
TEST_TOUR_ID   = str(uuid.uuid4())
TEST_AGENT_ID  = str(uuid.uuid4())
TEST_MODE      = os.environ.get("TEST_MODE",  "real")
TEST_STYLE     = os.environ.get("TEST_STYLE", "modern")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

POLL_INTERVAL_S = 5    # seconds between status checks
MAX_WAIT_S      = 600  # 10 minutes max

# ---------------------------------------------------------------------------
# Submit job
# ---------------------------------------------------------------------------
def submit_job(client: httpx.Client) -> str:
    payload = {
        "input": {
            "room_id":      TEST_ROOM_ID,
            "tour_id":      TEST_TOUR_ID,
            "agent_id":     TEST_AGENT_ID,
            "mode":         TEST_MODE,
            "style":        TEST_STYLE,
            "prompt":       None,
            "input_folder": f"rooms-input/{TEST_AGENT_ID}/{TEST_ROOM_ID}/",
        }
    }

    print(f"Submitting test job to: {ENDPOINT}/run")
    print(f"  room_id: {TEST_ROOM_ID}")
    print(f"  mode:    {TEST_MODE}")
    print(f"  style:   {TEST_STYLE}")
    print()

    resp = client.post(f"{ENDPOINT}/run", json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    job_id = data.get("id")
    if not job_id:
        print("ERROR: No job ID returned by RunPod")
        print("Response:", json.dumps(data, indent=2))
        sys.exit(1)

    print(f"Job submitted — ID: {job_id}")
    return job_id

# ---------------------------------------------------------------------------
# Poll for result
# ---------------------------------------------------------------------------
def poll_job(client: httpx.Client, job_id: str) -> dict:
    status_url = f"{ENDPOINT}/status/{job_id}"
    elapsed = 0

    while elapsed < MAX_WAIT_S:
        resp = client.get(status_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status", "UNKNOWN")
        print(f"[{elapsed:>4}s] Status: {status}")

        if status == "COMPLETED":
            return data
        if status in ("FAILED", "CANCELLED", "TIMED_OUT"):
            print("ERROR: Job failed")
            print(json.dumps(data, indent=2))
            sys.exit(1)

        time.sleep(POLL_INTERVAL_S)
        elapsed += POLL_INTERVAL_S

    print(f"ERROR: Job did not complete within {MAX_WAIT_S}s")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    with httpx.Client() as client:
        job_id = submit_job(client)
        result = poll_job(client, job_id)

    print()
    print("=== Job completed ===")
    output = result.get("output", {})
    print(json.dumps(output, indent=2))

    # Basic sanity checks on output
    expected_keys = ["panorama_url", "status"]
    missing = [k for k in expected_keys if k not in output]
    if missing:
        print(f"\nWARNING: Output missing expected keys: {missing}")
        sys.exit(1)

    print(f"\nPanorama URL: {output.get('panorama_url')}")
    print("Test PASSED")

if __name__ == "__main__":
    main()
