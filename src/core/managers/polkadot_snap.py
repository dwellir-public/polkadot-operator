#!/usr/bin/env python3
# Copyright 2025 Dwellir
# See LICENSE file for licensing details.

"""Functions for managing and interacting with the Polkadot workload.

This module provides functionality for managing the Polkadot snap package,
including installation, service management, and configuration.
"""

import re
import logging
import subprocess as sp
from typing import Optional
from core import constants as c
from core.utils import download_util, general_util
from subprocess import CalledProcessError
from charms.operator_libs_linux.v2 import snap
from core.managers import WorkloadManager, WorkloadType
from core.exceptions import PolkadotError, InstallError, ServiceError

logger = logging.getLogger(__name__)

class PolkadotSnapManager(WorkloadManager):
    """Manages the Polkadot workload via snap package."""

    def __init__(self):
        """Initialize the Polkadot workload manager."""
        super().__init__(WorkloadType.SNAP)

    def refresh(self, channel: str = None, revision: Optional[str] = None) -> None:
        """Refresh the Polkadot snap to a new channel or revision.
        
        Args:
            channel: The snap channel to refresh to
            revision: Specific revision to install
            
        Raises:
            InstallError: If refresh fails
        """
        channel = channel or self._channel # change to self._channel if not provided
        revision = revision or self._revision # change to self._revision if not provided

        try:
            self._polkadot_snap.ensure(
                snap.SnapState.Latest,
                channel=channel,
                revision=revision,
            )
        except Exception as e:
            logger.error(f"Failed to refresh {self._snap_config.get('snap_name')}: {e}")
            raise InstallError(f"Refresh failed: {e}")

    def configure(self, **kwargs):
        self._snap_name = kwargs.get("snap_name")
        if not self._snap_name:
            raise ValueError(f"No snap-name provided. Please specify one of {list(c.SNAP_CONFIG.keys())}.")
        if not self._snap_name in c.SNAP_CONFIG:
            raise ValueError(f"Invalid snap-name provided: {self._snap_name}. Must be one of {list(c.SNAP_CONFIG.keys())}.")

        self._channel = kwargs.get("channel") if kwargs.get("channel") else None
        self._revision = kwargs.get("revision") if kwargs.get("revision") else None
        self._hold = kwargs.get("hold") if kwargs.get("hold") else None
        self._endure = kwargs.get("endure") if kwargs.get("endure") else None
        self._type = kwargs.get("chain-type")
        self._snap_config = c.SNAP_CONFIG[self._snap_name]

        try:
            cache = snap.SnapCache()
            self._polkadot_snap = cache[self._snap_config.get("snap_name")]
        except Exception as e:
            logger.error(f"Failed to initialize snap cache: {e}")
            raise PolkadotError(f"Failed to initialize: {e}")

    def install(self):
        if self._polkadot_snap.present:
            sp.run(['snap', 'enable', self._snap_config.get("snap_name")], check=False)
        self.ensure_and_connect()
        self.stop_service()

    def uninstall(self):
        if self.is_service_installed():
            if self.is_service_running():
                self.stop_service()
            sp.run(['snap', 'disable', self._snap_config.get("snap_name")], check=False)

    def ensure_and_connect(self) -> None:
        """Install or update the Polkadot snap package.
        
        Args:
            channel: The snap channel to install from (e.g., 'latest/stable')
            revision: Specific revision to install
            
        Raises:
            InstallError: If installation fails
        """
        try:
            logger.info(f"Installing {self._snap_config.get('snap_name')} from channel={self._channel}, revision={self._revision}")
            self._polkadot_snap.ensure(
                snap.SnapState.Latest,
                channel=self._channel,
                revision=self._revision,
            )
            logger.info(f"{self._snap_config.get('snap_name')} installed successfully")

            logger.info(f"Setting connection plugs for {self._snap_config.get('snap_name')}")
            self._polkadot_snap.connect(plug='hardware-observe', service='polkadot')
            self._polkadot_snap.connect(plug='system-observe', service='polkadot')
            self._polkadot_snap.connect(plug='removable-media', service='polkadot')
            logger.info(f"Connection plugs set successfully for {self._snap_config.get('snap_name')}")

        except Exception as e:
            logger.error(f"Failed to install {self._snap_config.get('snap_name')}: {e}")
            raise InstallError(f"Installation failed: {e}")

    def start_service(self) -> None:
        """Start the Polkadot service.
        
        Raises:
            ServiceError: If service start fails
        """
        try:
            logger.info(f"Starting {self._snap_config.get('service_name')} service")
            self._polkadot_snap.start(enable=True)
            logger.info(f"{self._snap_config.get('service_name')} service started successfully")
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            raise ServiceError(f"Service start failed: {e}")

    def stop_service(self) -> None:
        """Stop the Polkadot service.
        
        Raises:
            ServiceError: If service stop fails
        """
        try:
            logger.info(f"Stopping {self._snap_config.get('service_name')} service")
            self._polkadot_snap.stop(disable=True)
            logger.info(f"{self._snap_config.get('service_name')} service stopped successfully")
        except Exception as e:
            logger.error(f"Failed to stop service: {e}")
            raise ServiceError(f"Service stop failed: {e}")

    def restart_service(self) -> None:
        """Restart the Polkadot service.
        
        Raises:
            ServiceError: If service restart fails
        """
        try:
            logger.info(f"Restarting {self._snap_config.get('service_name')} service")
            self._polkadot_snap.restart(reload=True)
            logger.info(f"{self._snap_config.get('service_name')} service restarted successfully")
        except Exception as e:
            logger.error(f"Failed to restart service: {e}")
            raise ServiceError(f"Service restart failed: {e}")
    
    def is_service_running(self, iterations=1) -> bool:
        """Check if the Polkadot service is running.
        
        Returns:
            True if running, False otherwise
        """
        try:
            return self._polkadot_snap.services[self._snap_config.get("service_name")]["active"]
        except KeyError:
            return False
        
    def upgrade_service(self):
        is_running = False
        if self.is_service_installed() and self.is_service_running():
            is_running = True
            self.stop_service()
        self.install()
        if is_running:
            self.start_service()

    def get_service_args(self) -> str:
        """Get the snap service arguments.
        
        Returns:
            Current service arguments as a string
            
        Raises:
            ServiceError: If getting service args fails
        """
        try:
            return self._polkadot_snap.get("service-args")
        except Exception as e:
            logger.error(f"Failed to get service args: {e}")
            raise ServiceError(f"Failed to get service args: {e}")

    def set_service_args(self, value: str) -> None:
        """Set the snap service arguments.
        
        Args:
            value: Service arguments string
            
        Raises:
            ServiceError: If setting service args fails
        """
        try:
            logger.info(f"Setting service args to: {value}")
            if not "--base-path" in value:
                value = f"--base-path {self._snap_config.get('base_path')} {value}"
            self._polkadot_snap.set({"service-args": value})
            logger.info("Service args set successfully")
        except Exception as e:
            logger.error(f"Failed to set service args: {e}")
            raise ServiceError(f"Failed to set service args: {e}")

    def set_hold(self, value: bool) -> None:
        """Set the snap hold state.

        Args:
            value: True to set hold, False to unset
        """
        if value:
            logger.info(f"Holding {self._snap_config.get('snap_name')} snap")
            self._polkadot_snap.hold()
        else:
            logger.info(f"Unholding {self._snap_config.get('snap_name')} snap")
            self._polkadot_snap.unhold()

    def set_endure(self, value: bool) -> None:
        """Set the snap endure state.

        Args:
            value: True to set endure, False to unset
        """
        if value:
            logger.info(f"Setting {self._snap_config.get('snap_name')} snap to endure state")
            self._polkadot_snap.set({"endure": "true"})
        else:
            logger.info(f"Unsetting endure state for {self._snap_config.get('snap_name')} snap")
            self._polkadot_snap.set({"endure": "false"})

    def get_binary_version(self) -> str:
        """Get the current installed version of Polkadot.
        
        Returns:
            Version string if available, empty string if not installed,
            or 'unknown' if version check fails
        """
        if not self._polkadot_snap.present:
            return ""
        
        try:
            command = ["snap", "run", self._snap_config.get("cli_command"), "--version"]
            output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
            version = re.search(r'([\d.]+)', output).group(1)
            return version
        except CalledProcessError as e:
            logger.error(f"Failed to get version: {e}")
            return "unknown"
    
    def get_service_version(self) -> str:
        return self.get_binary_version()

    def get_client_binary_help_output(self):
        return general_util.get_client_binary_help_output(f"{self._snap_config.get('cli_command')} --help")

    def download_wasm_runtime(self, url: str) -> None:
        download_util.download_wasm_runtime(url, self._snap_config.get("wasm_dir"), c.SNAP_USER)

    def get_wasm_info(self) -> str:
        return general_util.get_wasm_info(self._snap_config.get("wasm_dir"))

    def is_service_started(self, iterations: int) -> bool:
        return self.is_service_running(iterations)
    
    def get_chain_disk_usage(self) -> str:
        return general_util.get_disk_usage(self._snap_config.get("chain_db_dir"))

    def get_relay_disk_usage(self) -> str:
        return general_util.get_disk_usage(self._snap_config.get("relay_db_dir"))

    def is_service_installed(self) -> bool:
        return self._polkadot_snap.present
    
    def service_args_differ_from_disk(self, argument_string):
        current_args = self.get_service_args()
        if not '--base-path' in argument_string:
            argument_string = f"--base-path {self._snap_config.get('base_path')} {current_args}"
        return current_args != argument_string

    def generate_node_key(self) -> str:
        if self.is_service_installed():
            node_key_file = self._snap_config.get("node_key_file").as_posix()
            command = [self._snap_config.get("cli_command"), 'key', 'generate-node-key', '--file', node_key_file]

            # This is to make it work on Enjin relay deployments
            logger.debug("Getting binary version from client binary to check if it is Enjin.")
            get_version_command = [self._snap_config.get("cli_command"), "--version"]
            output = sp.run(get_version_command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip().lower()
            if "enjin" in output:
                command += ['--chain', 'enjin']

            sp.run(command, check=False)
            sp.run(['chown', f'{c.SNAP_USER}:{c.SNAP_USER}', node_key_file], check=False)
            sp.run(['chmod', '0600', node_key_file], check=False)
        else:
            raise ValueError("No binary file found to generate node key. Please check your configuration.")

    def get_binary_last_changed(self) -> str:
        return general_util.get_binary_last_changed(self._snap_config.get("snap_binary_path"))
    
    def get_binary_md5sum(self) -> str:
        return general_util.get_binary_md5sum(self._snap_config.get("snap_binary_path"))

    def get_proc_cmdline(self) -> str:
        return general_util.get_process_cmdline(self._snap_config.get("service_name")[:15])

    def is_relay_chain_node(self) -> bool:
        return not self.is_parachain_node()

    def is_parachain_node(self) -> bool:
        if self._snap_config.get("chain_db_dir").exists() and self._snap_config.get("relay_db_dir").exists():
            return True
        if self.is_service_installed():
            command = f'snap run {self._snap_config.get("cli_command")} --help | grep -i "\-\-collator"'
            output = sp.run(command, stdout=sp.PIPE, cwd='/', shell=True, check=False)
            if output.returncode == 0:
                return True
        return False
    
    def write_node_key_file(self, key) -> None:
        node_key_file = self._snap_config.get("node_key_file")
        general_util.write_node_key_file(node_key_file, key, c.SNAP_USER)

    def get_relay_for_parachain(self):
        if not self.is_parachain_node():
            return 'Error, this is not a parachain'
        return general_util.get_relay_for_parachain(self._snap_config.get("relay_db_dir"))
