"""Keep Phase 0 completeness separate from report integrity."""

import json
from pathlib import Path


REGISTRY_PATH = Path("tools/performance/phase_00_required_scenarios.json")
REQUIRED_SCENARIO_IDS = {
    "session_overview_cold_warm",
    "operator_render_navigation",
    "pairing_control_round_trip",
    "stop_to_upload_init",
    "upload_recovery_throughput",
    "recording_preview_seek_sync_cut",
    "calibration_workflow",
    "detection_streaming_postprocessing",
    "triangulation_and_3d",
    "pipeline_worker_orchestration",
    "dataset_export",
    "physical_device_matrix",
}
ALLOWED_STATUSES = {"captured", "partial", "unavailable"}


def test_phase_00_required_scenario_registry_is_complete_and_truthful() -> None:
    """Prevent a passing self-gate from being confused with phase completion."""

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    scenarios = registry["scenarios"]
    by_id = {scenario["id"]: scenario for scenario in scenarios}

    assert len(by_id) == len(scenarios), "required scenario IDs must be unique"
    assert set(by_id) == REQUIRED_SCENARIO_IDS
    for scenario in scenarios:
        assert scenario["status"] in ALLOWED_STATUSES
        assert scenario["evidence"], f"{scenario['id']} must link its available evidence"
        assert all(Path(path).exists() for path in scenario["evidence"])
        if scenario["status"] == "captured":
            assert scenario["blocker"] is None
        else:
            assert scenario["blocker"], f"{scenario['id']} must explain its blocker"

    all_captured = all(scenario["status"] == "captured" for scenario in scenarios)
    assert registry["phase_complete"] is all_captured
