"""Local machine-observability contract definitions.

This module mirrors the future shared contract shape so it can be extracted
later without another schema rewrite.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MACHINE_OBSERVABILITY_SCHEMA_VERSION = 1


class MetricsEndpoint(BaseModel):
    """One metrics scrape endpoint declared by a principal charm."""

    model_config = ConfigDict(extra="forbid")

    targets: list[str]
    path: str = "/metrics"
    scheme: str = "http"
    interval: str = ""
    timeout: str = ""
    tls: dict[str, str | bool] = Field(default_factory=dict)


class LogFileSource(BaseModel):
    """A file log source declared by a principal charm."""

    model_config = ConfigDict(extra="forbid")

    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)


class MachineObservabilityPayload(BaseModel):
    """Neutral source declarations from a principal charm."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[MACHINE_OBSERVABILITY_SCHEMA_VERSION] = (
        MACHINE_OBSERVABILITY_SCHEMA_VERSION
    )
    charm_name: str = ""
    metrics_endpoints: list[MetricsEndpoint] = Field(default_factory=list)
    systemd_units: list[str] = Field(default_factory=list)
    journal_match_expressions: list[str] = Field(default_factory=list)
    log_files: list[LogFileSource] = Field(default_factory=list)


def build_machine_observability_payload(
    *, service_name: str, charm_name: str
) -> MachineObservabilityPayload:
    """Build a typed source-only observability payload for publication."""

    return MachineObservabilityPayload(
        charm_name=charm_name,
        systemd_units=[service_name],
        journal_match_expressions=[],
        metrics_endpoints=[
            MetricsEndpoint(
                targets=["localhost:9615"],
                path="/metrics",
                scheme="http",
            )
        ],
        log_files=[],
    )
