#!/usr/bin/env python3

from pathlib import Path

USER_DIR = 'polkadot'
SERVICE_NAME = USER_DIR
HOME_PATH_DIR = Path('/home/polkadot')
BINARY_PATH_FILE = Path(HOME_PATH_DIR, 'polkadot')
CHAIN_SPEC_PATH_DIR = Path(HOME_PATH_DIR, 'spec')
NODE_KEY_PATH_FILE = Path(HOME_PATH_DIR, 'node-key')
DB_CHAIN_PATH_DIR = Path(HOME_PATH_DIR, '.local/share/polkadot/chains')
DB_RELAY_PATH_DIR = Path(HOME_PATH_DIR, '.local/share/polkadot/polkadot')
WASM_PATH_DIR = Path(HOME_PATH_DIR, 'wasm')
