"""Shared benchmark defaults.

Keep configuration as importable constants so benchmark scripts can be used like
an SDK and remain straightforward to call from tests and other Python code.
"""

DEFAULT_WARMUP_RUNS = 3
DEFAULT_MEASURED_RUNS = 10
LONG_WORKFLOW_MEASURED_RUNS = 5
DEFAULT_ALLOWED_REGRESSION_PERCENT = 3.0
SUPPORTED_CACHE_STATES = frozenset({"cold", "warm"})
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
