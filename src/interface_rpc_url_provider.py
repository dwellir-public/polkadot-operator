#!/usr/bin/python3

"""RPC url interface (providers side)."""

from core.service_args import ServiceArgs
from ops.framework import Object
from ops.charm import RelationJoinedEvent
from core.managers import WorkloadType
from core.factories import WorkloadFactory
import logging

logger = logging.getLogger(__name__)

class RpcUrlProvider(Object):
    """
    RPC URL provider interface.
    This interface is used by relay chain clients broadcast their RPC URLs to parachain clients
    that use them for relay-over-rpc.
    """

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name
        self.framework.observe(
            charm.on[relation_name].relation_joined, self._on_relation_joined
        )

    def _on_relation_joined(self, event: RelationJoinedEvent) -> None:
        """This event is used to broadcast the rpc url to the parachain clients."""

        service_args_obj = ServiceArgs(self._charm.config, "")

        ws_port = service_args_obj.ws_port
        rpc_port = service_args_obj.rpc_port
        if not ws_port and not rpc_port:
            event.defer()
            return

        if service_args_obj.is_binary:
            workload = WorkloadFactory.get_workload_manager(WorkloadType.BINARY)
        else:
            workload = WorkloadFactory.get_workload_manager(WorkloadType.SNAP)
        
        # In newer version of Polkadot the ws options are removed, and ws and http uses the same port specified by --rpc-port instead.
        if "--ws-port" not in workload.get_client_binary_help_output():
            logger.info(f'Using same RPC port ({rpc_port}) for websocket and http due to newer version of Polkadot.')
            ws_port = rpc_port
        
        ingress_address = event.relation.data.get(self.model.unit)['ingress-address']
        if rpc_port:
            event.relation.data[self.model.unit]['rpc_url'] = f'http://{ingress_address}:{rpc_port}'
        if ws_port:
            event.relation.data[self.model.unit]['ws_url'] = f'ws://{ingress_address}:{ws_port}'
