"""Provider for the neutral machine-observability relation."""

import json

from ops.framework import Object


def build_machine_observability_payload(*, service_name: str, charm_name: str) -> dict:
    """Build the source-only observability payload consumed by alloy-sub."""

    return {
        "schema_version": 1,
        "charm_name": charm_name,
        "systemd_units": [service_name],
        "journal_match_expressions": [],
        "metrics_endpoints": [
            {
                "targets": ["localhost:9615"],
                "path": "/metrics",
                "scheme": "http",
                "interval": "",
                "timeout": "",
                "tls": {},
            }
        ],
        "log_files": [],
    }


class MachineObservabilityProvider(Object):
    """Publish machine-observability payloads to related subordinates."""

    def __init__(self, charm, relation_name: str):
        super().__init__(charm, relation_name)
        self.relation_name = relation_name

    def publish(self, payload: dict) -> None:
        """Publish payload JSON into all related app databags."""

        if self.model.app is None:
            return
        for relation in self.model.relations.get(self.relation_name, []):
            relation.data[self.model.app]["payload"] = json.dumps(payload, sort_keys=True)
