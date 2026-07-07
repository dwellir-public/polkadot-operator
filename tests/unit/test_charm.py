# Copyright 2021 dwellir
# See LICENSE file for licensing details.

import sys
import types
from types import SimpleNamespace

substrateinterface = types.ModuleType("substrateinterface")
substrateinterface.SubstrateInterface = object
substrateinterface.Keypair = object
sys.modules.setdefault("substrateinterface", substrateinterface)

from charms.dwellir_observability.v0.machine_observability import (  # noqa: E402
    MACHINE_OBSERVABILITY_SCHEMA_VERSION_V1,
    MACHINE_OBSERVABILITY_SCHEMA_VERSION_V2,
    MachineObservabilityPayload,
    SourceTopology,
    build_machine_observability_payload,
)

from charm import PolkadotCharm  # noqa: E402
from core.managers import WorkloadType  # noqa: E402
from core.service_args import ServiceArgs  # noqa: E402


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
    assert payload.schema_version == MACHINE_OBSERVABILITY_SCHEMA_VERSION_V1
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
        "source_topology": None,
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


def test_machine_observability_payload_serializes_custom_metrics_port():
    payload = build_machine_observability_payload(
        service_name="snap.polkadot.polkadot.service",
        charm_name="polkadot",
        metrics_port="19615",
    )

    assert payload.metrics_endpoints[0].targets == ["localhost:19615"]


def test_machine_observability_payload_serializes_to_v2_relation_shape():
    payload = build_machine_observability_payload(
        service_name="snap.polkadot.polkadot.service",
        charm_name="polkadot",
        source_topology=SourceTopology(
            model="alloy-sub-e2e-20260419",
            model_uuid="uuid-1",
            application="polkadot",
            unit="polkadot/0",
            charm_name="polkadot",
        ),
    )

    assert payload.model_dump(mode="json") == {
        "schema_version": MACHINE_OBSERVABILITY_SCHEMA_VERSION_V2,
        "charm_name": "polkadot",
        "source_topology": {
            "model": "alloy-sub-e2e-20260419",
            "model_uuid": "uuid-1",
            "application": "polkadot",
            "unit": "polkadot/0",
            "charm_name": "polkadot",
        },
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
            "service-args": "",
            "snap-name": "",
        },
        _stored=SimpleNamespace(snap_name=None),
        meta=SimpleNamespace(name="polkadot"),
        app=SimpleNamespace(name="polkadot"),
        unit=SimpleNamespace(name="polkadot/0"),
        model=SimpleNamespace(name="alloy-sub-e2e-20260419", uuid="uuid-1"),
        machine_observability_provider=SimpleNamespace(publish=lambda payload: published.update(payload)),
    )
    charm._source_topology = lambda: PolkadotCharm._source_topology(charm)
    charm._build_machine_observability_payload = lambda: PolkadotCharm._build_machine_observability_payload(charm)

    PolkadotCharm._publish_machine_observability(charm)

    assert published["charm_name"] == "polkadot"
    assert published["source_topology"].application == "polkadot"
    assert published["systemd_units"] == ["polkadot.service"]


def test_publish_machine_observability_uses_snap_service_name_when_snap_configured():
    published = {}

    charm = SimpleNamespace(
        config={
            "service-args": "",
            "snap-name": "polkadot",
        },
        _stored=SimpleNamespace(snap_name=None),
        meta=SimpleNamespace(name="polkadot"),
        app=SimpleNamespace(name="polkadot"),
        unit=SimpleNamespace(name="polkadot/0"),
        model=SimpleNamespace(name="alloy-sub-e2e-20260419", uuid="uuid-1"),
        machine_observability_provider=SimpleNamespace(publish=lambda payload: published.update(payload)),
    )
    charm._source_topology = lambda: PolkadotCharm._source_topology(charm)
    charm._build_machine_observability_payload = lambda: PolkadotCharm._build_machine_observability_payload(charm)

    PolkadotCharm._publish_machine_observability(charm)

    assert published["systemd_units"] == ["snap.polkadot.polkadot.service"]


def test_build_machine_observability_payload_uses_snap_service_name_when_configured():
    charm = SimpleNamespace(
        config={"service-args": "", "snap-name": "polkadot"},
        _stored=SimpleNamespace(snap_name=None),
        meta=SimpleNamespace(name="polkadot"),
        app=SimpleNamespace(name="polkadot"),
        unit=SimpleNamespace(name="polkadot/0"),
        model=SimpleNamespace(name="alloy-sub-e2e-20260419", uuid="uuid-1"),
    )
    charm._source_topology = lambda: PolkadotCharm._source_topology(charm)

    payload = PolkadotCharm._build_machine_observability_payload(charm)

    assert payload.charm_name == "polkadot"
    assert payload.schema_version == MACHINE_OBSERVABILITY_SCHEMA_VERSION_V2
    assert payload.source_topology is not None
    assert payload.source_topology.application == "polkadot"
    assert payload.source_topology.unit == "polkadot/0"
    assert payload.systemd_units == ["snap.polkadot.polkadot.service"]


def test_build_machine_observability_payload_uses_snap_instance_name_when_configured():
    charm = SimpleNamespace(
        app=SimpleNamespace(name="foo-bar"),
        config={
            "service-args": "--chain polkadot --rpc-port 9933 --prometheus-port 19615",
            "snap-name": "polkadot",
        },
        _stored=SimpleNamespace(snap_name=None),
        meta=SimpleNamespace(name="polkadot"),
        model=SimpleNamespace(name="test-model", uuid="test-uuid"),
        unit=SimpleNamespace(name="foo-bar/0"),
    )
    charm._source_topology = lambda: PolkadotCharm._source_topology(charm)

    payload = PolkadotCharm._build_machine_observability_payload(charm)

    assert payload.systemd_units == ["snap.polkadot_db7329d5a3.polkadot.service"]
    assert payload.source_topology.application == "foo-bar"
    assert payload.metrics_endpoints[0].targets == ["localhost:19615"]


def test_prometheus_port():
    cases = [
        ("--chain polkadot --rpc-port 9933", "9615"),
        ("--chain polkadot --rpc-port 9933 --prometheus-port 19615", "19615"),
        ("--chain=polkadot --rpc-port=9933 --prometheus-port=19616", "19616"),
    ]

    for service_args, expected in cases:
        config = {
            "service-args": service_args,
            "data-dir": "",
            "chain-spec-url": "",
            "local-relaychain-spec-url": "",
            "wasm-runtime-url": "",
            "docker-tag": "",
            "binary-url": "",
            "snap-name": "polkadot",
        }
        assert ServiceArgs(config, {}).prometheus_port == expected


def test_config_changed_noops_without_restarting_running_workload_when_config_unchanged():
    config = {
        "binary-url": "",
        "binary-sha256-url": "",
        "docker-tag": "",
        "service-args": "--chain polkadot --rpc-port 9933",
        "data-dir": "",
        "chain-spec-url": "",
        "local-relaychain-spec-url": "",
        "wasm-runtime-url": "",
        "snap-revision": "123",
        "snap-channel": "latest/stable",
        "snap-hold": False,
        "snap-endure": False,
        "snap-name": "polkadot",
    }

    class FakeWorkload:
        def __init__(self):
            self.restart_calls = 0
            self.start_calls = 0
            self.set_service_args_calls = 0

        def get_type(self):
            return WorkloadType.SNAP

        def is_service_running(self, iterations=1):
            return True

        def is_service_started(self, iterations):
            return True

        def service_args_differ_from_disk(self, argument_string):
            return False

        def set_service_args(self, service_args):
            self.set_service_args_calls += 1

        def restart_service(self):
            self.restart_calls += 1

        def start_service(self):
            self.start_calls += 1

        def get_binary_version(self):
            return "1.0.0"

    workload = FakeWorkload()
    stored = SimpleNamespace(
        binary_url=config["binary-url"],
        docker_tag=config["docker-tag"],
        service_args=config["service-args"],
        data_dir=config["data-dir"],
        chain_spec_url=config["chain-spec-url"],
        local_relaychain_spec_url=config["local-relaychain-spec-url"],
        wasm_runtime_url=config["wasm-runtime-url"],
        snap_revision=config["snap-revision"],
        snap_channel=config["snap-channel"],
        snap_hold=config["snap-hold"],
        snap_endure=config["snap-endure"],
        snap_name=config["snap-name"],
        service_init=False,
    )
    unit = SimpleNamespace(
        status=None,
        set_workload_version=lambda version: None,
    )
    charm = SimpleNamespace(
        config=config,
        _stored=stored,
        _workload=workload,
        unit=unit,
        rpc_urls=lambda: [],
        _refresh_advertised_ports=lambda metrics_port: None,
        _publish_machine_observability=lambda: None,
        update_status_simple=lambda: PolkadotCharm.update_status_simple(charm),
        _has_valid_client_config=lambda: PolkadotCharm._has_valid_client_config(charm),
        _get_client_type=lambda: "snap",
        _get_workload_version=lambda: workload.get_binary_version(),
    )
    event = SimpleNamespace(deferred=False, defer=lambda: setattr(event, "deferred", True))

    PolkadotCharm._on_config_changed(charm, event)

    assert event.deferred is False
    assert workload.set_service_args_calls == 0
    assert workload.restart_calls == 0
    assert workload.start_calls == 0
