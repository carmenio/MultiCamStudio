"""Tests for the isolated complete recording-cut task benchmark."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.performance.phase_00_recording_cut_baseline import (
    RecordingCutConfig,
    RecordingCutSource,
    build_recording_cut_baseline,
)


class RecordingCutBaselineTests(unittest.TestCase):
    """Protect run counts, handler contracts, injection, and cleanup boundaries."""

    def test_runner_uses_injected_cut_execution_and_removes_isolated_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_root = Path(temporary_directory)
            source_dir = storage_root / "SyncedVideos" / "set-178"
            source_dir.mkdir(parents=True)
            sources = []
            for index, name in enumerate(("anna", "chris", "dom"), start=1):
                path = source_dir / f"synced_{name}.mp4"
                payload = (f"source-{name}-".encode("ascii") * 128)
                path.write_bytes(payload)
                sources.append(
                    RecordingCutSource(
                        recording_id=17_800 + index,
                        name=name.title(),
                        relative_path=path.relative_to(storage_root).as_posix(),
                        size_bytes=len(payload),
                        sha256=hashlib.sha256(payload).hexdigest(),
                        frame_count=11_465,
                        measured_fps=60.0,
                        duration_seconds=191.08333333333334,
                        width=1_920,
                        height=1_080,
                    )
                )

            calls = []

            def fake_cut_execution(*, source_path, output_path, start_seconds, end_seconds):
                calls.append((source_path.name, start_seconds, end_seconds))
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_path, output_path)

            def fake_probe(_recording_id, _path):
                return {"duration_seconds": 5.0, "measured_fps": 60.0, "frame_count": 300}

            # The source validator uses the production probe boundary; replace it only
            # for this non-media unit fixture while cut execution remains injected.
            from unittest.mock import patch

            output_path = storage_root / "cut.json"
            source_probe = {
                "frame_count": 11_465,
                "measured_fps": 60.0,
                "duration_seconds": 191.08333333333334,
                "source_frame_width": 1_920,
                "source_frame_height": 1_080,
            }
            output_probe = {
                "frame_count": 300,
                "measured_fps": 60.0,
                "duration_seconds": 5.0,
                "source_frame_width": 1_920,
                "source_frame_height": 1_080,
            }
            with patch(
                "tools.performance.phase_00_recording_cut_baseline._probe_summary",
                side_effect=lambda path: source_probe if "set-178" in path.as_posix() else output_probe,
            ):
                outcome = build_recording_cut_baseline(
                    RecordingCutConfig(
                        output_path=output_path,
                        shared_storage_root=storage_root,
                        sources=tuple(sources),
                    ),
                    cut_execution=fake_cut_execution,
                    timing_probe=fake_probe,
                )

            saved = json.loads(output_path.read_text(encoding="utf-8"))
            runtime_parent = storage_root / ".performance" / "recording-cut"

        result = outcome["results"][0]
        self.assertEqual(result.warmup_runs, 3)
        self.assertEqual(result.measured_runs, 10)
        self.assertFalse(result.failures)
        self.assertEqual(result.unit_name, "camera_seconds")
        self.assertEqual(result.work_units, (15.0,) * 10)
        self.assertEqual(len(calls), 3 * (1 + 3 + 10))
        self.assertFalse(any(runtime_parent.glob("run-*")))
        self.assertEqual(saved["metadata"]["fixture"]["frames_per_run"], 900)
        self.assertEqual(len(saved["metadata"]["expected_contract_identity"]), 64)
        self.assertEqual(len(saved["metadata"]["expected_media_identity"]), 64)
        self.assertEqual(len(saved["metadata"]["output_files"]), 3)

    def test_runner_rejects_drifted_source_before_cut_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_root = Path(temporary_directory)
            source = storage_root / "source.mp4"
            source.write_bytes(b"drifted")
            configured = RecordingCutSource(1, "One", "source.mp4", 999, "0" * 64, 1, 1.0, 1.0, 1, 1)
            calls = []
            with self.assertRaisesRegex(RuntimeError, "source identity changed"):
                build_recording_cut_baseline(
                    RecordingCutConfig(output_path=storage_root / "result.json", shared_storage_root=storage_root, sources=(configured,)),
                    cut_execution=lambda **kwargs: calls.append(kwargs),
                )
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
