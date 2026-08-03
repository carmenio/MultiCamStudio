"""Tests for restart-controlled service-cold performance evidence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.performance.phase_00_live_baseline import ReadOnlyResponse
from tools.performance.phase_00_service_cold_baseline import (
    ServiceColdConfig,
    build_service_cold_baseline,
)


class FakeRestarter:
    """Counts isolated backend restarts without touching Docker."""

    def __init__(self) -> None:
        self.calls = 0

    def restart(self) -> None:
        self.calls += 1


class FakeColdClient:
    """Returns a stable health check and first-request payload."""

    def __init__(self, health_url: str, target_url: str) -> None:
        self.health_url = health_url
        self.target_url = target_url
        self.target_headers: list[dict[str, str]] = []

    def get(self, url: str, headers=None) -> ReadOnlyResponse:
        if url == self.health_url:
            return ReadOnlyResponse(200, b'{"status":"ok"}', {})
        if url == self.target_url:
            self.target_headers.append(dict(headers or {}))
            return ReadOnlyResponse(200, b'{"data":{"49":{"name":"fixture"}}}', {})
        return ReadOnlyResponse(404, b'{"error":"missing"}', {})


class ServiceColdBaselineTests(unittest.TestCase):
    def test_each_warmup_and_measurement_restarts_before_the_first_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "cold.json"
            config = ServiceColdConfig(
                health_url="https://pc/health",
                target_url="https://pc/api/sessions-info?profile=ui",
                output_path=output,
                readiness_poll_seconds=0.001,
            )
            client = FakeColdClient(config.health_url, config.target_url)
            restarter = FakeRestarter()

            outcome = build_service_cold_baseline(
                config,
                client=client,
                restarter=restarter,
            )
            saved = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(restarter.calls, 13)
        self.assertEqual(len(client.target_headers), 13)
        self.assertTrue(
            all(
                headers == {"X-MCS-Benchmark-Cache": "service-cold"}
                for headers in client.target_headers
            )
        )
        self.assertEqual(outcome["result"].measured_runs, 10)
        self.assertEqual(len(outcome["metadata"]["restart_readiness_durations_ms"]), 13)
        self.assertEqual(saved["results"][0]["cache_state"], "cold")
        self.assertTrue(saved["metadata"]["expected_output_identity"])


if __name__ == "__main__":
    unittest.main()
