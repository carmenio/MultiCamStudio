"""Tests for deterministic PC resumable-upload route measurements."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.performance.phase_00_resumable_upload_baseline import (
    ResumableUploadConfig,
    build_resumable_upload_baseline,
)


class ResumableUploadBaselineTests(unittest.TestCase):
    """Protect route coverage, run counts, throughput, and evidence scope."""

    def test_runner_records_init_resume_chunk_and_completion_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "upload.json"
            outcome = build_resumable_upload_baseline(
                ResumableUploadConfig(
                    output_path=output_path,
                    total_bytes=32 * 1024,
                    chunk_count=4,
                )
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(len(outcome["results"]), 4)
        self.assertTrue(all(result.measured_runs == 10 for result in outcome["results"]))
        self.assertTrue(all(not result.failures for result in outcome["results"]))
        self.assertIsNone(outcome["results"][0].unit_name)
        self.assertEqual(outcome["results"][2].unit_name, "bytes")
        self.assertEqual(outcome["results"][3].unit_name, "bytes")
        self.assertEqual(saved["results"][0]["maximum_p95_ms"], 5_000.0)
        self.assertIn("not physical phone", saved["metadata"]["evidence_scope"])
        self.assertEqual(len(saved["metadata"]["expected_output_identity"]), 64)


if __name__ == "__main__":
    unittest.main()
