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
