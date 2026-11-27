"""Exercise multi-binary verification before replacing installed binaries."""

import hashlib
from unittest.mock import Mock
from urllib.parse import urlsplit

import pytest

from core import runtime as r
from core.utils import binary_util


@pytest.mark.parametrize("upstream,chain", [("polkadot", "polkadot"), ("enjin-relaychain", "enjin")])
@pytest.mark.parametrize("marker", ["", "*"])
@pytest.mark.parametrize("failure", [None, "missing", "mismatch"])
def test_bundle_manifest_uses_source_names(tmp_path, monkeypatch, upstream, chain, marker, failure):
    source_names = [upstream, f"{upstream}-execute-worker", f"{upstream}-prepare-worker"]
    worker_prefix = "enjin" if chain == "enjin" else "polkadot"
    targets = [tmp_path / "polkadot", tmp_path / f"{worker_prefix}-execute-worker", tmp_path / f"{worker_prefix}-prepare-worker"]
    monkeypatch.setattr(r, "home_dir", tmp_path)
    monkeypatch.setattr(r, "binary_file", targets[0])
    monkeypatch.setattr(r, "execute_worker_binary_file", {"default": targets[1], chain: targets[1]})
    monkeypatch.setattr(r, "prepare_worker_binary_file", {"default": targets[2], chain: targets[2]})
    for target in targets:
        target.write_bytes(b"old binary")

    manifest = []
    for index, name in enumerate(source_names):
        digest = hashlib.sha256(name.encode()).hexdigest()
        if index == 2:
            if failure == "missing":
                continue
            if failure == "mismatch":
                digest = "0" * 64
        manifest.append(f"{digest}  {marker}{name}")

    def get(url, **kwargs):
        name = urlsplit(url).path.rsplit("/", 1)[-1]
        content = "\n".join(manifest).encode() if name == "SHA256SUMS" else name.encode()
        return Mock(status_code=200, content=content, text=content.decode())

    monkeypatch.setattr(binary_util.requests, "get", get)
    monkeypatch.setattr(binary_util.sp, "run", Mock())

    def before_stop():
        assert all(target.read_bytes() == b"old binary" for target in targets)

    stop = Mock(side_effect=before_stop)
    monkeypatch.setattr(binary_util, "stop_service", stop)
    urls = " ".join(f"https://example.invalid/{name}?download=1" for name in source_names)
    checksum_url = "https://example.invalid/SHA256SUMS"
    if failure:
        with pytest.raises(ValueError, match="Could not find target hash" if failure == "missing" else "wrong hash"):
            binary_util.install_binary(chain, urls, checksum_url)
        stop.assert_not_called()
        assert all(target.read_bytes() == b"old binary" for target in targets)
    else:
        binary_util.install_binary(chain, urls, checksum_url)
        stop.assert_called_once_with()
        assert [target.read_bytes() for target in targets] == [name.encode() for name in source_names]
