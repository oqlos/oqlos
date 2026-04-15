"""Hardware performance benchmark."""

from __future__ import annotations

import statistics
import time


def run_benchmark(url: str = "http://localhost:8202", duration: int = 10) -> dict:
    """Run HTTP performance benchmark against firmware health endpoint.

    Args:
        url:      Firmware base URL.
        duration: Test duration in seconds (default 10).

    Returns:
        dict with latency statistics and request counts, or {"error": ...} on failure.
    """
    try:
        import httpx
    except ImportError:
        return {"error": "httpx not installed — pip install httpx"}

    latencies: list[float] = []
    errors = 0
    start_time = time.time()

    print(f"\n⏱️  Running benchmark for {duration}s...")

    with httpx.Client() as client:
        while time.time() - start_time < duration:
            try:
                t0 = time.time()
                r = client.get(f"{url}/api/v1/hardware/health", timeout=1.0)
                latency_ms = (time.time() - t0) * 1000
                if r.status_code == 200:
                    latencies.append(latency_ms)
                else:
                    errors += 1
            except Exception:
                errors += 1
            time.sleep(0.1)  # cap at ~10 req/s

    if not latencies:
        return {"error": "No successful requests", "errors": errors}

    return {
        "requests": len(latencies),
        "errors": errors,
        "latency_min_ms": min(latencies),
        "latency_max_ms": max(latencies),
        "latency_avg_ms": statistics.mean(latencies),
        "latency_median_ms": statistics.median(latencies),
        "rps": len(latencies) / duration,
    }
