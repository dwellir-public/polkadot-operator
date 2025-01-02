#!/usr/bin/env python3
# Copyright 2024 Dwellir AB
# See LICENSE file for licensing details.

"""Charm the Polkadot blockchain client service."""

import logging
from pathlib import Path
from requests.exceptions import ConnectionError as RequestsConnectionError
from urllib3.exceptions import NewConnectionError, MaxRetryError
import time
import re

import ops

from interface_prometheus import PrometheusProvider
from interface_rpc_url_provider import RpcUrlProvider
from interface_rpc_url_requirer import RpcUrlRequirer
from polkadot_rpc_wrapper import PolkadotRpcWrapper
import utils
from service_args import ServiceArgs

from charms.grafana_agent.v0.cos_agent import COSAgentProvider

logger = logging.getLogger(__name__)


class PolkadotCharm(ops.CharmBase):
    """Charm the Polkadot blockchain client service."""

    _stored = ops.framework.StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.prometheus_node_provider = PrometheusProvider(self, 'node-prometheus', 9100, '/metrics')
        self.prometheus_polkadot_provider = PrometheusProvider(self, 'polkadot-prometheus', 9615, '/metrics')
        self.rpc_url_provider = RpcUrlProvider(self, 'rpc_url'),
        self.rpc_url_requirer = RpcUrlRequirer(self, 'relay_rpc_url'),

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
        self.framework.observe(self.on.start_node_service_action, self._on_start_node_service_action)
        self.framework.observe(self.on.stop_node_service_action, self._on_stop_node_service_action)
        self.framework.observe(self.on.set_node_key_action, self._on_set_node_key_action)
        self.framework.observe(self.on.find_validator_address_action, self._on_find_validator_address_action)
        self.framework.observe(self.on.is_validating_next_era_action, self._on_is_validating_next_era_action)
        self.framework.observe(self.on.get_node_info_action, self._on_get_node_info_action)
        self.framework.observe(self.on.get_node_help_action, self._on_get_node_help_action)
        self.framework.observe(self.on.print_readme_action, self._on_print_readme_action)
        self.framework.observe(self.on.start_validating_action, self._on_start_validating_action)

        self._stored.set_default(binary_url=self.config.get('binary-url'),
                                 docker_tag=self.config.get('docker-tag'),
                                 service_args=self.config.get('service-args'),
                                 chain_spec_url=self.config.get('chain-spec-url'),
                                 local_relaychain_spec_url=self.config.get('local-relaychain-spec-url'),
                                 wasm_runtime_url=self.config.get('wasm-runtime-url'),
                                 )

    def rpc_urls(self):
        """
        Return the RPC URL:s that are currently available in all relay-rpc-url relations.
        The magic comprehension below is the unfortunate actual best method to perform this
        list flattening operation in Python.
        """
        return [subdata["ws_url"] for relation in self.model.relations["relay-rpc-url"] for subdata in relation.data.values() if "ws_url" in subdata]

    def _on_install(self, event: ops.InstallEvent) -> None:
        self.unit.status = ops.MaintenanceStatus("Begin installing charm")
        service_args_obj = ServiceArgs(self.config, self.rpc_urls())
        # Setup polkadot group and user, disable login
        utils.setup_group_and_user()
        # Create environment file for polkadot service arguments
        utils.create_env_file_for_service()
        # Download and prepare the binary
        self.unit.status = ops.MaintenanceStatus("Installing binary")
        utils.install_binary(self.config, service_args_obj.chain_name)
        utils.download_wasm_runtime(self.config.get('wasm-runtime-url'))
        utils.generate_node_key()
        # Install polkadot.service file
        self.unit.status = ops.MaintenanceStatus("Installing service")
        source_path = Path(self.charm_dir / 'templates/etc/systemd/system/polkadot.service')
        utils.install_service_file(source_path)
        utils.update_service_args(service_args_obj.service_args_string)
        self.unit.status = ops.MaintenanceStatus("Installing node exporter")
        utils.install_node_exporter()
        self.unit.status = ops.MaintenanceStatus("Charm install complete")

    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        try:
            service_args_obj = ServiceArgs(self.config, self.rpc_urls())
        except ValueError as e:
            self.unit.status = ops.BlockedStatus(str(e))
            event.defer()
            return

        # Update of polkadot binary requested
        if self._stored.binary_url != self.config.get('binary-url') or self._stored.docker_tag != self.config.get('docker-tag'):
            self.unit.status = ops.MaintenanceStatus("Installing binary")
            try:
                utils.install_binary(self.config, service_args_obj.chain_name)
            except ValueError as e:
                self.unit.status = ops.BlockedStatus(str(e))
                event.defer()
                return
            self._stored.binary_url = self.config.get('binary-url')
            self._stored.docker_tag = self.config.get('docker-tag')

        # Update of polkadot service arguments requested
        if self._stored.service_args != self.config.get('service-args'):
            self.unit.status = ops.MaintenanceStatus("Updating service args")
            utils.update_service_args(service_args_obj.service_args_string)
            self._stored.service_args = self.config.get('service-args')

        if self._stored.chain_spec_url != self.config.get('chain-spec-url'):
            try:
                self.unit.status = ops.MaintenanceStatus("Updating chain spec")
                utils.update_service_args(service_args_obj.service_args_string)
                self._stored.chain_spec_url = self.config.get('chain-spec-url')
            except ValueError as e:
                self.unit.status = ops.BlockedStatus(str(e))
                event.defer()
                return

        if self._stored.local_relaychain_spec_url != self.config.get('local-relaychain-spec-url'):
            try:
                self.unit.status = ops.MaintenanceStatus("Updating relaychain spec")
                utils.update_service_args(service_args_obj.service_args_string)
                self._stored.local_relaychain_spec_url = self.config.get('local-relaychain-spec-url')
            except ValueError as e:
                self.unit.status = ops.BlockedStatus(str(e))
                event.defer()
                return
        if self._stored.wasm_runtime_url != self.config.get('wasm-runtime-url'):
            self.unit.status = ops.MaintenanceStatus("Updating wasm runtime")
            utils.download_wasm_runtime(self.config.get('wasm-runtime-url'))
            utils.update_service_args(service_args_obj.service_args_string)
            self._stored.wasm_runtime_url = self.config.get('wasm-runtime-url')

        self.update_status_simple()

    def _on_update_status(self, event: ops.UpdateStatusEvent) -> None:
        self.update_status(validator_check=True)

    def update_status(self, connection_attempts: int = 4, validator_check: bool = False) -> None:
        """ 
        Update the status of the unit based on the state of the service.
        param connection_attempts: Number of attempts to connect to the client
        param validator_check: If the node is a validator, check if it's validating. 
        The validating check can take a long time so this boolean can be used to skip it in some cases.
        During a benchmark, it took 20 seconds on Kusama where there are 1000 validators.
        """
        if utils.service_started():
            service_args = ServiceArgs(self.config, self.rpc_urls())
            rpc_port = service_args.rpc_port
            for i in range(connection_attempts):
                time.sleep(5)
                try:
                    is_syncing = str(PolkadotRpcWrapper(rpc_port).is_syncing())
                    status_message = f'Syncing: {is_syncing}'
                    if validator_check and service_args.is_validator:
                        if PolkadotRpcWrapper(rpc_port).is_validating_this_era():
                            status_message += ", Validating: Yes"
                        else:
                            status_message += ", Validating: No"
                    self.unit.status = ops.ActiveStatus(status_message)
                    self.unit.set_workload_version(utils.get_binary_version())
                    break
                except RequestsConnectionError as e:
                    logger.warning(e)
                    self.unit.status = ops.MaintenanceStatus(
                        "Client not responding to HTTP (attempt {}/{})".format(i + 1, connection_attempts))
            if type(self.unit.status) != ops.ActiveStatus:
                self.unit.status = ops.WaitingStatus("Service running but not responding to HTTP")
        else:
            self.unit.status = ops.BlockedStatus("Service not running")

    def update_status_simple(self, iterations=4) -> None:
        """
        Update the status of the unit based on the state of the service.
        This is a simplified version of the update_status method, meant to give a quicker response.
        """
        if utils.service_started(iterations=iterations):
            self.unit.status = ops.ActiveStatus("Service running")
        else:
            self.unit.status = ops.BlockedStatus("Service not running")
        self.unit.set_workload_version(utils.get_binary_version())

    def _on_start(self, event: ops.StartEvent) -> None:
        utils.start_service()
        self.update_status_simple()

    def _on_stop(self, event: ops.StopEvent) -> None:
        utils.stop_service()
        self.update_status_simple()

    def _on_get_session_key_action(self, event: ops.ActionEvent) -> None:
        event.log("Getting new session key through RPC...")
        rpc_port = ServiceArgs(self.config, self.rpc_urls()).rpc_port
        key = PolkadotRpcWrapper(rpc_port).get_session_key()
        if key:
            event.set_results(results={'session-keys-merged': key})

            # For convenience, also print a split version of the session key
            keys_split = utils.split_session_key(key)
            for i, key in enumerate(keys_split):
                event.set_results(results={f'session-key-{i}': key})
        else:
            event.fail("Unable to get new session key")

    def _on_has_session_key_action(self, event: ops.ActionEvent) -> None:
        key = event.params['key']
        keypattern = re.compile(r'^0x')
        if not re.match(keypattern, key):
            event.fail("Illegal key pattern, did your key start with 0x ?")
        else:
            rpc_port = ServiceArgs(self.config, self.rpc_urls()).rpc_port
            has_session_key = PolkadotRpcWrapper(rpc_port).has_session_key(key)
            event.set_results(results={'has-key': has_session_key})

    def _on_insert_key_action(self, event: ops.ActionEvent) -> None:
        mnemonic = event.params['mnemonic']
        address = event.params['address']
        keypattern = re.compile(r'^0x')
        if not re.match(keypattern, address):
            event.fail("Illegal key pattern, did your public key/address start with 0x ?")
        else:
            rpc_port = ServiceArgs(self.config, self.rpc_urls()).rpc_port
            PolkadotRpcWrapper(rpc_port).insert_key(mnemonic, address)

    def _on_restart_node_service_action(self, event: ops.ActionEvent) -> None:
        utils.restart_service()
        if not utils.service_started(iterations=4):
            event.fail("Could not restart service")
        event.set_results(results={'message': 'Node service restarted'})
        self.update_status_simple()

    def _on_start_node_service_action(self, event: ops.ActionEvent) -> None:
        utils.start_service()
        if not utils.service_started(iterations=4):
            event.fail("Could not start service")
        event.set_results(results={'message': 'Node service started'})
        self.update_status_simple()

    def _on_stop_node_service_action(self, event: ops.ActionEvent) -> None:
        utils.stop_service()
        if utils.service_started(iterations=2):
            event.fail("Could not stop service")
        event.set_results(results={'message': 'Node service stopped'})
        self.update_status_simple(iterations=2)

    def _on_set_node_key_action(self, event: ops.ActionEvent) -> None:
        key = event.params['key']
        utils.stop_service()
        utils.write_node_key_file(key)
        utils.start_service()
        self.update_status_simple()

    def _on_find_validator_address_action(self, event: ops.ActionEvent) -> None:
        event.log("Checking sessions key through RPC...")
        rpc_port = ServiceArgs(self.config, self.rpc_urls()).rpc_port
        result = PolkadotRpcWrapper(rpc_port).is_validating_this_era()
        if result:
            event.set_results(results={'message': f'This node is currently validating for address {result["validator"]}'})
            event.set_results(results={'session-key': result["session_key"]})
        else:
            event.set_results(results={'message': 'This node is not currently validating for any address.'})

    def _on_is_validating_next_era_action(self, event: ops.ActionEvent) -> None:
        validator_address = event.params['address']
        event.log("Checking sessions key through RPC...")
        rpc_port = ServiceArgs(self.config, self.rpc_urls()).rpc_port
        session_key = PolkadotRpcWrapper(rpc_port).is_validating_next_era(validator_address)
        if session_key:
            event.set_results(results={'message': f'This node will be validating next era for address {validator_address}'})
            event.set_results(results={'session-key': session_key})
        else:
            event.set_results(results={'message': f'This node will not be validating next era for address {validator_address}'})

    def _on_start_validating_action(self, event: ops.ActionEvent) -> None:
        mnemonic_secret_id = self.config.get('mnemonic-secret-id')
        if not mnemonic_secret_id:
            event.fail("No secret id provided. Please provide a secret id using the mnemonic-secret-id config option.")
            return
        rpc_port = ServiceArgs(self.config, self.rpc_urls()).rpc_port
        secret = self.model.get_secret(id=mnemonic_secret_id)
        if not secret:
            event.fail(f"No secret found with the provided id {mnemonic_secret_id}")
            return
        try:
            mnemonic = secret.get_content(refresh=True).get('mnemonic')
        except KeyError:
            event.fail(f"Secret with id {mnemonic_secret_id} does not contain a 'mnemonic' key")
            return
        try:
            result = PolkadotRpcWrapper(rpc_port).set_session_key_on_chain(mnemonic)
        except ValueError as e:
            event.fail(str(e))
            return

        event.set_results(results={'message': 'Session key successfully set on chain.'})
        event.set_results(results={'result': result})

    # TODO: this action is getting quite large and specialized, perhaps move all actions to an `actions.py` file?
    def _on_get_node_info_action(self, event: ops.ActionEvent) -> None:
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
            rpc_port = ServiceArgs(self.config, self.rpc_urls()).rpc_port
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

    def _on_get_node_help_action(self, event: ops.ActionEvent) -> None:
        event.set_results(results={'help-output': utils.get_client_binary_help_output()})

    def _on_print_readme_action(self, event: ops.ActionEvent) -> None:
        """ Handle print readme action. """
        event.set_results(results={'readme': utils.get_readme()})


if __name__ == "__main__":
    ops.main(PolkadotCharm)
