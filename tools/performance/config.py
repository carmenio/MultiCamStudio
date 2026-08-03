"""Shared benchmark defaults.

Keep configuration as importable constants so benchmark scripts can be used like
an SDK and remain straightforward to call from tests and other Python code.
"""

DEFAULT_WARMUP_RUNS = 3
DEFAULT_MEASURED_RUNS = 10
LONG_WORKFLOW_MEASURED_RUNS = 5
DEFAULT_ALLOWED_REGRESSION_PERCENT = 3.0
# `header-bypass` is diagnostic evidence only. It must never satisfy a required
# cold-cache gate, but keeping the label explicit prevents request headers from
# being misrepresented as process, database, browser, or operating-system cold.
SUPPORTED_CACHE_STATES = frozenset({"cold", "warm", "header-bypass"})
REPORT_SCHEMA_VERSION = 1
DEFAULT_COMPARISON_METADATA_KEYS = (
    "platform",
    "python",
    "node",
    "hardware",
    "power_mode",
    "network_route",
    "database_snapshot",
    "fixture",
    "build_mode",
    "dependency_versions",
    "compose_configuration",
    "service_images",
    "cache_preparation",
    "camera_count",
    "recording_duration_seconds",
    "media_sizes_bytes",
    "expected_output_identity",
)
