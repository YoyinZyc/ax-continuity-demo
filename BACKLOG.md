# Sliding-Window Rate Limiter — Autonomous Engineering Backlog

This repository is developed autonomously by an **ADK Coding Agent** running on **AX + Agent Substrate**.

## 4-Stage Engineering Plan

1. **Stage 1 — Core Implementation (`src/rate_limiter.py`)**:
   - Implement a thread-safe `SlidingWindowRateLimiter(max_requests: int, window_seconds: float)` class in `src/rate_limiter.py` with `allow(client_id: str) -> bool` and `remaining(client_id: str) -> int`.
   - Commit and push Stage 1 to GitHub.

2. **Stage 2 — Unit Test Suite (`tests/test_rate_limiter.py`)**:
   - Create `tests/test_rate_limiter.py` covering basic allow/deny, per-client isolation, and window expiration.
   - Run `pytest` to verify all tests pass.
   - Commit and push Stage 2 to GitHub.

3. **Stage 3 — Cloud Throughput Benchmark (`benchmark.py`)**:
   - Create and run `benchmark.py` measuring throughput (ops/sec) across 1,000 simulated requests.
   - Save benchmark metrics and commit/push Stage 3 to GitHub.

4. **Stage 4 — Release Readiness Report (`RELEASE_REPORT.md`)**:
   - Synthesize the full cross-cluster engineering history (recalling local Stages 1–2 from Vertex AI Session & Memory Bank plus remote Stage 3 benchmark metrics) into `RELEASE_REPORT.md`.
   - Commit and push Stage 4 to GitHub.
