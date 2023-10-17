#!/usr/bin/env python3
# Copyright 2021 dwellir
# See LICENSE file for licensing details.

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging
from pathlib import Path
from requests.exceptions import ConnectionError as RequestsConnectionError
from urllib3.exceptions import NewConnectionError, MaxRetryError
import time
import re

from ops import main, framework, ConfigChangedEvent, InstallEvent, StartEvent, StopEvent, UpdateStatusEvent
from ops.charm import CharmBase, ActionEvent
from ops.model import ActiveStatus, MaintenanceStatus, WaitingStatus, BlockedStatus

from interface_prometheus import PrometheusProvider
from interface_rpc_url_provider import RpcUrlProvider
from polkadot_rpc_wrapper import PolkadotRpcWrapper
import utils
from service_args import ServiceArgs

from charms.grafana_agent.v0.cos_agent import COSAgentProvider

logger = logging.getLogger(__name__)


class PolkadotCharm(CharmBase):
    """Charm the service."""

    _stored = framework.StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.prometheus_node_provider = PrometheusProvider(self, 'node-prometheus', 9100, '/metrics')
        self.prometheus_polkadot_provider = PrometheusProvider(self, 'polkadot-prometheus', 9615, '/metrics')
        self.rpc_url_provider = RpcUrlProvider(self, 'rpc_url'),

        self.cos_agent_provider = COSAgentProvider(
            self,
            relation_name="grafana-agent",
            metrics_endpoints=[{"port": 9615, "path": "/metrics"}],
            refresh_events=[self.on.update_status, self.on.upgrade_charm],
            metrics_rules_dir="./src/alert_rules/prometheus",
            logs_rules_dir="./src/alert_rules/loki"
        )
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.stop, self._on_stop)
        # Actions
        self.framework.observe(self.on.get_session_key_action, self._on_get_session_key_action)
        self.framework.observe(self.on.has_session_key_action, self._on_has_session_key_action)
        self.framework.observe(self.on.insert_key_action, self._on_insert_key_action)
        self.framework.observe(self.on.restart_node_service_action, self._on_restart_node_service_action)
        self.framework.observe(self.on.set_node_key_action, self._on_set_node_key_action)
        self.framework.observe(self.on.get_node_info_action, self._on_get_node_info_action)

        self._stored.set_default(binary_url=self.config.get('binary-url'),
                                 docker_tag=self.config.get('docker-tag'),
                                 service_args=self.config.get('service-args'))

    def _on_install(self, event: InstallEvent) -> None:
        self.unit.status = MaintenanceStatus("Begin installing charm")
        service_args_obj = ServiceArgs(self.config.get('service-args'))
        # Setup polkadot group and user, disable login
        utils.setup_group_and_user()
        # Create environment file for polkadot service arguments
        utils.create_env_file_for_service()
        # Download and prepare the binary
        self.unit.status = MaintenanceStatus("Installing binary")
        utils.install_binary(self.config, service_args_obj.chain_name)
        # Install polkadot.service file
        self.unit.status = MaintenanceStatus("Installing service")
        source_path = Path(self.charm_dir / 'templates/etc/systemd/system/polkadot.service')
        utils.install_service_file(source_path)
        utils.update_service_args(service_args_obj.service_args_string)
        self.unit.status = MaintenanceStatus("Installing node exporter")
        utils.install_node_exporter()
        self.unit.status = MaintenanceStatus("Charm install complete")

    def _on_config_changed(self, event: ConfigChangedEvent) -> None:
        try:
            service_args_obj = ServiceArgs(self.config.get('service-args'))
        except ValueError as e:
            self.unit.status = BlockedStatus(str(e))
            event.defer()
            return

        # Update of polkadot binary requested
        if self._stored.binary_url != self.config.get('binary-url') or self._stored.docker_tag != self.config.get('docker-tag'):
            self.unit.status = MaintenanceStatus("Installing binary")
            try:
                utils.install_binary(self.config, service_args_obj.chain_name)
            except ValueError as e:
                self.unit.status = BlockedStatus(str(e))
                event.defer()
                return
            self._stored.binary_url = self.config.get('binary-url')
            self._stored.docker_tag = self.config.get('docker-tag')

        # Update of polkadot service arguments requested
        if self._stored.service_args != self.config.get('service-args'):
            self.unit.status = MaintenanceStatus("Updating service args")
            utils.update_service_args(service_args_obj.service_args_string)
            self._stored.service_args = self.config.get('service-args')

        self.update_status(connection_attempts=2)

    def _on_update_status(self, event: UpdateStatusEvent) -> None:
        self.update_status()

    def update_status(self, connection_attempts: int = 4) -> None:
        if utils.service_started():
            rpc_port = ServiceArgs(self._stored.service_args).rpc_port
            for i in range(connection_attempts):
                time.sleep(5)
                try:
                    self.unit.status = ActiveStatus("Syncing: {}, Validating: {}".format(
                        str(PolkadotRpcWrapper(rpc_port).is_syncing()),
                        str(PolkadotRpcWrapper(rpc_port).is_validating())))
                    self.unit.set_workload_version(PolkadotRpcWrapper(rpc_port).get_version())
                    break
                except RequestsConnectionError as e:
                    logger.warning(e)
                    self.unit.status = MaintenanceStatus("Client not responding to HTTP (attempt {}/{})".format(i, connection_attempts))
            if type(self.unit.status) != ActiveStatus:
                self.unit.status = BlockedStatus("Service running, client starting up")
        else:
            self.unit.status = WaitingStatus("Service not running")

    def _on_start(self, event: StartEvent) -> None:
        utils.start_polkadot()
        self.update_status()

    def _on_stop(self, event: StopEvent) -> None:
        utils.stop_polkadot()
        self.unit.status = ActiveStatus("Service stopped")

    def _on_get_session_key_action(self, event: ActionEvent) -> None:
        event.log("Getting new session key through rpc...")
        rpc_port = ServiceArgs(self._stored.service_args).rpc_port
        key = PolkadotRpcWrapper(rpc_port).get_session_key()
        if key:
            event.set_results(results={'session-key': key})
        else:
            event.fail("Unable to get new session key")

    def _on_has_session_key_action(self, event: ActionEvent) -> None:
        key = event.params['key']
        keypattern = re.compile(r'^0x')
        if not re.match(keypattern, key):
            event.fail("Illegal key pattern, did your key start with 0x ?")
        else:
            rpc_port = ServiceArgs(self._stored.service_args).rpc_port
            has_session_key = PolkadotRpcWrapper(rpc_port).has_session_key(key)
            event.set_results(results={'has-key': has_session_key})

    def _on_insert_key_action(self, event: ActionEvent) -> None:
        mnemonic = event.params['mnemonic']
        address = event.params['address']
        keypattern = re.compile(r'^0x')
        if not re.match(keypattern, address):
            event.fail("Illegal key pattern, did your public key/address start with 0x ?")
        else:
            rpc_port = ServiceArgs(self._stored.service_args).rpc_port
            PolkadotRpcWrapper(rpc_port).insert_key(mnemonic, address)

    def _on_restart_node_service_action(self, event: ActionEvent) -> None:
        utils.stop_polkadot()
        utils.start_polkadot()
        if not utils.service_started():
            event.fail("Could not start service")

    def _on_set_node_key_action(self, event: ActionEvent) -> None:
        key = event.params['key']
        utils.stop_polkadot()
        utils.write_node_key_file(key)
        utils.start_polkadot()

    # TODO: this action is getting quite large and specialized, perhaps move all actions to an `actions.py` file?
    def _on_get_node_info_action(self, event: ActionEvent) -> None:
        # Disk usage
        relay_du = utils.get_relay_disk_usage()
        chain_du = utils.get_chain_disk_usage()
        if not relay_du:
            # If only the chain DB exists, we're on a relay chain
            event.set_results(results={'disk-usage': chain_du})
        else:
            # If a relay DB also exists, we're on a parachain
            event.set_results(results={'disk-usage-relay': relay_du})
            event.set_results(results={'disk-usage-para': chain_du})
        # Client
        event.set_results(results={'client-service-args': utils.get_service_args()})
        event.set_results(results={'client-binary-version': utils.get_binary_version()})
        event.set_results(results={'client-binary-md5sum': utils.get_binary_md5sum()})
        event.set_results(results={'client-binary-last-changed': utils.get_binary_last_changed()})
        event.set_results(results={'client-wasm-files': utils.get_wasm_info()})
        proc_cmdline = utils.get_polkadot_proc_cmdline()
        if proc_cmdline:
            event.set_results(results={'client-proc-cmdline': proc_cmdline})
        else:
            event.set_results(results={'client-proc-cmdline': 'Process not found'})
        # Node type
        if utils.is_relay_chain_node():
            event.set_results(results={'node-type': 'Relaychain node'})
        elif utils.is_parachain_node():
            event.set_results(results={'node-type': 'Parachain node'})
            event.set_results(results={'node-relay': utils.get_relay_for_parachain()})
        # On-chain info
        try:
            rpc_port = ServiceArgs(self._stored.service_args).rpc_port
            block_height = PolkadotRpcWrapper(rpc_port).get_block_height()
            if block_height:
                event.set_results(results={'chain-block-height': block_height})
            peer_list, success = PolkadotRpcWrapper(rpc_port).get_system_peers()
            if peer_list and success:
                event.set_results(results={'chain-peer-count': len(peer_list)})
            elif peer_list and 'RPC call is unsafe' in peer_list[0]:
                event.set_results(results={'chain-peer-count': 'RPC method error, check if the node has `--rpc-methods unsafe` enabled'})
            else:
                event.set_results(results={'chain-peer-count': 'Error trying to get peer count'})
        except (RequestsConnectionError, NewConnectionError, MaxRetryError) as e:
            logger.warning(e)
            event.set_results(results={'on-chain-info': 'Unable to establish HTTP connection to client'})


if __name__ == "__main__":
    main.main(PolkadotCharm)
