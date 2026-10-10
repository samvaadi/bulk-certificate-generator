"""Benchmark a 100-recipient certificate batch against a running API."""
import argparse
import time

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--poll-interval", type=float, default=0.5, help="Seconds between status checks")
    parser.add_argument("--timeout", type=float, default=300, help="Maximum seconds to wait for completion")
    args = parser.parse_args()
    payload = {
        "event_name": "Certificate Benchmark",
        "recipients": [
            {"recipient_name": f"Benchmark Recipient {i:03d}", "recipient_email": f"benchmark{i:03d}@example.com"}
            for i in range(1, 101)
        ],
    }
    started = time.perf_counter()
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=30) as client:
        response = client.post("/api/v1/jobs", json=payload)
        response.raise_for_status()
        job = response.json()
        deadline = started + args.timeout
        while True:
            status_response = client.get(job["status_check_url"])
            status_response.raise_for_status()
            result = status_response.json()
            if result["status"] in {"COMPLETED", "PARTIALLY_COMPLETED", "FAILED"}:
                break
            if time.perf_counter() >= deadline:
                raise TimeoutError(f"Job {job['job_id']} did not finish within {args.timeout:g} seconds")
            time.sleep(args.poll_interval)
    elapsed = time.perf_counter() - started
    completed = result["completed_count"]
    print(f"job_id: {job['job_id']}")
    print(f"status: {result['status']}")
    print(f"certificates: {completed}/{result['total_count']} successful, {result['failed_count']} failed")
    print(f"execution_time_seconds: {elapsed:.2f}")
    print(f"throughput_certificates_per_second: {completed / elapsed:.2f}" if elapsed else "throughput_certificates_per_second: n/a")
    if result["status"] != "COMPLETED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
