"""Tests for deterministic PC pairing route measurements."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.performance import compare_report_files
from tools.performance.phase_00_pairing_baseline import (
    PairingBenchmarkConfig,
    build_pairing_baseline,
)


class PairingBaselineTests(unittest.TestCase):
    """Protect route coverage, stable identities, and evidence scope."""

    def test_runner_records_issue_and_resolve_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "pairing.json"
            outcome = build_pairing_baseline(PairingBenchmarkConfig(output_path=output_path))
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self_gate_passed = compare_report_files(output_path, output_path).passed

        self.assertEqual([result.name for result in outcome["results"]], [
            "pc_pairing_token_issue",
            "pc_pairing_token_resolve",
        ])
        self.assertTrue(all(result.measured_runs == 10 for result in outcome["results"]))
        self.assertTrue(all(not result.failures for result in outcome["results"]))
        self.assertEqual(saved["metadata"]["expiration_shape"], "integer Unix epoch")
        self.assertEqual(len(saved["metadata"]["expected_output_identity"]["issue_claims"]), 64)
        self.assertIn("not EdgeRelay", saved["metadata"]["evidence_scope"])
        self.assertTrue(self_gate_passed)


if __name__ == "__main__":
    unittest.main()
