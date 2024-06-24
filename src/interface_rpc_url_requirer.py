#!/usr/bin/python3

"""RPC url interface (requirers side)."""

from service_args import ServiceArgs
from ops.framework import Object
from ops.charm import RelationChangedEvent, RelationDepartedEvent
import utils
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
        utils.update_service_args(service_args_obj.service_args_string)
        self._charm.update_status()
