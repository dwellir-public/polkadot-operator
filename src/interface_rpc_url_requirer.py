#!/usr/bin/python3

"""RPC url interface (requirers side)."""

from service_args import ServiceArgs
from ops.framework import Object
from ops.charm import RelationChangedEvent, RelationDepartedEvent
import utils
import logging

logger = logging.getLogger(__name__)


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
        """This event is used to receive the Websocket RPC url from another client."""

        if not event.unit in event.relation.data:
            event.defer()
            return

        # The --relay-chain-rpc-urls option currently only supports ws, hence using ws_url and not rpc_url.
        try:
            ws_url = event.relation.data[event.unit]["ws_url"]
        except KeyError:
            logger.warning(f'Did not receive websocket URL from {event.unit} to use as a RPC endpoint.')
            event.defer()
            return
        logger.info(f'Received websocket URL {ws_url} from {event.unit} to use as a RPC endpoint.')
        # Storing the unitname+relation_id is a workaround because the relation data is already removed before the departed hook is called.
        # This is to know which url to remove. Issue for the bug: https://github.com/canonical/operator/issues/1109
        dict_key = event.unit.name + ':' + str(event.relation.id)
        self._charm._stored.relay_rpc_urls[dict_key] = ws_url
        service_args_obj = ServiceArgs(self._charm.config.get('service-args'), self._charm._stored.relay_rpc_urls, self._charm.config.get('parachain-spec-url'))
        utils.update_service_args(service_args_obj.service_args_string)
        self._charm.update_status()

    def _on_relation_departed(self, event: RelationDepartedEvent) -> None:
        dict_key = event.unit.name + ':' + str(event.relation.id)
        self._charm._stored.relay_rpc_urls.pop(dict_key)
        service_args_obj = ServiceArgs(self._charm.config.get('service-args'), self._charm._stored.relay_rpc_urls, self._charm.config.get('parachain-spec-url'))
        utils.update_service_args(service_args_obj.service_args_string)
        self._charm.update_status()
