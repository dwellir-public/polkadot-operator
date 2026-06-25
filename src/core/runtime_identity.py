#!/usr/bin/env python3

import hashlib
from pathlib import Path

from core import constants as c


def snap_instance_key(app_name: str) -> str:
    """Return the snap parallel-instance key for an application name."""
    if app_name == c.DEFAULT_APP_NAME:
        return ""
    return hashlib.sha1(app_name.encode("utf-8")).hexdigest()[:10]


def _snap_instance_name(base_snap_name: str, instance_key: str) -> str:
    if not instance_key:
        return base_snap_name
    return f"{base_snap_name}_{instance_key}"


def _build_snap_config(instance_key: str) -> dict:
    snap_config = {}
    for config_name, base_config in c.DEFAULT_SNAP_CONFIG.items():
        base_snap_name = base_config["snap_name"]
        snap_name = _snap_instance_name(base_snap_name, instance_key)
        base_path = Path("/var/snap", snap_name, "common/polkadot_base")
        snap_config[config_name] = {
            **base_config,
            "snap_name": snap_name,
            "base_snap_name": base_snap_name,
            "cli_command": f"{snap_name}.{base_config['cli_app']}",
            "base_path": base_path,
            "snap_binary_path": Path(
                "/snap",
                snap_name,
                "current/bin",
                base_config["binary_name"],
            ),
            "chain_spec_dir": Path("/var/snap", snap_name, "common/spec"),
            "chain_db_dir": Path(base_path, "chains"),
            "relay_db_dir": Path(base_path, "polkadot"),
            "wasm_dir": Path(base_path, "wasm"),
            "node_key_file": Path("/var/snap", snap_name, "common/node-key"),
            "systemd_service": f"snap.{snap_name}.{base_config['service_name']}.service",
        }
    return snap_config


def snap_config_for_app(app_name: str) -> dict:
    """Return snap configuration for an application name without mutating globals."""
    return _build_snap_config(snap_instance_key(app_name))


def configure_runtime_identity(app_name: str) -> None:
    """Configure host-level resource names from the Juju application name."""
    c.USER = app_name
    c.SERVICE_NAME = c.USER
    c.HOME_DIR = Path("/home", c.USER)
    c.BASE_PATH = Path(c.HOME_DIR, ".local/share/polkadot")
    c.BINARY_FILE = Path(c.HOME_DIR, "polkadot")
    c.EXECUTE_WORKER_BINARY_FILE = {"default": Path(c.HOME_DIR, "polkadot-execute-worker"), "enjin": Path(c.HOME_DIR, "enjin-execute-worker"), "canary": Path(c.HOME_DIR, "enjin-execute-worker")}
    c.PREPARE_WORKER_BINARY_FILE = {"default": Path(c.HOME_DIR, "polkadot-prepare-worker"), "enjin": Path(c.HOME_DIR, "enjin-prepare-worker"), "canary": Path(c.HOME_DIR, "enjin-prepare-worker")}
    c.CHAIN_SPEC_DIR = Path(c.HOME_DIR, "spec")
    c.NODE_KEY_FILE = Path(c.HOME_DIR, "node-key")
    c.DB_CHAIN_DIR = Path(c.BASE_PATH, "chains")
    c.DB_RELAY_DIR = Path(c.BASE_PATH, "polkadot")
    c.WASM_DIR = Path(c.HOME_DIR, "wasm")
    c.SNAP_INSTANCE_KEY = snap_instance_key(app_name)
    c.SNAP_CONFIG = _build_snap_config(c.SNAP_INSTANCE_KEY)
    c.DOCKER_CONTAINER_NAME = f"{c.USER}-install-tmp"
