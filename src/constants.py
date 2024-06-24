#!/usr/bin/env python3

from pathlib import Path

USER = 'polkadot'
SERVICE_NAME = USER
HOME_DIR = Path('/home/polkadot')
BINARY_FILE = Path(HOME_DIR, 'polkadot')
CHAIN_SPEC_DIR = Path(HOME_DIR, 'spec')
NODE_KEY_FILE = Path(HOME_DIR, 'node-key')
DB_CHAIN_DIR = Path(HOME_DIR, '.local/share/polkadot/chains')
DB_RELAY_DIR = Path(HOME_DIR, '.local/share/polkadot/polkadot')
WASM_DIR = Path(HOME_DIR, 'wasm')
