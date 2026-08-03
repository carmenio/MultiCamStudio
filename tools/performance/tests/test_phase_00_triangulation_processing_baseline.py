"""Tests for deterministic production triangulation measurements."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.performance.config import DEFAULT_COMPARISON_METADATA_KEYS
from tools.performance.phase_00_triangulation_processing_baseline import (
    TriangulationProcessingConfig,
    build_triangulation_processing_baseline,
)


class TriangulationProcessingBaselineTests(unittest.TestCase):
    """Protect fixture identity, accepted work, and long-workflow evidence."""

    def test_runner_persists_verified_fixed_triangulation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "triangulation.json"
            outcome = build_triangulation_processing_baseline(
                TriangulationProcessingConfig(
                    output_path=output_path,
                    frame_count=4,
                    point_count=3,
                )
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        result = outcome["result"]
        self.assertEqual(result.measured_runs, 5)
        self.assertEqual(len(result.durations_ms), 5)
        self.assertEqual(result.failures, ())
        self.assertEqual(result.unit_name, "accepted_3d_points")
        self.assertEqual(saved["metadata"]["accepted_3d_points"], 12)
        self.assertEqual(saved["metadata"]["observations_total"], 36)
        self.assertTrue(saved["metadata"]["coordinate_transform"]["applied"])
        self.assertEqual(len(saved["metadata"]["fixture_identity"]), 64)
        self.assertEqual(len(saved["metadata"]["expected_output_identity"]), 64)
        self.assertTrue(
            set(DEFAULT_COMPARISON_METADATA_KEYS).issubset(saved["metadata"])
        )


if __name__ == "__main__":
    unittest.main()
