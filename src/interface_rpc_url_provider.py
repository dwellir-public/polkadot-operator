#!/usr/bin/python3

"""RPC url interface (providers side)."""

from service_args import ServiceArgs
from ops.framework import Object
from ops.charm import RelationChangedEvent
import utils

class RpcUrlProvider(Object):
    """RPC url provider interface."""

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name
        self.framework.observe(
            charm.on[relation_name].relation_joined, self._on_relation_joined
        )

    def _on_relation_joined(self, event: RelationChangedEvent) -> None:
        """This event is used to send the ws or http rpc url to another client."""

        service_args_obj = ServiceArgs(self._charm.config.get('service-args'), "")

        ws_port = service_args_obj.ws_port
        rpc_port = service_args_obj.rpc_port
        if not ws_port and not rpc_port:
            event.defer()
            return

        # In newer version of Polkadot the ws options are removed, and ws and http uses the same port specified by --rpc-port instead.
        if "--ws-port" not in utils.get_client_binary_help_output():
            ws_port = rpc_port
        
        ingress_address = event.relation.data.get(self.model.unit)['ingress-address']
        if rpc_port:
            event.relation.data[self.model.unit]['rpc_url'] = f'http://{ingress_address}:{rpc_port}'
        if ws_port:
            event.relation.data[self.model.unit]['ws_url'] = f'ws://{ingress_address}:{ws_port}'
