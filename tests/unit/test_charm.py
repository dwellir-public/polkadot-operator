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
from interface_machine_observability_provider import build_machine_observability_payload


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


def test_machine_observability_payload_contains_generic_sources():
    payload = build_machine_observability_payload(
        service_name="snap.polkadot.polkadot.service",
        charm_name="polkadot",
    )

    assert payload["schema_version"] == 1
    assert payload["charm_name"] == "polkadot"
    assert payload["systemd_units"] == ["snap.polkadot.polkadot.service"]
    assert payload["journal_match_expressions"] == []
    assert payload["metrics_endpoints"] == [
        {
            "targets": ["localhost:9615"],
            "path": "/metrics",
            "scheme": "http",
            "interval": "",
            "timeout": "",
            "tls": {},
        }
    ]
    assert payload["log_files"] == []
