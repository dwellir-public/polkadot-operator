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
            charm.on[relation_name].relation_changed, self._on_relation_changed
        )
        self.framework.observe(
            charm.on[relation_name].relation_departed, self._on_relation_departed
        )

    def _on_relation_changed(self, event: RelationChangedEvent) -> None:
        """This event is used to receive the http rpc url from another client."""

        if not event.unit in event.relation.data:
            return

        # The --relay-chain-rpc-urls option currently only supports ws, hence using ws_url and not rpc_url.
        ws_url = event.relation.data[event.unit]["ws_url"]
        self._charm._stored.relay_rpc_urls.add(ws_url)
        service_args_obj = ServiceArgs(self._charm.config.get('service-args'), self._charm._stored.relay_rpc_urls)
        utils.update_service_args(service_args_obj.service_args_string)
        self._charm.update_status()

    def _on_relation_departed(self, event: RelationChangedEvent) -> None:
        self.framework.breakpoint("departed")
        ws_url = event.relation.data[event.unit]["ws_url"]
        self._charm._stored.relay_rpc_urls.remove(ws_url)
        service_args_obj = ServiceArgs(self._charm.config.get('service-args'), self._charm._stored.relay_rpc_urls)
        utils.update_service_args(service_args_obj.service_args_string)
        self._charm.update_status()
