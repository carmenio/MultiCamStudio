"""Tests for the complete Phase 1 recording-synchronization benchmark."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.performance import compare_report_files
from tools.performance.phase_01_recording_sync_baseline import (
    RecordingSyncConfig,
    RecordingSyncSource,
    build_recording_sync_baseline,
)


class RecordingSyncBaselineTests(unittest.TestCase):
    """Protect run counts, source identity, cleanup, and report evidence."""

    def test_runner_captures_reference_and_ten_equivalent_measured_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_root = Path(temporary_directory)
            source_dir = storage_root / "RawVideos"
            source_dir.mkdir()
            sources = []
            for recording_id, name in ((649, "chris"), (650, "dom"), (651, "anna")):
                path = source_dir / f"{name}.mp4"
                payload = (f"source-{name}-".encode("utf-8") * 32)
                path.write_bytes(payload)
                sources.append(
                    RecordingSyncSource(
                        recording_id,
                        name,
                        path.relative_to(storage_root).as_posix(),
                        len(payload),
                        hashlib.sha256(payload).hexdigest(),
                    )
                )
            runtime_relative = Path(".performance/recording-sync/run-current")
            runtime_root = storage_root / runtime_relative
            output_path = storage_root / "baseline.json"
            calls = []
            contract = {"result": {"synced": True}, "preview_tasks": [1, 2, 3]}
            artifacts = {"media": [{"name": "synced.mp4", "size_bytes": 123}], "metadata": {}}
            contract_identity = hashlib.sha256(
                json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            media_identity = hashlib.sha256(
                json.dumps(artifacts, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()

            def execute_workload():
                calls.append(len(calls))
                (runtime_root / "marker.txt").write_text("isolated", encoding="utf-8")
                return {
                    "contract": contract,
                    "artifacts": artifacts,
                    "contract_identity": contract_identity,
                    "media_identity": media_identity,
                    "output_bytes": 123,
                }

            outcome = build_recording_sync_baseline(
                RecordingSyncConfig(
                    output_path=output_path,
                    shared_storage_root=storage_root,
                    runtime_relative_root=runtime_relative,
                    sources=tuple(sources),
                    target_duration_seconds=10.0,
                ),
                workload_executor=execute_workload,
                source_probe=lambda path: {"duration": 10.0, "name": path.name},
            )

            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self_gate = compare_report_files(output_path, output_path)

        result = outcome["results"][0]
        self.assertEqual(len(calls), 14)
        self.assertEqual(result.warmup_runs, 3)
        self.assertEqual(result.measured_runs, 10)
        self.assertEqual(result.work_units, (30.0,) * 10)
        self.assertEqual(result.unit_name, "camera_seconds")
        self.assertFalse(result.failures)
        self.assertFalse(result.warmup_failures)
        self.assertTrue(self_gate.passed)
        self.assertFalse(runtime_root.exists())
        self.assertEqual(saved["metadata"]["expected_output_identity"], {
            "task_contract": contract_identity,
            "media": media_identity,
        })
        self.assertEqual(len(saved["metadata"]["fixture"]["sources"]), 3)
        self.assertEqual(saved["metadata"]["bytes_throughput"]["output_bytes_per_run"], 123)

    def test_runner_rejects_source_drift_before_workload_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_root = Path(temporary_directory)
            source = storage_root / "source.mp4"
            source.write_bytes(b"drifted")
            calls = []
            with self.assertRaisesRegex(RuntimeError, "source identity changed"):
                build_recording_sync_baseline(
                    RecordingSyncConfig(
                        output_path=storage_root / "baseline.json",
                        shared_storage_root=storage_root,
                        sources=(
                            RecordingSyncSource(1, "one", "source.mp4", 999, "0" * 64),
                        ),
                    ),
                    workload_executor=lambda: calls.append(True),
                    source_probe=lambda _path: {},
                )
        self.assertEqual(calls, [])

    def test_runner_rejects_output_identity_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_root = Path(temporary_directory)
            source = storage_root / "source.mp4"
            source.write_bytes(b"source")
            calls = 0

            def execute_workload():
                nonlocal calls
                calls += 1
                identity = hashlib.sha256(f"media-{calls}".encode("utf-8")).hexdigest()
                return {
                    "contract_identity": "a" * 64,
                    "media_identity": identity,
                    "output_bytes": 1,
                }

            with self.assertRaisesRegex(RuntimeError, "did not complete every run"):
                build_recording_sync_baseline(
                    RecordingSyncConfig(
                        output_path=storage_root / "baseline.json",
                        shared_storage_root=storage_root,
                        sources=(
                            RecordingSyncSource(
                                1,
                                "one",
                                "source.mp4",
                                6,
                                hashlib.sha256(b"source").hexdigest(),
                            ),
                        ),
                    ),
                    workload_executor=execute_workload,
                    source_probe=lambda _path: {},
                )


if __name__ == "__main__":
    unittest.main()
