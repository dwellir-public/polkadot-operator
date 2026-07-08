from types import SimpleNamespace

from core import runtime as r
from core.managers.polkadot_snap import PolkadotSnapManager
from core.utils import binary_util


def test_snap_help_option_prefixed_with_collator_does_not_make_node_parachain(tmp_path, monkeypatch):
    manager = PolkadotSnapManager()
    manager._chain_db_dir = tmp_path / "chains"
    manager._relay_db_dir = tmp_path / "polkadot"
    manager._snap_config = {"cli_command": "polkadot.polkadot-cli"}
    manager._chain_db_dir.mkdir()
    manager._polkadot_snap = SimpleNamespace(present=True)

    def fake_run(command, **kwargs):
        if r'grep -i "\-\-collator"' in command:
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr("core.managers.polkadot_snap.sp.run", fake_run)

    assert manager.is_parachain_node() is False


def test_snap_help_standalone_collator_option_makes_node_parachain(tmp_path, monkeypatch):
    manager = PolkadotSnapManager()
    manager._chain_db_dir = tmp_path / "chains"
    manager._relay_db_dir = tmp_path / "polkadot"
    manager._snap_config = {"cli_command": "polkadot.polkadot-cli"}
    manager._chain_db_dir.mkdir()
    manager._polkadot_snap = SimpleNamespace(present=True)

    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("core.managers.polkadot_snap.sp.run", fake_run)

    assert manager.is_parachain_node() is True


def test_binary_help_option_prefixed_with_collator_does_not_make_node_parachain(tmp_path, monkeypatch):
    binary_file = tmp_path / "bin" / "polkadot"
    binary_file.parent.mkdir()
    binary_file.touch()
    chain_db_dir = tmp_path / "chains"
    relay_db_dir = tmp_path / "polkadot"
    chain_db_dir.mkdir()

    monkeypatch.setattr(r, "binary_file", binary_file)

    def fake_run(command, **kwargs):
        if r'grep -i "\-\-collator"' in command:
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(binary_util.sp, "run", fake_run)

    assert binary_util.is_parachain_node(chain_db_dir, relay_db_dir) is False


def test_binary_help_standalone_collator_option_makes_node_parachain(tmp_path, monkeypatch):
    binary_file = tmp_path / "bin" / "polkadot"
    binary_file.parent.mkdir()
    binary_file.touch()
    chain_db_dir = tmp_path / "chains"
    relay_db_dir = tmp_path / "polkadot"
    chain_db_dir.mkdir()

    monkeypatch.setattr(r, "binary_file", binary_file)

    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(binary_util.sp, "run", fake_run)

    assert binary_util.is_parachain_node(chain_db_dir, relay_db_dir) is True
