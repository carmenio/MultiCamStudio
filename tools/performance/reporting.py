"""Versioned JSON persistence for benchmark evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .config import REPORT_SCHEMA_VERSION
from .models import BenchmarkResult


def write_report(
    output_path: Path,
    results: Iterable[BenchmarkResult],
    metadata: Mapping[str, Any],
) -> None:
    """Write an atomic, human-readable report without external dependencies."""

    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "metadata": dict(metadata),
        "results": [result.to_dict() for result in results],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary_path.replace(output_path)


def read_report(input_path: Path) -> tuple[dict[str, Any], tuple[BenchmarkResult, ...]]:
    """Read and validate the version before exposing benchmark results."""

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported benchmark report schema: {payload.get('schema_version')}"
        )
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("benchmark report metadata must be an object")
    results = tuple(BenchmarkResult.from_dict(item) for item in payload["results"])
    return metadata, results
