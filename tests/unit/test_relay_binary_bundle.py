"""Check the filenames produced by the multi-binary installer."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from core import runtime as r
from core.utils import binary_util


@pytest.mark.parametrize(
    "chain,upstream,worker_prefix",
    [
        ("mainnet", "zkv-relay", "zkv-relay"),
        ("polkadot", "polkadot", "polkadot"),
        ("enjin", "enjin-relaychain", "enjin"),
        ("canary", "enjin-relaychain", "enjin"),
        ("mainnet", "custom-relay", "polkadot"),
    ],
)
def test_relay_install_names(tmp_path, monkeypatch, chain, upstream, worker_prefix):
    worker_names = {
        "default": "polkadot",
        "enjin": "enjin",
        "canary": "enjin",
    }
    monkeypatch.setattr(r, "home_dir", tmp_path)
    monkeypatch.setattr(r, "binary_file", tmp_path / "polkadot")
    for role in ("execute", "prepare"):
        monkeypatch.setattr(
            r,
            f"{role}_worker_binary_file",
            {key: tmp_path / f"{name}-{role}-worker" for key, name in worker_names.items()},
        )
    monkeypatch.setattr(binary_util, "stop_service", Mock())
    monkeypatch.setattr(binary_util.sp, "run", Mock())
    monkeypatch.setattr(
        binary_util.requests,
        "get",
        lambda url, **_: Mock(status_code=200, content=Path(url).name.encode()),
    )
    source = [upstream, f"{upstream}-execute-worker", f"{upstream}-prepare-worker"]
    binary_util.install_binary(chain, " ".join(f"https://example.invalid/{name}" for name in source), "")
    expected = ["polkadot", f"{worker_prefix}-execute-worker", f"{worker_prefix}-prepare-worker"]
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == dict(zip(expected, map(str.encode, source), strict=True))
