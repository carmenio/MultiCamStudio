"""Tests for deterministic calibration video-preflight measurements."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.performance.phase_00_calibration_preflight_baseline import (
    CalibrationPreflightConfig,
    _canonical_identity,
    build_calibration_preflight_baseline,
)


class _FakeProbe:
    """Returns stable production-shaped metadata without decoding test bytes."""

    def _probe_video_metadata(self, _path: str):
        return {"frame_count": 120, "fps": 60.0, "duration_seconds": 2.0}

    def _probe_video_readability(self, _path: str):
        return {"usable": True}


class CalibrationPreflightBaselineTests(unittest.TestCase):
    """Protect fixed run counts, identities, and evidence boundaries."""

    def test_runner_records_four_camera_probe_throughput(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = tuple(f"camera-{index}.mp4" for index in range(4))
            for index, name in enumerate(names):
                (root / name).write_bytes(bytes([index]) * (index + 1))
            sizes = tuple((root / name).stat().st_size for name in names)
            identities = tuple(
                hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names
            )
            expected_payload = [
                {
                    "filename": name,
                    "size_bytes": sizes[index],
                    "metadata": {"frame_count": 120, "fps": 60.0, "duration_seconds": 2.0},
                    "readability": {"usable": True},
                }
                for index, name in enumerate(names)
            ]
            output_path = root / "report.json"
            outcome = build_calibration_preflight_baseline(
                CalibrationPreflightConfig(
                    output_path=output_path,
                    source_directory=root,
                    source_files=names,
                    source_sizes=sizes,
                    source_identities=identities,
                    expected_output_identity=_canonical_identity(expected_payload),
                ),
                service_factory=_FakeProbe,
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        result = outcome["result"]
        self.assertEqual(result.measured_runs, 10)
        self.assertFalse(result.failures)
        self.assertEqual(result.work_units, (4.0,) * 10)
        self.assertEqual(result.unit_name, "videos_preflighted")
        self.assertEqual(saved["metadata"]["fixture"]["recording_set_id"], 201)
        self.assertIn("not full calibration", saved["metadata"]["evidence_scope"])

    def test_runner_rejects_misaligned_source_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be non-empty and aligned"):
            build_calibration_preflight_baseline(
                CalibrationPreflightConfig(source_files=("one.mp4",), source_sizes=())
            )

    def test_runner_rejects_malformed_source_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "64-character SHA256"):
            build_calibration_preflight_baseline(
                CalibrationPreflightConfig(
                    source_files=("one.mp4",),
                    source_sizes=(1,),
                    source_identities=("not-a-sha256",),
                )
            )


if __name__ == "__main__":
    unittest.main()
