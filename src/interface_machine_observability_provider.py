"""Provider for the neutral machine-observability relation."""

import json

from ops.framework import Object

from machine_observability import MachineObservabilityPayload, build_machine_observability_payload


class MachineObservabilityProvider(Object):
    """Publish machine-observability payloads to related subordinates."""

    def __init__(self, charm, relation_name: str):
        super().__init__(charm, relation_name)
        self.relation_name = relation_name

    def publish(self, payload: MachineObservabilityPayload | dict) -> None:
        """Publish payload JSON into all related app databags."""

        if self.model.app is None:
            return
        serializable = (
            payload.model_dump(mode="json")
            if isinstance(payload, MachineObservabilityPayload)
            else payload
        )
        for relation in self.model.relations.get(self.relation_name, []):
            relation.data[self.model.app]["payload"] = json.dumps(serializable, sort_keys=True)
