"""Provider for the neutral machine-observability relation."""

import json

from ops.framework import Object


def build_machine_observability_payload(*, service_name: str, chain_name: str) -> dict:
    """Build the principal observability payload consumed by alloy-sub."""

    return {
        "charm_name": "polkadot",
        "systemd_units": [service_name],
        "journal_match_expressions": [],
        "metrics_jobs": [
            {
                "job_name": "polkadot",
                "metrics_path": "/metrics",
                "static_configs": [{"targets": ["localhost:9615"]}],
            }
        ],
        "log_files_include": [],
        "log_files_exclude": [],
        "log_attributes": {},
        "workload_labels": {
            "chain_name": chain_name,
            "chain_family": "substrate",
            "client_name": "polkadot",
        },
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
