#!/usr/bin/python3

"""RPC url interface (providers side)."""

from service_args import ServiceArgs
from ops.framework import Object
from ops.charm import RelationChangedEvent

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

        service_args_obj = ServiceArgs(self._charm.config.get('service-args'))
        ingress_address = event.relation.data.get(self.model.unit)['ingress-address']
        if service_args_obj.ws_port:
            url = f'ws://{ingress_address}:{service_args_obj.ws_port}'
        elif service_args_obj.rpc_port:
            url = f'http://{ingress_address}:{service_args_obj.rpc_port}'
        else:
            event.defer()
            return

        event.relation.data[self.model.unit]['url'] = url
