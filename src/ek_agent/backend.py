from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any

import certifi


class BackendClient:
    def __init__(self, base_url: str, access_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token

    def next_job(self) -> dict[str, Any] | None:
        status, body = self._request("/agents/jobs/next")
        return body if status == 200 else None

    def complete(self, job: dict[str, Any], result: dict[str, Any]) -> None:
        self._request(
            f"/agencies/{job['agencyId']}/clients/{job['clientId']}/ai/jobs/{job['jobId']}/complete",
            method="POST",
            body={"result": result},
        )

    def _request(
        self, path: str, method: str = "GET", body: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(
                request, timeout=30, context=ssl.create_default_context(cafile=certifi.where())
            ) as response:
                raw = response.read()
                return response.status, json.loads(raw or b"{}")
        except urllib.error.HTTPError as error:
            if error.code == 204:
                return 204, {}
            raise
