#!/usr/bin/python3

"""RPC url interface (requirers side)."""

from core.service_args import ServiceArgs
from ops.framework import Object
from core.managers import WorkloadType
from core.managers import WorkloadFactory
import logging

logger = logging.getLogger(__name__)


class RpcUrlRequirer(Object):
    """
    RPC url requirer interface.

    This interface is used by parachain clients that receive relay rpc urls from relay chain nodes.
    """

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self._charm = charm
        self._relation_name = relation_name
        self.framework.observe(
            charm.on[relation_name].relation_changed, self._update_service_args
        )
        self.framework.observe(
            charm.on[relation_name].relation_departed, self._update_service_args
        )

    def _update_service_args(self, event):
        """
        Update service args in response to a change in the relation data.
        """
        service_args_obj = ServiceArgs(self._charm.config, self._charm.rpc_urls())
        if service_args_obj.is_binary:
            workload = WorkloadFactory.get_workload_manager(WorkloadType.BINARY)
        else:
            workload = WorkloadFactory.get_workload_manager(WorkloadType.SNAP)
        
        if workload.service_args_differ_from_disk(service_args_obj.service_args_string):
            workload.set_service_args(service_args_obj.service_args_string)
            if workload.is_service_running():
                workload.restart_service()
        self._charm.update_status()
