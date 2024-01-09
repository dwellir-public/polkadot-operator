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
            charm.on[relation_name].relation_joined, self._on_relation_changed
        )

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """This event is used to receive the ws or http rpc url from another client."""

        if not event.unit in event.relation.data:
            return

        rpc_url = event.relation.data[event.unit].get("url")
        service_args_obj = ServiceArgs(self.config.get('service-args'))
        utils.update_service_args(service_args_obj.service_args_string)