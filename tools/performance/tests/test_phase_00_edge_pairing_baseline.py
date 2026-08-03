"""Tests for isolated EdgeRelay pairing route measurements."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.performance import compare_report_files
from tools.performance.config import DEFAULT_COMPARISON_METADATA_KEYS
from tools.performance.phase_00_edge_pairing_baseline import (
    EdgePairingBenchmarkConfig,
    build_edge_pairing_baseline,
)


class EdgePairingBaselineTests(unittest.TestCase):
    """Protect route coverage, output identity, comparison context, and cleanup."""

    def test_runner_records_complete_issue_and_resolve_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            output_path = temporary_root / "edge-pairing.json"
            runtime_parent = temporary_root / "runtime"
            outcome = build_edge_pairing_baseline(
                EdgePairingBenchmarkConfig(
                    output_path=output_path,
                    temporary_parent=runtime_parent,
                )
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self_gate_passed = compare_report_files(output_path, output_path).passed
            remaining_runtime_entries = list(runtime_parent.iterdir())

        self.assertEqual(
            [result.name for result in outcome["results"]],
            ["edge_pairing_token_issue", "edge_pairing_token_resolve"],
        )
        self.assertTrue(all(result.warmup_runs == 3 for result in outcome["results"]))
        self.assertTrue(all(result.measured_runs == 10 for result in outcome["results"]))
        self.assertTrue(all(not result.failures for result in outcome["results"]))
        self.assertEqual(outcome["results"][0].unit_name, "tokens_issued")
        self.assertEqual(outcome["results"][1].unit_name, "tokens_resolved")
        self.assertEqual(outcome["results"][0].work_units, (1.0,) * 10)
        self.assertTrue(
            set(DEFAULT_COMPARISON_METADATA_KEYS).issubset(saved["metadata"])
        )
        self.assertEqual(
            saved["metadata"]["expected_output_identity"],
            {
                "issue_normalized": "cc9c38241d5b629d41fcc7a0d11c3f90afb35b02ada6930a9b425a3cef212ac2",
                "resolve_response": "523066633931a73ca217dba3236dd0dafe8fb4173dd2e74813cad16ee751c768",
            },
        )
        self.assertIn("not PC network", saved["metadata"]["evidence_scope"])
        self.assertEqual(remaining_runtime_entries, [])
        self.assertTrue(self_gate_passed)


if __name__ == "__main__":
    unittest.main()
