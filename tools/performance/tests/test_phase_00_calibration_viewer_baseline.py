"""Tests for deterministic production calibration viewer measurements."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.performance.config import DEFAULT_COMPARISON_METADATA_KEYS
from tools.performance.phase_00_calibration_viewer_baseline import (
    CalibrationViewerConfig,
    build_calibration_viewer_baseline,
)


class CalibrationViewerBaselineTests(unittest.TestCase):
    """Protect render counts, camera throughput, and exact output evidence."""

    def test_runner_persists_ten_equivalent_viewer_renders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "viewer.json"
            outcome = build_calibration_viewer_baseline(
                CalibrationViewerConfig(output_path=output_path, camera_count=3)
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        result = outcome["result"]
        self.assertEqual(result.measured_runs, 10)
        self.assertEqual(len(result.durations_ms), 10)
        self.assertEqual(result.failures, ())
        self.assertEqual(result.unit_name, "cameras")
        self.assertEqual(saved["metadata"]["camera_count"], 3)
        self.assertGreater(saved["metadata"]["output_bytes"], 1_000)
        self.assertEqual(len(saved["metadata"]["expected_output_identity"]), 64)
        self.assertTrue(
            set(DEFAULT_COMPARISON_METADATA_KEYS).issubset(saved["metadata"])
        )


if __name__ == "__main__":
    unittest.main()
