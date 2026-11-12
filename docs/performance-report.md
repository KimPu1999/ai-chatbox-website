# Performance report

## Changes in Phase 9

- Added request timing logs and correlation IDs to make latency measurable.
- Added lazy loading for platform pages so Recharts/admin screens are not part
  of the initial user route bundle.
- Kept cursor pagination and ownership indexes for conversations/documents.
- Kept vector retrieval exact/index-backed behavior unchanged; no unmeasured HNSW
  change was applied.

## Baseline and verification

The only repeatable local measurement completed in this workspace was an
in-process ASGI health check with the database-independent `/health` route:

```text
100 requests: p50=2.545ms, p95=3.408ms, p99=4.118ms, max=23.779ms
```

This is not a network, PostgreSQL, Redis, worker, or production baseline. The
workspace did not provide a repeatable production-like load target, hardware
profile, or authorized 5/20/50/100-user run, so no production P50/P95/P99
budget is claimed. Run the isolated Locust profile with:

```bash
python -m venv /tmp/pychat-locust
/tmp/pychat-locust/bin/pip install -r perf/requirements.txt
PYCHAT_LOAD_TEST_ACK=isolated /tmp/pychat-locust/bin/locust \
  -f perf/locustfile.py --host http://127.0.0.1:8000 \
  --headless -u 5 -r 1 -t 60s --csv=/tmp/pychat-health-5
```

Run only against a disposable/local or explicitly authorized environment. The
profile does not call OpenAI and does not mutate data. Record CPU, memory,
PostgreSQL and Redis latency next to the Locust CSV before setting release
budgets.
