#!/usr/bin/env python3
# Copyright 2025 Dwellir
# See LICENSE file for licensing details.

"""Functions for managing and interacting with the Polkadot workload.

This module provides functionality for managing the Polkadot snap package,
including installation, service management, and configuration.
"""

import logging
from typing import Optional
from subprocess import run, CalledProcessError
from charms.operator_libs_linux.v2 import snap

logger = logging.getLogger(__name__)


class PolkadotError(Exception):
    """Base exception for Polkadot workload errors."""
    pass


class InstallError(PolkadotError):
    """Raised when installation fails."""
    pass


class ServiceError(PolkadotError):
    """Raised when service operations fail."""
    pass


class PolkadotSnapManager:
    """Manages the Polkadot workload via snap package."""

    SNAP_NAME = "polkadot"
    SERVICE_NAME = "polkadot"
    CLI_COMMAND = "polkadot.polkadot-cli"

    def __init__(self):
        """Initialize the Polkadot workload manager."""
        try:
            cache = snap.SnapCache()
            self._polkadot_snap = cache[self.SNAP_NAME]
        except Exception as e:
            logger.error(f"Failed to initialize snap cache: {e}")
            raise PolkadotError(f"Failed to initialize: {e}")

    def ensure_and_connect(self, channel: Optional[str] = None, revision: Optional[str] = None) -> None:
        """Install or update the Polkadot snap package.
        
        Args:
            channel: The snap channel to install from (e.g., 'latest/stable')
            revision: Specific revision to install
            
        Raises:
            InstallError: If installation fails
        """
        try:
            logger.info(f"Installing {self.SNAP_NAME} from channel={channel}, revision={revision}")
            self._polkadot_snap.ensure(
                snap.SnapState.Latest,
                channel=channel,
                revision=revision,
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

    def start(self) -> None:
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

    def stop(self) -> None:
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

    def restart(self) -> None:
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

    def refresh(self, channel: str, revision: Optional[str] = None) -> None:
        """Refresh the Polkadot snap to a new channel or revision.
        
        Args:
            channel: The snap channel to refresh to
            revision: Specific revision to install
            
        Raises:
            InstallError: If refresh fails
        """
        run_args = ["snap", "refresh", self.SNAP_NAME]
        if channel:
            run_args.extend(["--channel", channel])
        if revision:
            run_args.extend(["--revision", revision])

        try:
            run(run_args, check=True)
            logger.info(f"Refreshed {self.SNAP_NAME} to channel={channel}, revision={revision}")
        except Exception as e:
            logger.error(f"Failed to refresh {self.SNAP_NAME}: {e}")
            raise InstallError(f"Refresh failed: {e}")

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

    @property
    def installed(self) -> bool:
        """Check if the Polkadot snap is installed.
        
        Returns:
            True if installed, False otherwise
        """
        return self._polkadot_snap.present

    @property
    def running(self) -> bool:
        """Check if the Polkadot service is running.
        
        Returns:
            True if running, False otherwise
        """
        try:
            return self._polkadot_snap.services[self.SERVICE_NAME]["active"]
        except KeyError:
            return False

    @property
    def version(self) -> str:
        """Get the current installed version of Polkadot.
        
        Returns:
            Version string if available, empty string if not installed,
            or 'unknown' if version check fails
        """
        if not self._polkadot_snap.present:
            return ""
        
        try:
            output = run(
                ["snap", "run", self.CLI_COMMAND, "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            return output.stdout.strip()
        except CalledProcessError as e:
            logger.error(f"Failed to get version: {e}")
            return "unknown"
