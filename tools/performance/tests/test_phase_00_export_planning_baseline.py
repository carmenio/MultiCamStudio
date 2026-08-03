"""Tests for production-contract export planning measurements."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.performance.config import DEFAULT_COMPARISON_METADATA_KEYS
from tools.performance.phase_00_export_planning_baseline import (
    ExportPlanningConfig,
    JsonResponse,
    _semantic_preflight_identity,
    build_export_planning_baseline,
)


class FakePlanningClient:
    """Returns a deterministic eligible plan and records every POST."""

    def __init__(self) -> None:
        self.calls = []

    def post_json(self, url, payload):
        self.calls.append((url, payload))
        return JsonResponse(
            200,
            json.dumps(
                {
                    "data": {
                        "eligible_count": 1,
                        "blocked_count": 0,
                        "preflight_hash": "reviewed-hash",
                        "destination": {"path": "/exports", "free_bytes": 100},
                        "sets": [{"session_id": 49, "recording_set_id": 178}],
                    }
                }
            ).encode("utf-8"),
        )


class ExportPlanningBaselineTests(unittest.TestCase):
    def test_runner_uses_only_preflight_and_persists_ten_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config = ExportPlanningConfig(
                preflight_url="https://pc/api/exports/preflight",
                output_path=Path(temporary_directory) / "planning.json",
            )
            client = FakePlanningClient()
            outcome = build_export_planning_baseline(config, client=client)
            saved = json.loads(config.output_path.read_text(encoding="utf-8"))

        self.assertEqual(len(client.calls), 13)
        self.assertTrue(all(call[0].endswith("/api/exports/preflight") for call in client.calls))
        self.assertEqual(outcome["result"].measured_runs, 10)
        self.assertEqual(saved["results"][0]["failure_count"], 0)
        self.assertEqual(saved["metadata"]["preflight_hash"], "reviewed-hash")
        self.assertTrue(
            set(DEFAULT_COMPARISON_METADATA_KEYS).issubset(saved["metadata"])
        )
        self.assertEqual(saved["metadata"]["camera_count"], 3)
        self.assertEqual(len(saved["metadata"]["recording_duration_seconds"]), 3)
        self.assertEqual(len(saved["metadata"]["media_sizes_bytes"]), 3)

    def test_semantic_identity_excludes_only_volatile_free_space(self) -> None:
        first = {
            "data": {
                "eligible_count": 1,
                "destination": {"path": "/exports", "free_bytes": 100},
            }
        }
        second = {
            "data": {
                "eligible_count": 1,
                "destination": {"path": "/exports", "free_bytes": 90},
            }
        }
        changed = {
            "data": {
                "eligible_count": 0,
                "destination": {"path": "/exports", "free_bytes": 90},
            }
        }

        self.assertEqual(
            _semantic_preflight_identity(first),
            _semantic_preflight_identity(second),
        )
        self.assertNotEqual(
            _semantic_preflight_identity(first),
            _semantic_preflight_identity(changed),
        )


if __name__ == "__main__":
    unittest.main()
