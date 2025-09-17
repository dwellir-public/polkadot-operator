#!/usr/bin/env python3

from pathlib import Path

USER = 'polkadot'
SERVICE_NAME = USER
HOME_DIR = Path('/home/polkadot')
BINARY_FILE = Path(HOME_DIR, 'polkadot')
EXECUTE_WORKER_BINARY_FILE = {
    'default': Path(HOME_DIR, 'polkadot-execute-worker'),
    'enjin': Path(HOME_DIR, 'enjin-execute-worker'),
    'canary': Path(HOME_DIR, 'enjin-execute-worker')
}
PREPARE_WORKER_BINARY_FILE = {
    'default': Path(HOME_DIR, 'polkadot-prepare-worker'),
    'enjin': Path(HOME_DIR, 'enjin-prepare-worker'),
    'canary': Path(HOME_DIR, 'enjin-prepare-worker')
}
CHAIN_SPEC_DIR = Path(HOME_DIR, 'spec')
NODE_KEY_FILE = Path(HOME_DIR, 'node-key')
DB_CHAIN_DIR = Path(HOME_DIR, '.local/share/polkadot/chains')
DB_RELAY_DIR = Path(HOME_DIR, '.local/share/polkadot/polkadot')
WASM_DIR = Path(HOME_DIR, 'wasm')

SNAP_USER = 'root'
SNAP_CONFIG = {
    'polkadot': {
        'snap_name': 'polkadot',
        'service_name': 'polkadot',
        'cli_command': 'polkadot.polkadot-cli',
        'base_path': Path('/var/snap/polkadot/common/polkadot_base'),
        'snap_binary_path': Path('/snap/polkadot/current/bin/polkadot'),
        'chain_spec_dir': Path('/var/snap/polkadot/common/polkadot_base/spec'),
        'chain_db_dir': Path('/var/snap/polkadot/common/polkadot_base/chains'),
        'relay_db_dir': Path('/var/snap/polkadot/common/polkadot_base/polkadot'),
        'wasm_dir': Path('/var/snap/polkadot/common/polkadot_base/wasm'),
        'node_key_file': Path('/var/snap/polkadot/common/node-key')
    },
    'polkadot-parachain': {
        'snap_name': 'polkadot-parachain',
        'service_name': 'polkadot-parachain',
        'cli_command': 'polkadot-parachain.cli',
        'base_path': Path('/var/snap/polkadot-parachain/common/polkadot_base'),
        'snap_binary_path': Path('/snap/polkadot-parachain/current/bin/polkadot-parachain'),
        'chain_spec_dir': Path('/var/snap/polkadot-parachain/common/polkadot_base/spec'),
        'chain_db_dir': Path('/var/snap/polkadot-parachain/common/polkadot_base/chains'),
        'relay_db_dir': Path('/var/snap/polkadot-parachain/common/polkadot_base/polkadot'),
        'wasm_dir': Path('/var/snap/polkadot-parachain/common/polkadot_base/wasm'),
        'node_key_file': Path('/var/snap/polkadot-parachain/common/node-key')
    }
}
