#!/usr/bin/env python3

from pathlib import Path

from core import constants as c

app_name = c.DEFAULT_APP_NAME
user = c.DEFAULT_APP_NAME
service_name = user
home_dir = Path("/home/polkadot")
base_path = Path(home_dir, ".local/share/polkadot")
binary_file = Path(home_dir, "polkadot")
execute_worker_binary_file = {"default": Path(home_dir, "polkadot-execute-worker"), "enjin": Path(home_dir, "enjin-execute-worker"), "canary": Path(home_dir, "enjin-execute-worker")}
prepare_worker_binary_file = {"default": Path(home_dir, "polkadot-prepare-worker"), "enjin": Path(home_dir, "enjin-prepare-worker"), "canary": Path(home_dir, "enjin-prepare-worker")}
chain_spec_dir = Path(home_dir, "spec")
node_key_file = Path(home_dir, "node-key")
db_chain_dir = Path(base_path, "chains")
db_relay_dir = Path(base_path, "polkadot")
wasm_dir = Path(home_dir, "wasm")

snap_instance_key = ""


def build_snap_config(instance_key: str) -> dict:
    snap_config = {}
    for config_name, base_config in c.DEFAULT_SNAP_CONFIG.items():
        base_snap_name = base_config["snap_name"]
        snap_name = base_snap_name if not instance_key else f"{base_snap_name}_{instance_key}"
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


snap_config = build_snap_config(snap_instance_key)

docker_container_name = "polkadot-install-tmp"
