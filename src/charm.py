#!/usr/bin/env python3
# Copyright 2024 Dwellir AB
# See LICENSE file for licensing details.

"""Charm the Polkadot blockchain client service."""

import logging
from requests.exceptions import ConnectionError as RequestsConnectionError
from urllib3.exceptions import NewConnectionError, MaxRetryError
from core.managers import WorkloadType, WorkloadFactory, PolkadotSnapManager
import time
import re
import json
import subprocess as sp

import ops

from interface_prometheus import PrometheusProvider
from interface_rpc_url_provider import RpcUrlProvider
from interface_rpc_url_requirer import RpcUrlRequirer
from migrators import node_key_migrator
from polkadot_rpc_wrapper import PolkadotRpcWrapper
from core.service_args import ServiceArgs
from core.utils import general_util

from core.utils import user_group_util
from migrators import data_migrator

from charms.grafana_agent.v0.cos_agent import COSAgentProvider

logger = logging.getLogger(__name__)


class PolkadotCharm(ops.CharmBase):
    """Charm the Polkadot blockchain client service."""

    _stored = ops.framework.StoredState()

    def __init__(self, *args):
        super().__init__(*args)
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
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
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
        self.framework.observe(self.on.migrate_data_action, self._on_migrate_data_action)
        self.framework.observe(self.on.snap_refresh_action, self._on_snap_refresh_action)
        self.framework.observe(self.on.migrate_node_key_action, self._on_migrate_node_key_action)

        self._stored.set_default(binary_url=self.config.get('binary-url'),
                                 docker_tag=self.config.get('docker-tag'),
                                 service_args=self.config.get('service-args'),
                                 chain_spec_url=self.config.get('chain-spec-url'),
                                 local_relaychain_spec_url=self.config.get('local-relaychain-spec-url'),
                                 wasm_runtime_url=self.config.get('wasm-runtime-url'),
                                 snap_hold=self.config.get('snap-hold'),
                                 snap_endure=self.config.get('snap-endure'),
                                 snap_revision=self.config.get('snap-revision'),
                                 snap_channel=self.config.get('snap-channel'),
                                 snap_name=self.config.get('snap-name'),
                                 service_init=True,
                                 )

        # Configure the workload as it was the last time the charm was executed
        if self._stored.binary_url or self._stored.docker_tag:
            self._workload = WorkloadFactory.BINARY_MANAGER
            self._workload.configure(
                charm_base_dir=self.charm_dir,
                binary_url=self._stored.binary_url,
                docker_tag=self._stored.docker_tag,
                binary_sha256_url=self.config.get('binary-sha256-url'),
                chain_name=ServiceArgs(self.config, self.rpc_urls()).chain_name,
            )
        else:
            self._workload = WorkloadFactory.SNAP_MANAGER
            self._workload.configure(
                channel=self._stored.snap_channel,
                revision=self._stored.snap_revision,
                hold=self._stored.snap_hold,
                endure=self._stored.snap_endure,
                snap_name=self._stored.snap_name,
            )

    def rpc_urls(self):
        """
        Return the RPC URL:s that are currently available in all relay-rpc-url relations.
        The magic comprehension below is the unfortunate actual best method to perform this
        list flattening operation in Python.
        """
        return [subdata["ws_url"] for relation in self.model.relations["relay-rpc-url"] for subdata in relation.data.values() if "ws_url" in subdata]

    def _on_install(self, event: ops.InstallEvent) -> None:
        # validate that the client configuration is correct
        if not self._has_valid_client_config():
            logger.error("Invalid client configuration, only one of 'binary-url', 'docker-tag' or 'snap-name' can be set at a time.")
            self.unit.status = ops.BlockedStatus("Only one of 'binary-url', 'docker-tag' or 'snap-name' can be set at a time.")
            event.defer()
            return
        
        self.unit.status = ops.MaintenanceStatus("Begin installing charm")
        service_args_obj = ServiceArgs(self.config, self.rpc_urls())
        # Setup polkadot group and user, disable login
        user_group_util.setup_group_and_user()
        # Create environment file for polkadot service arguments

        if service_args_obj.is_binary:
            self.unit.status = ops.MaintenanceStatus("Installing binary")
        else:
            self.unit.status = ops.MaintenanceStatus("Installing snap")
        self._workload.install()
        
        if self.config.get('wasm-runtime-url'):
            self._workload.download_wasm_runtime(self.config.get('wasm-runtime-url'))

        self._workload.generate_node_key()
        self._workload.set_service_args(service_args_obj.service_args_string)
        self.unit.status = ops.MaintenanceStatus("Charm install complete")
    

    def _on_upgrade_charm(self, event: ops.UpgradeCharmEvent) -> None:
        # Charm upgrade should not automatically start the service
        self._stored.service_init = False

    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        # validate that the client configuration is correct
        if not self._has_valid_client_config():
            logger.error("Invalid client configuration, only one of 'binary-url', 'docker-tag' or 'snap-name' can be set at a time.")
            self.unit.status = ops.BlockedStatus("Only one of 'binary-url', 'docker-tag' or 'snap-name' can be set at a time.")
            event.defer()
            return
        
        try:
            service_args_obj = ServiceArgs(self.config, self.rpc_urls())
        except ValueError as e:
            self.unit.status = ops.BlockedStatus(str(e))
            event.defer()
            return

        # Get the service status to determine if a restart is needed
        should_restart = self._workload.is_service_running()

        # NB: The install operation would stop the service if it's running.
        # The caller is responsible for restarting the service afterwards.
        #
        # Switching the workload type (binary to snap or snap to binary) would
        # not cause a restart if the service is already running.
        # The operator must handle this manually through the juju api. This is necessary
        # to ensure that data and key migration can or should be applied afterwards.
        try:
            # Update of polkadot binary requested
            if self._stored.binary_url != self.config.get('binary-url') or \
                self._stored.docker_tag != self.config.get('docker-tag'):

                # If either binary-url or docker-tag is set, switch to binary manager
                # and configure it with the current settings
                if  self.config.get('binary-url') or self.config.get('docker-tag'):
                        if self._workload.get_type() == WorkloadType.SNAP:
                            self.unit.status = ops.MaintenanceStatus("Uninstalling snap")
                            self._workload.uninstall()
                            self.unit.status = ops.MaintenanceStatus("Installing binary")
                            self._workload = WorkloadFactory.BINARY_MANAGER
                            should_restart = False
                        else:
                            self.unit.status = ops.MaintenanceStatus("Updating binary")
                        self._workload.configure(
                            binary_url=self.config.get('binary-url'),
                            docker_tag=self.config.get('docker-tag'),
                            charm_base_dir=self.charm_dir,
                            binary_sha256_url=self.config.get('binary-sha256-url'),
                            chain_name=service_args_obj.chain_name,
                        )
                # If neither binary-url nor docker-tag is set, switch to snap manager
                # and configure it with the current settings
                else:
                    if self._workload.get_type() == WorkloadType.BINARY:
                        self.unit.status = ops.MaintenanceStatus("Uninstalling binary")
                        self._workload.uninstall()
                        self.unit.status = ops.MaintenanceStatus("Installing Snap")
                        self._workload = WorkloadFactory.SNAP_MANAGER
                        should_restart = False
                    self._workload.configure(
                        channel=self.config.get('snap-channel'),
                        revision=self.config.get('snap-revision'),
                        hold=self.config.get('snap-hold'),
                        endure=self.config.get('snap-endure'),
                        snap_name=self.config.get('snap-name'),
                    )
                
                self._workload.install()

            # Update of snap revision or channel is changed
            elif self._stored.snap_revision != self.config.get('snap-revision') or \
                self._stored.snap_channel != self.config.get('snap-channel'):

                # Only update if the workload is of type POLKADOT_SNAP otherwise
                # ignore the changes to snap-channel and snap-revision
                if self._workload.get_type() == WorkloadType.SNAP:
                    self.unit.status = ops.MaintenanceStatus("Updating Snap")
                    self._workload.configure(
                        channel=self.config.get('snap-channel'),
                        revision=self.config.get('snap-revision'),
                        hold=self.config.get('snap-hold'),
                        endure=self.config.get('snap-endure'),
                        snap_name=self.config.get('snap-name'),
                    )
                    self._workload.install()
                else:
                    should_restart = False
                # Update stored snap configurations
                self._stored.snap_name = self.config.get('snap-name')
                self._stored.snap_hold = self.config.get('snap-hold')
                self._stored.snap_endure = self.config.get('snap-endure')

            # Update stored configurations
            self._stored.binary_url = self.config.get('binary-url')
            self._stored.docker_tag = self.config.get('docker-tag')
            self._stored.snap_revision = self.config.get('snap-revision')
            self._stored.snap_channel = self.config.get('snap-channel')
        except ValueError as e:
            self.unit.status = ops.BlockedStatus(str(e))
            event.defer()
            return

        # Update of polkadot service arguments requested
        if self._stored.service_args != self.config.get('service-args'):
            self.unit.status = ops.MaintenanceStatus("Updating service args")
            self._workload.set_service_args(service_args_obj.service_args_string)
            self._stored.service_args = self.config.get('service-args')

        if self._stored.chain_spec_url != self.config.get('chain-spec-url'):
            try:
                self.unit.status = ops.MaintenanceStatus("Updating chain spec")
                self._workload.set_service_args(service_args_obj.service_args_string)
                self._stored.chain_spec_url = self.config.get('chain-spec-url')
            except ValueError as e:
                self.unit.status = ops.BlockedStatus(str(e))
                event.defer()
                return

        if self._stored.local_relaychain_spec_url != self.config.get('local-relaychain-spec-url'):
            try:
                self.unit.status = ops.MaintenanceStatus("Updating relaychain spec")
                self._workload.set_service_args(service_args_obj.service_args_string)
                self._stored.local_relaychain_spec_url = self.config.get('local-relaychain-spec-url')
            except ValueError as e:
                self.unit.status = ops.BlockedStatus(str(e))
                event.defer()
                return
        
        if self._stored.wasm_runtime_url != self.config.get('wasm-runtime-url'):
            self.unit.status = ops.MaintenanceStatus("Updating wasm runtime")
            self._workload.download_wasm_runtime(self.config.get('wasm-runtime-url'))
            self._workload.set_service_args(service_args_obj.service_args_string)
            self._stored.wasm_runtime_url = self.config.get('wasm-runtime-url')

        if self._workload.get_type() == WorkloadType.SNAP:
            if self._stored.snap_hold != self.config.get('snap-hold'):
                try:
                    logger.info(f"Changing snap hold: from {self._stored.snap_hold} to {self.config.get('snap-hold')}")
                    self.unit.status = ops.MaintenanceStatus("Updating snap hold")
                    self._workload.set_hold(self.config.get('snap-hold'))
                    self._stored.snap_hold = self.config.get('snap-hold')
                    logger.info(f"Snap hold changed to {self.config.get('snap-hold')} successfully")
                except ValueError as e:
                    self.unit.status = ops.BlockedStatus(str(e))
                    event.defer()
                    return
            
            if self._stored.snap_endure != self.config.get('snap-endure'):
                try:
                    logger.info(f"Changing snap endure: from {self._stored.snap_endure} to {self.config.get('snap-endure')}")
                    self.unit.status = ops.MaintenanceStatus("Updating snap endure")
                    self._workload.set_endure(self.config.get('snap-endure'))
                    self._stored.snap_endure = self.config.get('snap-endure')
                    logger.info(f"Snap endure changed to {self.config.get('snap-endure')} successfully")
                except ValueError as e:
                    self.unit.status = ops.BlockedStatus(str(e))
                    event.defer()
                    return
            if self._stored.snap_name != self.config.get('snap-name'):
                try:
                    logger.info(f"Changing snap name: from {self._stored.snap_name} to {self.config.get('snap-name')}")
                    self.unit.status = ops.MaintenanceStatus("Updating snap name")
                    if self._workload.is_service_running():
                        self._workload.stop_service()
                        should_restart = True

                    self.unit.status = ops.MaintenanceStatus("Uninstalling old snap")
                    self._workload.uninstall()

                    self.unit.status = ops.MaintenanceStatus("Installing new snap")
                    self._workload.configure(
                        channel=self.config.get('snap-channel'),
                        revision=self.config.get('snap-revision'),
                        hold=self.config.get('snap-hold'),
                        endure=self.config.get('snap-endure'),
                        snap_name=self.config.get('snap-name'),
                    )
                    self._workload.install()
                    self._stored.snap_name = self.config.get('snap-name')
                    logger.info(f"Snap name changed to {self.config.get('snap-name')} successfully")
                except ValueError as e:
                    self.unit.status = ops.BlockedStatus(str(e))
                    event.defer()
                    return

        self._workload.set_service_args(service_args_obj.service_args_string)
        # Start the service if it was just initialized or restart is required due to config changes
        if self._stored.service_init or should_restart:
            self._workload.start_service()

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
        if self._workload.is_service_running():
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
                    status_message += f", client-type: {self._get_client_type()}"
                    self.unit.status = ops.ActiveStatus(status_message)
                    self.unit.set_workload_version(self._get_workload_version())
                    break
                except RequestsConnectionError as e:
                    logger.warning(e)
                    self.unit.status = ops.MaintenanceStatus(
                        "Client not responding to HTTP (attempt {}/{})".format(i + 1, connection_attempts))
            if type(self.unit.status) != ops.ActiveStatus:
                self.unit.status = ops.WaitingStatus("Service running but not responding to HTTP")
        else:
            self.unit.status = ops.BlockedStatus(f"Service not running, client-type: {self._get_client_type()}")

    def update_status_simple(self, iterations=4) -> None:
        """
        Update the status of the unit based on the state of the service.
        This is a simplified version of the update_status method, meant to give a quicker response.
        """
        if self._workload.is_service_started(iterations=iterations):
            self.unit.status = ops.ActiveStatus(f"Service running, client-type: {self._get_client_type()}")
        else:
            self.unit.status = ops.BlockedStatus(f"Service not running, client-type: {self._get_client_type()}")
        self.unit.set_workload_version(self._get_workload_version())

    def _on_start(self, event: ops.StartEvent) -> None:
        self._workload.start_service()
        self.update_status_simple()

    def _on_stop(self, event: ops.StopEvent) -> None:
        self._workload.stop_service()
        self.update_status_simple()

    def _on_get_session_key_action(self, event: ops.ActionEvent) -> None:
        event.log("Getting new session key through RPC...")
        rpc_port = ServiceArgs(self.config, self.rpc_urls()).rpc_port
        key = PolkadotRpcWrapper(rpc_port).get_session_key()
        if key:
            event.set_results(results={'session-keys-merged': key})

            # For convenience, also print a split version of the session key
            keys_split = general_util.split_session_key(key)
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
        self._workload.restart_service()
        if not self._workload.is_service_running(iterations=4):
            event.fail("Could not restart service")
        event.set_results(results={'message': 'Node service restarted'})
        self.update_status_simple()

    def _on_start_node_service_action(self, event: ops.ActionEvent) -> None:
        self._workload.start_service()
        if not self._workload.is_service_running(iterations=4):
            event.fail("Could not start service")
        event.set_results(results={'message': 'Node service started'})
        self.update_status_simple()

    def _on_stop_node_service_action(self, event: ops.ActionEvent) -> None:
        self._workload.stop_service()
        if self._workload.is_service_running(iterations=2):
            event.fail("Could not stop service")
        event.set_results(results={'message': 'Node service stopped'})
        self.update_status_simple(iterations=2)

    def _on_set_node_key_action(self, event: ops.ActionEvent) -> None:
        key = event.params['key']
        should_restart = self._workload.is_service_running()
        if should_restart:
            self._workload.stop_service()
        self._workload.write_node_key_file(key)
        if should_restart:
            self._workload.start_service()
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
        address = event.params.get('address', None)
        proxy_type = secret.get_content(refresh=True).get('proxy-type', None)
        if address and not proxy_type:
            event.fail(f"'proxy-type' needs to be set in the secret '{mnemonic_secret_id}' to use the 'address' parameter.")
            return
        if proxy_type and not address:
            event.fail(f"Parameter 'address' must be used since the secret {mnemonic_secret_id} is configured as a proxy account with 'proxy-type' set.")
            return
        try:
            result = PolkadotRpcWrapper(rpc_port).set_session_key_on_chain(mnemonic, proxy_type, address)
        except ValueError as e:
            event.fail(str(e))
            return

        event.set_results(results={'message': 'Session key successfully set on chain.'})
        event.set_results(results={'blocknumber-extrinsicindex': result})

    # TODO: this action is getting quite large and specialized, perhaps move all actions to an `actions.py` file?
    def _on_get_node_info_action(self, event: ops.ActionEvent) -> None:
        # Disk usage
        relay_du = self._workload.get_relay_disk_usage()
        chain_du = self._workload.get_chain_disk_usage()
        if not relay_du:
            # If only the chain DB exists, we're on a relay chain
            event.set_results(results={'disk-usage': chain_du})
        else:
            # If a relay DB also exists, we're on a parachain
            event.set_results(results={'disk-usage-relay': relay_du})
            event.set_results(results={'disk-usage-para': chain_du})
        # Client
        event.set_results(results={'client-service-args': self._workload.get_service_args()})
        event.set_results(results={'client-binary-version': self._get_workload_version()})
        event.set_results(results={'client-workload-type': self._workload.get_type().value})
        event.set_results(results={'client-binary-md5sum': self._workload.get_binary_md5sum()})
        event.set_results(results={'client-binary-last-changed': self._workload.get_binary_last_changed()})
        event.set_results(results={'client-wasm-files': self._workload.get_wasm_info()})
        proc_cmdline = self._workload.get_proc_cmdline()
        if proc_cmdline:
            event.set_results(results={'client-proc-cmdline': proc_cmdline})
        else:
            event.set_results(results={'client-proc-cmdline': 'Process not found'})
        # Node type
        if self._workload.is_relay_chain_node():
            event.set_results(results={'node-type': 'Relaychain node'})
        elif self._workload.is_parachain_node():
            event.set_results(results={'node-type': 'Parachain node'})
            event.set_results(results={'node-relay': self._workload.get_relay_for_parachain()})
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
        event.set_results(results={'help-output': self._workload.get_client_binary_help_output()})

    def _on_print_readme_action(self, event: ops.ActionEvent) -> None:
        """ Handle print readme action. """
        event.set_results(results={'readme': general_util.get_readme()})

    def _on_migrate_data_action(self, event: ops.ActionEvent) -> None:
        """ Handle data migration action. """
        try:
            result = data_migrator.migrate_data(
                snap_name=event.params.get('snap-name'),
                dry_run=event.params.get('dry-run', False),
                reverse=event.params.get('reverse', False))

            if result["success"]:
                event.set_results({"result": json.dumps(result, indent=2)})
                logger.info("Data migration completed successfully")
            else:
                event.fail(f"Data migration failed: {json.dumps(result, indent=2)}")
        except Exception as e:
            logger.error(f"Data migration failed: {e}")
            event.fail(f"Data migration failed: {str(e)}")
    
    def _on_snap_refresh_action(self, event: ops.ActionEvent) -> None:
        """ Handle snap refresh action. """
        try:
            if not isinstance(self._workload, PolkadotSnapManager):
                raise ValueError("Current workload type is not a snap")
            self._workload.refresh()
            event.set_results({"message": "Snap refreshed successfully"})
            self.update_status_simple()
        except Exception as e:
            event.fail(f"Snap refresh failed: {str(e)}")
            event.set_results({"message": f"Snap refresh failed: {str(e)}"})

    def _on_migrate_node_key_action(self, event: ops.ActionEvent) -> None:
        """ Handle node key migration action. """
        try:
            service_args_obj = ServiceArgs(self.config, self.rpc_urls())
            dry_run = event.params.get('dry-run', False)
            reverse = event.params.get('reverse', False)
            snap_name = event.params.get('snap-name')
            result = node_key_migrator.migrate_node_key(snap_name=snap_name, dry_run=dry_run, reverse=reverse)
            if not dry_run:
                self._workload.set_service_args(service_args_obj.service_args_string)
            if result["success"]:
                event.set_results({"message": json.dumps(result, indent=2)})
            else:
                event.fail(f"Node key migration failed: {json.dumps(result, indent=2)}")
            self.update_status_simple()
        except Exception as e:
            logger.error(f"Node key migration failed: {e}")
            event.fail(f"Node key migration failed: {str(e)}")
    
    def _get_client_type(self) -> str:
        """ Return the current client type as a string. """
        return 'snap' if self._workload.get_type() == WorkloadType.SNAP else 'binary'
    
    def _has_valid_client_config(self) -> bool:
        """ Validate that the client configuration is correct. """
        # Only one of binary-url, docker-tag or snap-name can be set at a time
        values = [self.config.get('binary-url'), self.config.get('docker-tag'), self.config.get('snap-name')]
        if sum(bool(v) for v in values) >= 2:
            return False
        return True
    
    def _get_workload_version(self) -> str:
        """ Return the current workload version. """
        service_args = ServiceArgs(self.config, self.rpc_urls())
        if service_args.chain_name == 'bittensor':
            try:
                return PolkadotRpcWrapper(service_args.rpc_port).get_version()
            except Exception as e:
                logger.error(f"Could not get bittensor version via RPC: {e}")
        return self._workload.get_binary_version()

if __name__ == "__main__":
    ops.main(PolkadotCharm)
