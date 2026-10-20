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
        access_key_id="AKIA-DO-NOT-LOG",
        secret_access_key="collector-secret-do-not-log",
        session_token="collector-session-do-not-log",
        endpoint_url="https://s3.example.invalid",
        key_prefix="metadata/",
    )
    workload = SimpleNamespace(
        get_binary_path=lambda: "/usr/bin/polkadot",
        get_proc_cmdline=lambda: "/usr/bin/polkadot --chain polkadot",
    )
    charm = SimpleNamespace(
        model=SimpleNamespace(
            config={"collector-s3-credentials": "secret:collector"},
            name="polkadot-mainnet",
        ),
        app=SimpleNamespace(name="polkadot"),
        unit=SimpleNamespace(name="polkadot/0"),
        meta=SimpleNamespace(name="polkadot"),
        config={},
        rpc_urls=lambda: [],
        _workload=workload,
        _get_workload_version=lambda: "1.2.3",
    )
    rpc = SimpleNamespace(
        get_chain_name=lambda: "Polkadot",
        get_genesis_hash=lambda: "0x" + "91" * 32,
    )

    with (
        caplog.at_level(logging.INFO, logger="polkadot_metadata"),
        patch("polkadot_metadata.parse_credentials_secret_id", return_value=credentials),
        patch("polkadot_metadata.ServiceArgs", return_value=SimpleNamespace(rpc_port="9933")),
        patch("polkadot_metadata.PolkadotRpcWrapper", return_value=rpc),
        patch("polkadot_metadata.collect_and_upload", return_value=Path("/tmp/metadata.json")),
    ):
        collect_upload_metadata(charm)

    assert "AKIA-DO-NOT-LOG" not in caplog.text
    assert "collector-secret-do-not-log" not in caplog.text
    assert "collector-session-do-not-log" not in caplog.text
    assert "model=polkadot-mainnet" in caplog.text
    assert "app=polkadot" in caplog.text
    assert "unit=polkadot/0" in caplog.text
    assert "upload_enabled=True" in caplog.text
    assert "metadata collection and upload complete" in caplog.text
