#!/usr/bin/env python3

import hashlib
from pathlib import Path

from core import constants as c
from core import runtime as r


def snap_instance_key(app_name: str) -> str:
    """Return the snap parallel-instance key for an application name."""
    if app_name == c.DEFAULT_APP_NAME:
        return ""
    return hashlib.sha1(app_name.encode("utf-8")).hexdigest()[:10]


def snap_config_for_app(app_name: str) -> dict:
    """Return snap configuration for an application name without mutating globals."""
    return r.build_snap_config(snap_instance_key(app_name))


def configure_runtime_identity(app_name: str) -> None:
    """Configure host-level resource names from the Juju application name."""
    r.app_name = app_name
    r.user = app_name
    r.service_name = r.user
    r.home_dir = Path("/home", r.user)
    r.base_path = Path(r.home_dir, ".local/share/polkadot")
    r.binary_file = Path(r.home_dir, "polkadot")
    r.execute_worker_binary_file = {"default": Path(r.home_dir, "polkadot-execute-worker"), "enjin": Path(r.home_dir, "enjin-execute-worker"), "canary": Path(r.home_dir, "enjin-execute-worker")}
    r.prepare_worker_binary_file = {"default": Path(r.home_dir, "polkadot-prepare-worker"), "enjin": Path(r.home_dir, "enjin-prepare-worker"), "canary": Path(r.home_dir, "enjin-prepare-worker")}
    r.chain_spec_dir = Path(r.home_dir, "spec")
    r.node_key_file = Path(r.home_dir, "node-key")
    r.db_chain_dir = Path(r.base_path, "chains")
    r.db_relay_dir = Path(r.base_path, "polkadot")
    r.wasm_dir = Path(r.home_dir, "wasm")
    r.snap_instance_key = snap_instance_key(app_name)
    r.snap_config = r.build_snap_config(r.snap_instance_key)
    r.docker_container_name = f"{r.user}-install-tmp"
