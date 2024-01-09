#!/usr/bin/python3

"""RPC url interface (providers side)."""

from service_args import ServiceArgs
from ops.framework import Object
from ops.charm import RelationChangedEvent
import utils

class RpcUrlRequirer(Object):
    """RPC url requirer interface."""

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name
        self.framework.observe(
            charm.on[relation_name].relation_changed, self._on_relation_changed,
            charm.on[relation_name].relation_departed, self._on_relation_departed
        )

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """This event is used to receive the ws or http rpc url from another client."""

        if not event.unit in event.relation.data:
            return

        rpc_url = event.relation.data[event.unit].get("url")
        self._charm._stored.relay_rpc_url = rpc_url
        service_args_obj = ServiceArgs(self._charm.config.get('service-args'), self._charm._stored.relay_rpc_url)
        utils.update_service_args(service_args_obj.service_args_string)

    def _on_relation_departed(self, event: RelationChangedEvent) -> None:
        self._charm._stored.relay_rpc_url = ""
        service_args_obj = ServiceArgs(self._charm.config.get('service-args'), self._charm._stored.relay_rpc_url)
        utils.update_service_args(service_args_obj.service_args_string)
