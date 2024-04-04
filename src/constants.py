#!/usr/bin/env python3

from pathlib import Path

USER = 'polkadot'
SERVICE_NAME = USER
HOME_PATH = Path('/home/polkadot')
BINARY_PATH = Path(HOME_PATH, 'polkadot')
CHAIN_SPEC_PATH = Path(HOME_PATH, 'spec')
NODE_KEY_PATH = Path(HOME_PATH, 'node-key')
DB_CHAIN_PATH = Path(HOME_PATH, '.local/share/polkadot/chains')
DB_RELAY_PATH = Path(HOME_PATH, '.local/share/polkadot/polkadot')
WASM_PATH = Path(HOME_PATH, 'wasm')
