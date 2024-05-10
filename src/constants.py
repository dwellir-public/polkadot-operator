#!/usr/bin/env python3

from pathlib import Path

USER = 'polkadot'
SERVICE_NAME = USER
HOME_DIR = Path('/home/polkadot')
BINARY_PATH_FILE = Path(HOME_DIR, 'polkadot')
CHAIN_SPEC_PATH_DIR = Path(HOME_DIR, 'spec')
NODE_KEY_PATH_FILE = Path(HOME_DIR, 'node-key')
DB_CHAIN_PATH_DIR = Path(HOME_DIR, '.local/share/polkadot/chains')
DB_RELAY_PATH_DIR = Path(HOME_DIR, '.local/share/polkadot/polkadot')
WASM_PATH_DIR = Path(HOME_DIR, 'wasm')
