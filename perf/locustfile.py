"""Bounded, provider-free Locust scenarios for an isolated environment.

Run only against an explicitly authorized test/staging target. These users call
read-only health and public API guards; they never call OpenAI or mutate data.
Authenticated scenarios can be added with short-lived test cookies through the
environment, but are intentionally not enabled by default.
"""

import os

from locust import HttpUser, between, task


class PyChatHealthUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task(5)
    def health(self):
        self.client.get("/health", name="GET /health")

    @task(1)
    def public_auth_guard(self):
        self.client.get("/api/v1/auth/me", name="GET /api/v1/auth/me (guard)")

    def on_start(self):
        if os.getenv("PYCHAT_LOAD_TEST_ACK") != "isolated":
            raise RuntimeError(
                "Set PYCHAT_LOAD_TEST_ACK=isolated before running performance tests"
            )
