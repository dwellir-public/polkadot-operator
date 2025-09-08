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
from subprocess import run, CalledProcessError
from charms.operator_libs_linux.v2 import snap
from core.managers import WorkloadManager, WorkloadType
from core.exceptions import PolkadotError, InstallError, ServiceError

logger = logging.getLogger(__name__)

class PolkadotSnapManager(WorkloadManager):
    """Manages the Polkadot workload via snap package."""

    SNAP_NAME = "polkadot"
    SERVICE_NAME = "polkadot"
    CLI_COMMAND = "polkadot.polkadot-cli"
    BASE_PATH = "/var/snap/polkadot/common/polkadot_base"
    SNAP_BINARY_PATH = "/snap/polkadot/current/bin/polkadot"

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
            logger.error(f"Failed to refresh {self.SNAP_NAME}: {e}")
            raise InstallError(f"Refresh failed: {e}")

    def configure(self, **kwargs):
        self._channel = kwargs.get("channel") if kwargs.get("channel") else None
        self._revision = kwargs.get("revision") if kwargs.get("revision") else None
        self._hold = kwargs.get("hold") if kwargs.get("hold") else None
        self._endure = kwargs.get("endure") if kwargs.get("endure") else None

        try:
            cache = snap.SnapCache()
            self._polkadot_snap = cache[self.SNAP_NAME]
        except Exception as e:
            logger.error(f"Failed to initialize snap cache: {e}")
            raise PolkadotError(f"Failed to initialize: {e}")

    def install(self):
        self.ensure_and_connect()
        self.stop_service()

    def ensure_and_connect(self) -> None:
        """Install or update the Polkadot snap package.
        
        Args:
            channel: The snap channel to install from (e.g., 'latest/stable')
            revision: Specific revision to install
            
        Raises:
            InstallError: If installation fails
        """
        try:
            logger.info(f"Installing {self.SNAP_NAME} from channel={self._channel}, revision={self._revision}")
            self._polkadot_snap.ensure(
                snap.SnapState.Latest,
                channel=self._channel,
                revision=self._revision,
            )
            logger.info(f"{self.SNAP_NAME} installed successfully")

            logger.info(f"Setting connection plugs for {self.SNAP_NAME}")
            self._polkadot_snap.connect(plug='hardware-observe', service='polkadot')
            self._polkadot_snap.connect(plug='system-observe', service='polkadot')
            self._polkadot_snap.connect(plug='removable-media', service='polkadot')
            logger.info(f"Connection plugs set successfully for {self.SNAP_NAME}")

        except Exception as e:
            logger.error(f"Failed to install {self.SNAP_NAME}: {e}")
            raise InstallError(f"Installation failed: {e}")

    def start_service(self) -> None:
        """Start the Polkadot service.
        
        Raises:
            ServiceError: If service start fails
        """
        try:
            logger.info(f"Starting {self.SERVICE_NAME} service")
            self._polkadot_snap.start(enable=True)
            logger.info(f"{self.SERVICE_NAME} service started successfully")
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            raise ServiceError(f"Service start failed: {e}")

    def stop_service(self) -> None:
        """Stop the Polkadot service.
        
        Raises:
            ServiceError: If service stop fails
        """
        try:
            logger.info(f"Stopping {self.SERVICE_NAME} service")
            self._polkadot_snap.stop(disable=True)
            logger.info(f"{self.SERVICE_NAME} service stopped successfully")
        except Exception as e:
            logger.error(f"Failed to stop service: {e}")
            raise ServiceError(f"Service stop failed: {e}")

    def restart_service(self) -> None:
        """Restart the Polkadot service.
        
        Raises:
            ServiceError: If service restart fails
        """
        try:
            logger.info(f"Restarting {self.SERVICE_NAME} service")
            self._polkadot_snap.restart(reload=True)
            logger.info(f"{self.SERVICE_NAME} service restarted successfully")
        except Exception as e:
            logger.error(f"Failed to restart service: {e}")
            raise ServiceError(f"Service restart failed: {e}")
    
    def is_service_running(self, iterations=1) -> bool:
        """Check if the Polkadot service is running.
        
        Returns:
            True if running, False otherwise
        """
        try:
            return self._polkadot_snap.services[self.SERVICE_NAME]["active"]
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
                value = f"--base-path {self.BASE_PATH} {value}"
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
            logger.info(f"Holding {self.SNAP_NAME} snap")
            self._polkadot_snap.hold()
        else:
            logger.info(f"Unholding {self.SNAP_NAME} snap")
            self._polkadot_snap.unhold()

    def set_endure(self, value: bool) -> None:
        """Set the snap endure state.

        Args:
            value: True to set endure, False to unset
        """
        if value:
            logger.info(f"Setting {self.SNAP_NAME} snap to endure state")
            self._polkadot_snap.set({"endure": "true"})
        else:
            logger.info(f"Unsetting endure state for {self.SNAP_NAME} snap")
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
            command = ["snap", "run", self.CLI_COMMAND, "--version"]
            output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
            version = re.search(r'([\d.]+)', output).group(1)
            return version
        except CalledProcessError as e:
            logger.error(f"Failed to get version: {e}")
            return "unknown"
    
    def get_service_version(self) -> str:
        return self.get_binary_version()

    def get_client_binary_help_output(self):
        return general_util.get_client_binary_help_output(f"{self.CLI_COMMAND} --help")

    def download_wasm_runtime(self, url: str) -> None:
        download_util.download_wasm_runtime(url, c.SNAP_WASM_DIR, c.SNAP_USER)

    def get_wasm_info(self) -> str:
        return general_util.get_wasm_info(c.SNAP_WASM_DIR)

    def is_service_started(self, iterations: int) -> bool:
        return self.is_service_running(iterations)
    
    def get_chain_disk_usage(self) -> str:
        return general_util.get_disk_usage(c.SNAP_DB_CHAIN_DIR)

    def get_relay_disk_usage(self) -> str:
        return general_util.get_disk_usage(c.SNAP_DB_RELAY_DIR)

    def is_service_installed(self) -> bool:
        return self._polkadot_snap.present
    
    def service_args_differ_from_disk(self, argument_string):
        current_args = self.get_service_args()
        return current_args != f"--base-path {self.BASE_PATH} {argument_string}"

    def generate_node_key(self) -> str:
        if self.is_service_installed():
            command = ['polkadot.polkadot-cli', 'key', 'generate-node-key', '--file', c.NODE_KEY_FILE]

            # This is to make it work on Enjin relay deployments
            logger.debug("Getting binary version from client binary to check if it is Enjin.")
            get_version_command = ['polkadot.polkadot-cli', "--version"]
            output = sp.run(get_version_command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip().lower()
            if "enjin" in output:
                command += ['--chain', 'enjin']

            sp.run(command, check=False)
            sp.run(['chown', f'{c.USER}:{c.USER}', c.NODE_KEY_FILE], check=False)
            sp.run(['chmod', '0600', c.NODE_KEY_FILE], check=False)
        else:
            raise ValueError("No binary file found to generate node key. Please check your configuration.")

    def get_binary_last_changed(self) -> str:
        return general_util.get_binary_last_changed(self.SNAP_BINARY_PATH)
    
    def get_binary_md5sum(self) -> str:
        return general_util.get_binary_md5sum(self.SNAP_BINARY_PATH)

    def get_proc_cmdline(self) -> str:
        return general_util.get_process_cmdline(self.SERVICE_NAME)

    def is_relay_chain_node(self) -> bool:
        return self.is_parachain_node()

    def is_parachain_node(self) -> bool:
        if c.SNAP_DB_CHAIN_DIR.exists() and c.SNAP_DB_RELAY_DIR.exists():
            return True
        if self.is_service_installed():
            command = f'snap run {self.CLI_COMMAND} --help | grep -i "\-\-collator"'
            output = sp.run(command, stdout=sp.PIPE, cwd='/', shell=True, check=False)
            if output.returncode == 0:
                return True
        return False
    
    def write_node_key_file(self, key) -> None:
        general_util.write_node_key_file(c.SNAP_NODE_KEY_FILE, key, c.SNAP_USER)
