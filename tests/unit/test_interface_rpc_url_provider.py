from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from ops.charm import RelationJoinedEvent
from ops.model import ModelError

from interface_rpc_url_provider import RpcUrlProvider


def test_relation_joined_uses_ingress_address_when_network_binding_is_unavailable():
    unit = "polkadot/0"
    relation_data = {
        unit: {
            "egress-subnets": "192.168.109.82/32",
            "ingress-address": "192.168.109.82",
            "private-address": "192.168.109.82",
        }
    }
    event = cast(
        RelationJoinedEvent,
        SimpleNamespace(
            relation=SimpleNamespace(data=relation_data),
            defer=lambda: (_ for _ in ()).throw(AssertionError("relation event was deferred")),
        ),
    )

    def unavailable_binding(_relation_name):
        raise ModelError("no network config found for binding rpc_url")

    provider = cast(
        RpcUrlProvider,
        SimpleNamespace(
            _charm=SimpleNamespace(
                config={
                    "service-args": "--chain polkadot --rpc-port 9933",
                    "data-dir": "",
                    "chain-spec-url": "",
                    "local-relaychain-spec-url": "",
                    "wasm-runtime-url": "",
                    "docker-tag": "",
                    "binary-url": "",
                    "snap-name": "polkadot",
                }
            ),
            _relation_name="rpc_url",
            model=SimpleNamespace(unit=unit, get_binding=unavailable_binding),
        ),
    )
    workload = SimpleNamespace(get_client_binary_help_output=lambda: "--rpc-port <PORT>")

    with patch("interface_rpc_url_provider.WorkloadFactory.get_workload_manager", return_value=workload):
        RpcUrlProvider._on_relation_joined(provider, event)

    assert relation_data[unit] == {
        "egress-subnets": "192.168.109.82/32",
        "ingress-address": "192.168.109.82",
        "private-address": "192.168.109.82",
        "rpc_url": "http://192.168.109.82:9933",
        "ws_url": "ws://192.168.109.82:9933",
    }
