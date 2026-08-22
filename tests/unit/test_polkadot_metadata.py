import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from charms.dwellir.blockchain_common.v1 import CollectorCredentials

from polkadot_metadata import collect_upload_metadata


def test_collect_upload_metadata_does_not_log_collector_credentials(caplog):
    credentials = CollectorCredentials(
        bucket="metadata-bucket",
        region="eu-north-1",
        access_key_id="sensitive-access-key",
        secret_access_key="sensitive-secret-key",
        session_token="sensitive-session-token",
        endpoint_url="https://s3.example.invalid",
        key_prefix="metadata/",
    )
    workload = SimpleNamespace(
        get_binary_path=lambda: "/usr/local/bin/polkadot",
        get_proc_cmdline=lambda: "/usr/local/bin/polkadot --chain=polkadot",
    )
    charm = SimpleNamespace(
        model=SimpleNamespace(
            config={"collector-s3-credentials": "secret:collector"},
            name="polkadot-mainnet",
            uuid="model-uuid",
        ),
        config={},
        rpc_urls=lambda: {},
        _workload=workload,
        _get_workload_version=lambda: "1.0.0",
        app=SimpleNamespace(name="polkadot"),
        unit=SimpleNamespace(name="polkadot/0"),
        meta=SimpleNamespace(name="polkadot"),
    )
    rpc = SimpleNamespace(
        get_chain_name=lambda: "Polkadot",
        get_genesis_hash=lambda: "0x91b171bb",
    )

    with (
        caplog.at_level(logging.INFO, logger="polkadot_metadata"),
        patch("polkadot_metadata.parse_credentials_secret_id", return_value=credentials),
        patch("polkadot_metadata.ServiceArgs", return_value=SimpleNamespace(rpc_port=9933)),
        patch("polkadot_metadata.PolkadotRpcWrapper", return_value=rpc),
        patch("polkadot_metadata.collect_and_upload", return_value=Path("/tmp/metadata.json")),
    ):
        collect_upload_metadata(charm)

    assert "sensitive-access-key" not in caplog.text
    assert "sensitive-secret-key" not in caplog.text
    assert "sensitive-session-token" not in caplog.text
    assert "model=polkadot-mainnet" in caplog.text
    assert "app=polkadot" in caplog.text
    assert "unit=polkadot/0" in caplog.text
    assert "upload_enabled=True" in caplog.text
