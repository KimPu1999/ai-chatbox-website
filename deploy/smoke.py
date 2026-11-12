"""Non-authenticated deployment smoke checks; never calls OpenAI or mutates data."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def check(base_url: str, path: str, expected: set[int]) -> None:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=10) as response:
            body = response.read(4096)
            if response.status not in expected:
                raise RuntimeError(f"{path}: unexpected status {response.status}")
            if path == "/health":
                payload = json.loads(body)
                if payload.get("status") != "ok":
                    raise RuntimeError(f"{path}: health status is not ok")
            print(f"PASS {path} ({response.status})")
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"FAIL {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    if not args.base_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        raise SystemExit("Refusing non-HTTPS smoke target outside local development")
    check(args.base_url, "/health", {200})
    check(args.base_url, "/api/v1/health", {200})
    check(args.base_url, "/health/ready", {200})
    return 0


if __name__ == "__main__":
    sys.exit(main())
