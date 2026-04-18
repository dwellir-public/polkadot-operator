# Copyright 2021 dwellir
# See LICENSE file for licensing details.

import sys
import types
from types import SimpleNamespace

substrateinterface = types.ModuleType("substrateinterface")
substrateinterface.SubstrateInterface = object
substrateinterface.Keypair = object
sys.modules.setdefault("substrateinterface", substrateinterface)

from charm import PolkadotCharm


def test_has_valid_client_config_allows_single_source():
    charm = SimpleNamespace(
        config={
            "binary-url": "",
            "docker-tag": "",
            "snap-name": "polkadot",
        }
    )

    assert PolkadotCharm._has_valid_client_config(charm) is True


def test_has_valid_client_config_rejects_multiple_sources():
    charm = SimpleNamespace(
        config={
            "binary-url": "https://example.invalid/polkadot",
            "docker-tag": "v1.0.0",
            "snap-name": "",
        }
    )

    assert PolkadotCharm._has_valid_client_config(charm) is False
