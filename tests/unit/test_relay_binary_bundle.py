"""Check the filenames produced by the multi-binary installer."""

import hashlib
from itertools import permutations
from unittest.mock import Mock
from urllib.parse import urlsplit

import pytest

from core import runtime as r
from core.utils import binary_util


@pytest.fixture
def installation(tmp_path, monkeypatch):
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
        lambda url, **_: Mock(status_code=200, content=urlsplit(url).path.rsplit("/", 1)[-1].encode()),
    )
    return tmp_path


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
@pytest.mark.parametrize("query", ["", "?download=1"])
def test_relay_install_names(installation, chain, upstream, worker_prefix, query):
    source = [upstream, f"{upstream}-execute-worker", f"{upstream}-prepare-worker"]
    binary_util.install_binary(chain, " ".join(f"https://example.invalid/{name}{query}" for name in source), "")
    expected = ["polkadot", f"{worker_prefix}-execute-worker", f"{worker_prefix}-prepare-worker"]
    assert {p.name: p.read_bytes() for p in installation.iterdir()} == dict(zip(expected, map(str.encode, source), strict=True))


@pytest.mark.parametrize("source", list(permutations(["zkv-relay", "zkv-relay-execute-worker", "zkv-relay-prepare-worker"])))
def test_zkverify_bundle_order(installation, source):
    binary_util.install_binary("mainnet", " ".join(f"https://example.invalid/{name}" for name in source), "")
    assert {p.name: p.read_bytes() for p in installation.iterdir()} == {
        "polkadot": b"zkv-relay",
        "zkv-relay-execute-worker": b"zkv-relay-execute-worker",
        "zkv-relay-prepare-worker": b"zkv-relay-prepare-worker",
    }


@pytest.mark.parametrize(
    "source",
    [
        ["zkv-relay", "zkv-relay-execute-worker"],
        ["zkv-relay-execute-worker", "zkv-relay-prepare-worker"],
        ["zkv-relay", "zkv-relay-execute-worker", "zkv-relay-execute-worker"],
        ["zkv-relay", "zkv-relay-execute-worker", "zkv-relay-prepare-worker", "extra"],
    ],
)
def test_non_exact_zkverify_bundle_keeps_default_mapping(installation, source):
    pairs = [(f"https://example.invalid/{name}?download=1", f"https://example.invalid/{name}.sha256") for name in source]
    targets = binary_util.resolve_binary_targets(pairs, "mainnet")
    expected = {
        "zkv-relay-execute-worker": "polkadot-execute-worker",
        "zkv-relay-prepare-worker": "polkadot-prepare-worker",
    }
    assert [(target.url, target.checksum_url, target.target_path) for target in targets] == [
        (url, checksum_url, installation / expected.get(name, "polkadot")) for (url, checksum_url), name in zip(pairs, source, strict=True)
    ]


@pytest.mark.parametrize("failure", [None, "download", "checksum"])
def test_bundle_staged_before_service_stop(installation, monkeypatch, failure):
    source = ["zkv-relay", "zkv-relay-execute-worker", "zkv-relay-prepare-worker"]
    installed = [installation / "polkadot", installation / source[1], installation / source[2]]
    for target in installed:
        target.write_bytes(b"old binary")
    requested = []

    def get(url, **kwargs):
        requested.append(url)
        name = urlsplit(url).path.rsplit("/", 1)[-1]
        if name.endswith(".sha256"):
            digest = hashlib.sha256(name.removesuffix(".sha256").encode()).hexdigest()
            if failure == "checksum" and name.startswith(source[-1]):
                digest = "0" * 64
            return Mock(content=digest.encode(), text=digest)
        return Mock(status_code=500 if failure == "download" and name == source[-1] else 200, content=name.encode(), text="download failed")

    def before_stop():
        assert len(requested) == 6
        assert all(target.read_bytes() == b"old binary" for target in installed)

    stop = Mock(side_effect=before_stop)
    monkeypatch.setattr(binary_util, "stop_service", stop)
    monkeypatch.setattr(binary_util.requests, "get", get)
    urls = " ".join(f"https://example.invalid/{name}" for name in source)
    checksums = " ".join(f"https://example.invalid/{name}.sha256" for name in source)
    if failure:
        with pytest.raises(ValueError, match="Download binary failed" if failure == "download" else "wrong hash"):
            binary_util.install_binary("mainnet", urls, checksums)
        stop.assert_not_called()
        assert all(target.read_bytes() == b"old binary" for target in installed)
    else:
        binary_util.install_binary("mainnet", urls, checksums)
        stop.assert_called_once_with()
        assert [target.read_bytes() for target in installed] == [name.encode() for name in source]
