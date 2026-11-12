# Scaling report

The current bounded configuration uses the existing SQLAlchemy pool, Redis
rate limiting, ARQ worker concurrency of two document jobs, provider timeouts,
and database-backed generation lifecycle state. No process-local generation
registry was introduced.

Phase 11 adds no unmeasured capacity claim. Before increasing replicas, collect
P50/P95/P99 API latency, SSE time-to-first-token, Neon pool wait time, Redis
queue lag, pgvector query latency, worker memory and R2 transfer time in an
isolated staging environment. Record baseline and post-change values here.
