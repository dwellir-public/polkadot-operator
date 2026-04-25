# Copyright 2026 Erik Lönroth
# See LICENSE file for licensing details.

"""Machine-observability relation library.

This library provides a neutral relation contract for machine-subordinate
telemetry collection. Principal charms publish metrics, journald, and file-log
source declarations; subordinate consumers validate and apply those
declarations.

The canonical source of this library lives in `alloy-sub-operator` and can be
vendor-copied into other charms to keep the contract in sync.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Literal, Optional

from ops.charm import CharmBase, HookEvent, RelationBrokenEvent, RelationChangedEvent
from ops.framework import EventBase, EventSource, Object, ObjectEvents
from ops.model import Relation
from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)

# The unique Charmhub library identifier, never change it
LIBID = "0b7d5c45f19b4b4b9876db265b31af48"

# Increment this major API version when introducing breaking changes
LIBAPI = 0

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 2

DEFAULT_RELATION_NAME = "machine-observability"
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


class MachineObservabilityProviderAppData(BaseModel):
    """Application databag model for the provider side of the relation."""

    payload: str

    def dump(self, databag: dict[str, str]) -> None:
        """Write the model into a relation databag."""

        databag["payload"] = self.payload

    @classmethod
    def load(cls, databag: dict[str, str]) -> "MachineObservabilityProviderAppData":
        """Load the provider model from a relation databag."""

        return cls(payload=databag.get("payload", "{}"))


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


def load_machine_observability_payload(relation: Any) -> MachineObservabilityPayload:
    """Load and validate the remote application payload for machine-observability."""

    raw_payload = "{}"

    if hasattr(relation, "remote_app_data"):
        raw_payload = relation.remote_app_data.get("payload", "{}")
    else:
        app = getattr(relation, "app", None)
        if app is None:
            return MachineObservabilityPayload()
        raw_payload = relation.data[app].get("payload", "{}")

    return MachineObservabilityPayload.model_validate(json.loads(raw_payload))


class MachineObservabilityProvider(Object):
    """Publish machine-observability payloads to related subordinates."""

    def __init__(
        self,
        charm: CharmBase,
        relation_name: str = DEFAULT_RELATION_NAME,
        *,
        payload_factory: Optional[Callable[[], MachineObservabilityPayload | dict[str, Any]]] = None,
        refresh_events: Optional[list[HookEvent]] = None,
    ):
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name
        self._payload_factory = payload_factory
        self._refresh_events = refresh_events or []

        events = self._charm.on[relation_name]
        self.framework.observe(events.relation_joined, self._on_refresh)
        self.framework.observe(events.relation_changed, self._on_refresh)
        for event in self._refresh_events:
            self.framework.observe(event, self._on_refresh)

    def _on_refresh(self, _: HookEvent) -> None:
        """Refresh relation data from the payload factory when configured."""

        if self._payload_factory is None:
            return
        self.publish(self._payload_factory())

    def publish(self, payload: MachineObservabilityPayload | dict[str, Any]) -> None:
        """Publish payload JSON into all related app databags."""

        if self.model.app is None:
            return

        serializable = (
            payload.model_dump(mode="json")
            if isinstance(payload, MachineObservabilityPayload)
            else payload
        )
        provider_data = MachineObservabilityProviderAppData(
            payload=json.dumps(serializable, sort_keys=True)
        )
        for relation in self.model.relations.get(self._relation_name, []):
            provider_data.dump(relation.data[self.model.app])


class MachineObservabilityDataChanged(EventBase):
    """Event emitted when machine-observability data changes."""


class MachineObservabilityValidationError(EventBase):
    """Event emitted when machine-observability data fails validation."""

    def __init__(self, handle, message: str = ""):
        super().__init__(handle)
        self.message = message

    def snapshot(self) -> dict[str, str]:
        """Save validation error state."""

        return {"message": self.message}

    def restore(self, snapshot: dict[str, str]) -> None:
        """Restore validation error state."""

        self.message = snapshot["message"]


class MachineObservabilityConsumerEvents(ObjectEvents):
    """Events emitted by MachineObservabilityConsumer."""

    data_changed = EventSource(MachineObservabilityDataChanged)
    validation_error = EventSource(MachineObservabilityValidationError)


class MachineObservabilityConsumer(Object):
    """Validate and read machine-observability payloads from principal charms."""

    on = MachineObservabilityConsumerEvents()  # pyright: ignore

    def __init__(self, charm: CharmBase, relation_name: str = DEFAULT_RELATION_NAME):
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name

        events = self._charm.on[relation_name]
        self.framework.observe(events.relation_changed, self._on_relation_changed)
        self.framework.observe(events.relation_broken, self._on_relation_broken)

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        relation = event.relation
        if not self._validated_payload(relation):
            return
        self.on.data_changed.emit()  # pyright: ignore

    def _on_relation_broken(self, _: RelationBrokenEvent) -> None:
        self.on.data_changed.emit()  # pyright: ignore

    def get_payload(
        self, relation: Optional[Relation] = None
    ) -> MachineObservabilityPayload:
        """Return the validated payload for a relation or the default empty payload."""

        relation = relation or self._relation
        if relation is None:
            return MachineObservabilityPayload()

        payload = self._validated_payload(relation)
        return payload if payload is not None else MachineObservabilityPayload()

    @property
    def relations(self) -> list[Relation]:
        """All relations using the configured relation name."""

        return list(self._charm.model.relations[self._relation_name])

    @property
    def _relation(self) -> Optional[Relation]:
        """The single relation for this endpoint when present."""

        relations = self.relations
        return relations[0] if relations else None

    def _validated_payload(
        self, relation: Relation
    ) -> Optional[MachineObservabilityPayload]:
        try:
            return load_machine_observability_payload(relation)
        except (ValidationError, json.JSONDecodeError) as exc:
            logger.warning("Invalid machine-observability payload on relation %s: %s", relation.id, exc)
            self.on.validation_error.emit(message=str(exc))  # pyright: ignore
            return None
