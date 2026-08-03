"""Tests for deterministic All-page pipeline-dispatch measurements."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.performance.phase_00_pipeline_dispatch_baseline import (
    PipelineDispatchConfig,
    build_pipeline_dispatch_baseline,
)


class PipelineDispatchBaselineTests(unittest.TestCase):
    """Protect route coverage, task throughput, and evidence scope."""

    def test_runner_records_exact_five_stage_task_chains(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "pipeline.json"
            outcome = build_pipeline_dispatch_baseline(
                PipelineDispatchConfig(
                    output_path=output_path,
                    warmup_runs=3,
                    measured_runs=10,
                    recording_set_count=2,
                )
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        result = outcome["result"]
        self.assertEqual(result.measured_runs, 10)
        self.assertFalse(result.failures)
        self.assertEqual(result.work_units, (10.0,) * 10)
        self.assertEqual(result.unit_name, "tasks_dispatched")
        self.assertEqual(saved["metadata"]["fixture"]["stages_per_set"], 5)
        self.assertEqual(saved["metadata"]["fixture"]["expected_tasks_per_run"], 10)
        self.assertEqual(len(saved["metadata"]["expected_output_identity"]), 64)
        self.assertIn("not worker execution", saved["metadata"]["evidence_scope"])

    def test_runner_rejects_empty_recording_set_fixture(self) -> None:
        with self.assertRaisesRegex(ValueError, "recording_set_count must be positive"):
            build_pipeline_dispatch_baseline(
                PipelineDispatchConfig(recording_set_count=0)
            )


if __name__ == "__main__":
    unittest.main()
