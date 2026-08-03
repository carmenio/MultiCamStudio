"""Tests for deterministic production point-processing measurements."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.performance.config import DEFAULT_COMPARISON_METADATA_KEYS
from tools.performance.phase_00_detection_processing_baseline import (
    DetectionProcessingConfig,
    build_detection_processing_baseline,
)


class DetectionProcessingBaselineTests(unittest.TestCase):
    """Protect run counts, stage order, segments, and persisted identities."""

    def test_runner_records_two_verified_long_workflow_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "detection.json"
            outcome = build_detection_processing_baseline(
                DetectionProcessingConfig(
                    output_path=output_path,
                    camera_count=2,
                    frame_count=12,
                    point_count=4,
                )
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(len(outcome["results"]), 2)
        self.assertTrue(all(result.measured_runs == 5 for result in outcome["results"]))
        self.assertTrue(all(not result.failures for result in outcome["results"]))
        self.assertTrue(all(result.unit_name == "keypoints" for result in outcome["results"]))
        self.assertEqual(saved["metadata"]["camera_count"], 2)
        self.assertEqual(
            saved["metadata"]["stage_order"],
            [
                "confidence_filter",
                "motion_prediction",
                "outlier_rejection",
                "gap_fill",
                "smoothing",
                "rigid_body_correction",
            ],
        )
        self.assertEqual(saved["metadata"]["segments_per_camera"], [1, 1])
        self.assertTrue(
            all(
                len(identity) == 64
                for identity in saved["metadata"]["expected_output_identity"].values()
            )
        )
        self.assertTrue(
            set(DEFAULT_COMPARISON_METADATA_KEYS).issubset(saved["metadata"])
        )


if __name__ == "__main__":
    unittest.main()
