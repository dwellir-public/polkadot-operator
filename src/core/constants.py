#!/usr/bin/env python3

from pathlib import Path

USER = 'polkadot'
SNAP_USER = 'root'
SERVICE_NAME = USER
HOME_DIR = Path('/home/polkadot')
SNAP_COMMON_DIR = Path('/var/snap/polkadot/common')
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

SNAP_SERVICE_NAME = "snap.polkadot.polkadot"
SNAP_BINARY = "polkadot.polkadot-cli"
SNAP_NODE_KEY_FILE = Path(SNAP_COMMON_DIR, 'node-key')
SNAP_CHAIN_SPEC_DIR = Path(SNAP_COMMON_DIR, 'spec')
SNAP_DB_CHAIN_DIR = Path(SNAP_COMMON_DIR, 'polkadot_base', 'chains')
SNAP_DB_RELAY_DIR = Path(SNAP_COMMON_DIR, 'polkadot_base', 'polkadot')
SNAP_WASM_DIR = Path(SNAP_COMMON_DIR, 'wasm')
