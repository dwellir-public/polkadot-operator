#!/usr/bin/env python3

from pathlib import Path

DEFAULT_APP_NAME = "polkadot"
DEFAULT_PROMETHEUS_PORT = "9615"
SNAP_USER = "root"
DEFAULT_SNAP_CONFIG = {
    "polkadot": {
        "snap_name": "polkadot",
        "service_name": "polkadot",
        "cli_app": "polkadot-cli",
        "binary_name": "polkadot",
    },
    "polkadot-parachain": {
        "snap_name": "polkadot-parachain",
        "service_name": "polkadot-parachain",
        "cli_app": "cli",
        "binary_name": "polkadot-parachain",
    },
}

DOCKER_DEAMON_CONFIG_PATH = Path("/etc/docker/daemon.json")
DOCKER_DEAMON_JSON_CONFIG = """{
  "storage-driver": "fuse-overlayfs"
}
"""
