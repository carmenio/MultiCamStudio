"""Tests for deterministic production-code export writing measurements."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.performance.phase_00_export_writing_baseline import (
    ExportWritingConfig,
    build_export_writing_baseline,
)


class ExportWritingBaselineTests(unittest.TestCase):
    def test_runner_persists_five_verified_long_workflow_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "writing.json"
            outcome = build_export_writing_baseline(
                ExportWritingConfig(
                    output_path=output_path,
                    frame_count=3,
                    point_count=2,
                )
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        result = outcome["result"]
        self.assertEqual(result.measured_runs, 5)
        self.assertEqual(len(result.durations_ms), 5)
        self.assertEqual(result.failures, ())
        self.assertEqual(result.unit_name, "bytes")
        self.assertGreater(result.throughput_per_second or 0, 0)
        self.assertEqual(saved["metadata"]["fixture"]["frame_count"], 3)
        self.assertEqual(len(saved["metadata"]["expected_output_identity"]), 64)

    def test_fixture_output_is_identical_across_independent_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            first = build_export_writing_baseline(
                ExportWritingConfig(
                    output_path=directory / "first.json",
                    frame_count=2,
                    point_count=2,
                )
            )
            second = build_export_writing_baseline(
                ExportWritingConfig(
                    output_path=directory / "second.json",
                    frame_count=2,
                    point_count=2,
                )
            )

        self.assertEqual(
            first["metadata"]["expected_output_identity"],
            second["metadata"]["expected_output_identity"],
        )
        self.assertEqual(
            first["metadata"]["output_bytes_per_export"],
            second["metadata"]["output_bytes_per_export"],
        )


if __name__ == "__main__":
    unittest.main()
