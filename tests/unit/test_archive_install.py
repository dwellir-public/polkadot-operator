"""Exercise archive installation through the shared library with real HTTP and tar."""

import functools
import hashlib
import io
import shutil
import tarfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock

import pytest
from charms.dwellir.blockchain_common.v1 import downloads

from core import runtime as r
from core.utils import binary_util


@pytest.fixture
def archive_server(tmp_path):
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(tmp_path)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield tmp_path, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def installation(tmp_path, monkeypatch):
    target = tmp_path / "installed" / "polkadot"
    target.parent.mkdir()
    target.write_bytes(b"old binary")
    stop = Mock()
    commands = []
    real_run = downloads.run_command

    def run(command, **kwargs):
        commands.append(command)
        if command[0] == "chown":
            return None
        return real_run(command, **kwargs)

    monkeypatch.setattr(r, "binary_file", target)
    monkeypatch.setattr(r, "user", "test-node")
    monkeypatch.setattr(binary_util, "stop_service", stop)
    monkeypatch.setattr(downloads, "run_command", run)
    return target, stop, commands


def make_archive(path, members, mode="w:gz"):
    with tarfile.open(path, mode) as archive:
        for name in members:
            member = tarfile.TarInfo(name)
            member.size = len(b"new binary")
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(b"new binary"))


@pytest.mark.parametrize(
    "chain,member,entries,suffix,mode",
    [
        ("using_chainspec_config", "humanode-peer", ["./humanode-peer"], ".tar.gz", "w:gz"),
        ("generic", "client", ["release/bin/client", "README"], ".tar.xz", "w:xz"),
        ("goldberg", "", ["data-avail"], ".tgz", "w:gz"),
        ("polkadot", "", ["bin/polkadot"], ".tar", "w"),
        ("generic", "bin/client", ["bin/client", "other/client"], ".tar.bz2", "w:bz2"),
    ],
)
def test_archive_install(archive_server, installation, chain, member, entries, suffix, mode):
    root, url = archive_server
    target, stop, commands = installation
    archive = root / f"release{suffix}"
    make_archive(archive, entries, mode)
    (root / "sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest())

    def before_stop():
        assert target.read_bytes() == b"old binary"
        assert any(command[0] == "tar" and "-tf" not in command for command in commands)

    stop.side_effect = before_stop
    binary_util.install_binary(chain, f"{url}/{archive.name}?download=1", f"{url}/sha256", member)

    assert target.read_bytes() == b"new binary"
    assert target.stat().st_mode & 0o111
    stop.assert_called_once_with()
    assert ["chown", "test-node:test-node", str(target)] in commands


@pytest.mark.parametrize("failure", ["missing", "ambiguous", "checksum", "corrupt"])
def test_invalid_archive_preserves_running_binary(archive_server, installation, failure):
    root, url = archive_server
    target, stop, _ = installation
    entries = ["other"] if failure == "missing" else ["bin/client", "other/client"] if failure == "ambiguous" else ["client"]
    archive = root / "release.tar.gz"
    make_archive(archive, entries)
    if failure == "corrupt":
        archive.write_bytes(b"not a tar archive")
    (root / "sha256").write_text("0" * 64)

    with pytest.raises(ValueError):
        binary_util.install_binary("generic", f"{url}/{archive.name}", f"{url}/sha256" if failure == "checksum" else None, "client")

    assert target.read_bytes() == b"old binary"
    stop.assert_not_called()


def test_multi_binary_urls_keep_existing_installer(monkeypatch):
    install = Mock()
    monkeypatch.setattr(binary_util, "install_binaries_from_urls", install)
    urls = "https://example.invalid/polkadot https://example.invalid/worker"
    binary_util.install_binary("polkadot", urls)
    install.assert_called_once_with(urls, None, "polkadot")


def test_real_humanode_archive(tmp_path, installation, monkeypatch):
    """Optionally check the previously downloaded upstream release without networking."""
    import os

    archive = os.environ.get("HUMANODE_TEST_ARCHIVE")
    if not archive:
        pytest.skip("set HUMANODE_TEST_ARCHIVE to an existing upstream tarball")
    target, stop, _ = installation
    monkeypatch.setattr(downloads, "download_file", lambda url, destination: shutil.copyfile(archive, destination))
    binary_util.install_binary("using_chainspec_config", "https://example.invalid/humanode.tar.gz", archive_member="humanode-peer")
    assert hashlib.sha256(target.read_bytes()).hexdigest() == "6640451317dab7111e191394e21f6c5a38e6c7c155cd6e359f37ca9284c70a84"
    stop.assert_called_once_with()


def test_binary_manager_passes_member_to_archive_installer(archive_server, installation, monkeypatch):
    from core.managers.polkadot_binary import PolkadotBinaryManager

    root, url = archive_server
    target, stop, _ = installation
    make_archive(root / "release.tar.gz", ["./humanode-peer"])
    monkeypatch.setattr(binary_util, "create_env_file_for_service", lambda: None)
    monkeypatch.setattr(binary_util, "install_service_file", lambda template: None)
    manager = PolkadotBinaryManager()
    manager.configure(
        binary_url=f"{url}/release.tar.gz",
        archive_member="humanode-peer",
        chain_name="using_chainspec_config",
        charm_base_dir=root,
    )

    manager.install()

    assert target.read_bytes() == b"new binary"
    stop.assert_called_once_with()
