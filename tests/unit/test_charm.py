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
from charms.dwellir_observability.v0.machine_observability import (
    MACHINE_OBSERVABILITY_SCHEMA_VERSION,
    MachineObservabilityPayload,
    build_machine_observability_payload,
)


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

    assert isinstance(payload, MachineObservabilityPayload)
    assert payload.schema_version == MACHINE_OBSERVABILITY_SCHEMA_VERSION
    assert payload.charm_name == "polkadot"
    assert payload.systemd_units == ["snap.polkadot.polkadot.service"]
    assert payload.journal_match_expressions == []
    assert payload.metrics_endpoints[0].model_dump(mode="json") == {
        "targets": ["localhost:9615"],
        "path": "/metrics",
        "scheme": "http",
        "interval": "",
        "timeout": "",
        "tls": {},
    }
    assert payload.log_files == []


def test_machine_observability_payload_serializes_to_relation_shape():
    payload = build_machine_observability_payload(
        service_name="snap.polkadot.polkadot.service",
        charm_name="polkadot",
    )

    assert payload.model_dump(mode="json") == {
        "schema_version": 1,
        "charm_name": "polkadot",
        "systemd_units": ["snap.polkadot.polkadot.service"],
        "journal_match_expressions": [],
        "metrics_endpoints": [
            {
                "targets": ["localhost:9615"],
                "path": "/metrics",
                "scheme": "http",
                "interval": "",
                "timeout": "",
                "tls": {},
            }
        ],
        "log_files": [],
    }


def test_publish_machine_observability_uses_charm_metadata_and_runtime_service_name():
    published = {}

    charm = SimpleNamespace(
        config={
            "snap-name": "",
        },
        _stored=SimpleNamespace(snap_name=None),
        meta=SimpleNamespace(name="polkadot"),
        machine_observability_provider=SimpleNamespace(
            publish=lambda payload: published.update(payload)
        ),
    )
    charm._build_machine_observability_payload = (
        lambda: PolkadotCharm._build_machine_observability_payload(charm)
    )

    PolkadotCharm._publish_machine_observability(charm)

    assert published["charm_name"] == "polkadot"
    assert published["systemd_units"] == ["polkadot.service"]


def test_publish_machine_observability_uses_snap_service_name_when_snap_configured():
    published = {}

    charm = SimpleNamespace(
        config={
            "snap-name": "polkadot",
        },
        _stored=SimpleNamespace(snap_name=None),
        meta=SimpleNamespace(name="polkadot"),
        machine_observability_provider=SimpleNamespace(
            publish=lambda payload: published.update(payload)
        ),
    )
    charm._build_machine_observability_payload = (
        lambda: PolkadotCharm._build_machine_observability_payload(charm)
    )

    PolkadotCharm._publish_machine_observability(charm)

    assert published["systemd_units"] == ["snap.polkadot.polkadot.service"]


def test_build_machine_observability_payload_uses_snap_service_name_when_configured():
    charm = SimpleNamespace(
        config={"snap-name": "polkadot"},
        _stored=SimpleNamespace(snap_name=None),
        meta=SimpleNamespace(name="polkadot"),
    )

    payload = PolkadotCharm._build_machine_observability_payload(charm)

    assert payload.charm_name == "polkadot"
    assert payload.systemd_units == ["snap.polkadot.polkadot.service"]
