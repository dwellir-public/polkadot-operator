from pathlib import Path
from types import SimpleNamespace

from core.utils import general_util


def test_get_process_cmdline_uses_binary_path_without_process_name(monkeypatch):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command == ["pgrep", "-f", "/home/moonbeam/polkadot"]:
            return SimpleNamespace(stdout=b"2342344\n")
        if command == "cat /proc/2342344/cmdline":
            return SimpleNamespace(stdout=b"/home/moonbeam/polkadot\x00--chain\x00moonbeam\x00")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(general_util.sp, "run", fake_run)

    assert general_util.get_process_cmdline(process_path=Path("/home/moonbeam/polkadot")) == "/home/moonbeam/polkadot --chain moonbeam "
    assert ["pgrep", "-x", "moonbeam"] not in commands


def test_get_process_cmdline_uses_first_matching_pid(monkeypatch):
    def fake_run(command, **kwargs):
        if command == ["pgrep", "-x", "polkadot"]:
            return SimpleNamespace(stdout=b"111\n222\n")
        if command == "cat /proc/111/cmdline":
            return SimpleNamespace(stdout=b"/snap/polkadot/69/bin/polkadot\x00--chain\x00polkadot\x00")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(general_util.sp, "run", fake_run)

    assert general_util.get_process_cmdline("polkadot") == "/snap/polkadot/69/bin/polkadot --chain polkadot "


def test_get_process_cmdline_falls_back_to_process_name_when_path_does_not_match(monkeypatch):
    def fake_run(command, **kwargs):
        if command == ["pgrep", "-f", "/snap/polkadot/current/bin/polkadot"]:
            return SimpleNamespace(stdout=b"")
        if command == ["pgrep", "-x", "polkadot"]:
            return SimpleNamespace(stdout=b"111\n")
        if command == "cat /proc/111/cmdline":
            return SimpleNamespace(stdout=b"/snap/polkadot/69/bin/polkadot\x00--chain\x00polkadot\x00")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(general_util.sp, "run", fake_run)

    assert general_util.get_process_cmdline("polkadot", Path("/snap/polkadot/current/bin/polkadot")) == "/snap/polkadot/69/bin/polkadot --chain polkadot "


def test_get_process_cmdline_returns_empty_when_no_process_matches(monkeypatch):
    def fake_run(command, **kwargs):
        if command == ["pgrep", "-f", "/home/moonbeam/polkadot"]:
            return SimpleNamespace(stdout=b"")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(general_util.sp, "run", fake_run)

    assert general_util.get_process_cmdline(process_path=Path("/home/moonbeam/polkadot")) == ""
