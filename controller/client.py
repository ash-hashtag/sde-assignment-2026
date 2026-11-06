"""Thin HTTP client for the simulator.

Transport failures and 5xx are retried with backoff (every call we make is either a read or carries its own
idempotency key, so a retry can't double-apply). 4xx responses are returned to the caller as `ApiResult`
so governance code can branch on the error code instead of catching exceptions.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Iterator

import httpx

log = logging.getLogger(__name__)


@dataclass
class ApiResult:
    status: int
    body: Any

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def code(self) -> str | None:
        return self.body.get("error") if isinstance(self.body, dict) else None


class SimClient:
    def __init__(self, base_url: str, timeout: float = 300.0, retries: int = 8):
        self.http = httpx.Client(base_url=base_url, timeout=timeout)
        self.retries = retries

    def _request(self, method: str, path: str, **kw) -> ApiResult:
        delay = 0.5
        for attempt in range(self.retries + 1):
            try:
                r = self.http.request(method, path, **kw)
            except httpx.TransportError as e:
                if attempt == self.retries:
                    raise
                log.warning("transport error on %s %s (%s), retrying in %.1fs", method, path, e, delay)
            else:
                if r.status_code < 500:
                    try:
                        body = r.json()
                    except ValueError:
                        body = r.text
                    return ApiResult(r.status_code, body)
                if attempt == self.retries:
                    r.raise_for_status()
                log.warning("%s on %s %s, retrying in %.1fs", r.status_code, method, path, delay)
            time.sleep(delay)
            delay = min(delay * 2, 30)
        raise RuntimeError("unreachable")

    def get(self, path: str, **params) -> ApiResult:
        return self._request("GET", path, params={k: v for k, v in params.items() if v is not None})

    def post(self, path: str, body: dict) -> ApiResult:
        return self._request("POST", path, json=body)

    def put(self, path: str, body: dict) -> ApiResult:
        return self._request("PUT", path, json=body)

    def must(self, res: ApiResult) -> Any:
        if not res.ok:
            raise RuntimeError(f"unexpected API response {res.status}: {res.body}")
        return res.body

    # -- convenience
    def state(self) -> dict:
        return self.must(self.get("/sim/state"))

    def workflows(self) -> list[dict]:
        return self.must(self.get("/workflows"))

    def config(self, wid: str) -> dict:
        return self.must(self.get(f"/workflows/{wid}/config"))

    def config_history(self, wid: str) -> list[dict]:
        return self.must(self.get(f"/workflows/{wid}/config/history"))

    def chunks(self, kind: str, after: int) -> list[dict]:
        return self.must(self.get("/events/chunks", kind=kind, after=after))

    def chunk_events(self, n: int) -> Iterator[dict]:
        """Downloads the whole chunk first (so a dropped connection is retried cleanly), then parses lazily."""
        delay = 0.5
        for attempt in range(self.retries + 1):
            try:
                r = self.http.get(f"/events/chunks/{n}")
                r.raise_for_status()
                return (json.loads(line) for line in r.content.splitlines() if line)
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                if attempt == self.retries:
                    raise
                log.warning("chunk %d fetch failed (%s), retrying", n, e)
                time.sleep(delay)
                delay = min(delay * 2, 30)
        raise RuntimeError("unreachable")
