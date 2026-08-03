"""Tests for deterministic production calibration processing measurements."""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

from tools.performance.config import DEFAULT_COMPARISON_METADATA_KEYS
from tools.performance.phase_00_calibration_processing_baseline import (
    CAMERA_NAMES,
    EXPECTED_RESULT_IDENTITY,
    EXPECTED_TOML_IDENTITY,
    CalibrationProcessingConfig,
    PreparedCalibrationFixture,
    _benchmark_prepared_fixture,
    _canonical,
    _clear_verified_output_dir,
    _result_identity,
)


class _FakeArtifacts:
    """Provides the two artifact paths consumed by the benchmark boundary."""

    def __init__(self, output_dir: Path) -> None:
        self.calibration_toml_path = output_dir / "camera_calibration.toml"
        self.calibration_yaml_path = output_dir / "camera_calibration.yaml"


class _FakeCalibrationRunner:
    """Writes deterministic artifacts without invoking the expensive solver."""

    calls = 0
    result = {
        "intrinsics": {name: {"rms": None} for name in CAMERA_NAMES},
        "extrinsics": {name: {"rms": None} for name in CAMERA_NAMES},
    }
    toml_bytes = b"deterministic calibration\n"

    def __init__(self, config) -> None:
        self._config = config

    def run(self):
        type(self).calls += 1
        self._config.output_dir.mkdir(parents=True, exist_ok=True)
        artifacts = _FakeArtifacts(self._config.output_dir)
        artifacts.calibration_toml_path.write_bytes(self.toml_bytes)
        artifacts.calibration_yaml_path.write_text("cameras: {}\n", encoding="utf-8")
        return self.result, artifacts


class CalibrationProcessingBaselineTests(unittest.TestCase):
    """Protect solver configuration, safe cleanup, and report evidence."""

    def test_default_configuration_freezes_real_fixture_and_seeded_outputs(
        self,
    ) -> None:
        config = CalibrationProcessingConfig()

        self.assertEqual(config.start_frame, 500)
        self.assertEqual(config.clip_frame_count, 120)
        self.assertEqual(config.warmup_runs, 3)
        self.assertEqual(config.measured_runs, 5)
        self.assertEqual(config.expected_toml_identity, EXPECTED_TOML_IDENTITY)
        self.assertEqual(config.expected_result_identity, EXPECTED_RESULT_IDENTITY)
        self.assertEqual(config.clip_sizes, (4_086_441, 5_781_290))

    def test_canonical_result_replaces_only_non_finite_floats(self) -> None:
        payload = {"z": [math.inf, -math.inf, math.nan, 1.25], "a": {"b": 2}}

        self.assertEqual(
            _canonical(payload),
            {"a": {"b": 2}, "z": [None, None, None, 1.25]},
        )
        self.assertEqual(_result_identity(payload), _result_identity(payload))

    def test_output_cleanup_rejects_paths_outside_temporary_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory) / "fixture"
            temporary_root.mkdir()
            outside = Path(directory) / "outside"
            outside.mkdir()

            with self.assertRaisesRegex(ValueError, "refusing to clear"):
                _clear_verified_output_dir(outside, temporary_root)

    def test_fake_runner_persists_long_workflow_schema_without_real_solve(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            clips = (temporary_root / "camera_0.mp4", temporary_root / "camera_1.mp4")
            for clip in clips:
                clip.write_bytes(b"fixture")
            fixture = PreparedCalibrationFixture(
                temporary_root=temporary_root,
                video_inputs=clips,
                clip_identities=("a" * 64, "b" * 64),
                clip_sizes=(7, 7),
            )
            output_path = temporary_root / "report.json"
            config = CalibrationProcessingConfig(
                output_path=output_path,
                warmup_runs=3,
                measured_runs=5,
                expected_toml_identity=hashlib.sha256(
                    _FakeCalibrationRunner.toml_bytes
                ).hexdigest(),
                expected_result_identity=_result_identity(
                    _FakeCalibrationRunner.result
                ),
            )
            _FakeCalibrationRunner.calls = 0

            outcome = _benchmark_prepared_fixture(
                config, fixture, _FakeCalibrationRunner
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        result = outcome["result"]
        self.assertEqual(_FakeCalibrationRunner.calls, 8)
        self.assertEqual(result.measured_runs, 5)
        self.assertEqual(len(result.durations_ms), 5)
        self.assertEqual(result.failures, ())
        self.assertEqual(result.unit_name, "camera_frames")
        self.assertEqual(result.work_units, (240.0,) * 5)
        self.assertEqual(
            saved["metadata"]["fixture"]["camera_names"], ["anna", "chris"]
        )
        self.assertEqual(saved["metadata"]["fixture"]["board"]["columns"], 7)
        self.assertEqual(
            saved["metadata"]["fixture"]["source_frame_range_inclusive"], [500, 619]
        )
        self.assertTrue(
            set(DEFAULT_COMPARISON_METADATA_KEYS).issubset(saved["metadata"])
        )


if __name__ == "__main__":
    unittest.main()
