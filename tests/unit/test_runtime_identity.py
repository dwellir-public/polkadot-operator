import hashlib
import inspect
from types import SimpleNamespace

from charms.operator_libs_linux.v2 import snap

from core import constants as c
from core.utils import binary_util


def test_constants_module_contains_no_functions():
    functions = [name for name, value in inspect.getmembers(c, inspect.isfunction) if getattr(value, "__module__", "") == c.__name__]

    assert functions == []


def test_runtime_identity_does_not_duplicate_base_snap_config():
    from core import runtime_identity

    assert not hasattr(runtime_identity, "BASE_SNAP_CONFIG")
    assert "polkadot" in c.DEFAULT_SNAP_CONFIG
    assert "polkadot-parachain" in c.DEFAULT_SNAP_CONFIG


def test_runtime_identity_uses_application_name_for_binary_resources(tmp_path, monkeypatch):
    from core import runtime_identity

    try:
        runtime_identity.configure_runtime_identity("foo-bar")
        service_template_path = tmp_path / "polkadot.service"
        service_template_path.write_text(
            """[Unit]
EnvironmentFile=-/etc/default/${service_name}
ExecStart=${binary_file} $$POLKADOT_CLI_ARGS
User=${user}
Group=${group}
""",
            encoding="utf-8",
        )
        installed_service_path = tmp_path / "foo-bar.service"
        real_path = binary_util.Path
        monkeypatch.setattr(
            binary_util,
            "Path",
            lambda *args: installed_service_path if args == ("/etc/systemd/system/foo-bar.service",) else real_path(*args),
        )
        monkeypatch.setattr(binary_util.sp, "run", lambda *args, **kwargs: None)

        assert c.USER == "foo-bar"
        assert c.SERVICE_NAME == "foo-bar"
        assert c.HOME_DIR.as_posix() == "/home/foo-bar"
        assert c.BASE_PATH.as_posix() == "/home/foo-bar/.local/share/polkadot"
        assert c.BINARY_FILE.as_posix() == "/home/foo-bar/polkadot"
        assert c.NODE_KEY_FILE.as_posix() == "/home/foo-bar/node-key"
        assert c.WASM_DIR.as_posix() == "/home/foo-bar/wasm"
        assert c.DOCKER_CONTAINER_NAME == "foo-bar-install-tmp"

        binary_util.install_service_file(service_template_path)
        service_file = installed_service_path.read_text(encoding="utf-8")
        assert "EnvironmentFile=-/etc/default/foo-bar" in service_file
        assert "ExecStart=/home/foo-bar/polkadot $POLKADOT_CLI_ARGS" in service_file
        assert "User=foo-bar" in service_file
        assert "Group=foo-bar" in service_file
    finally:
        runtime_identity.configure_runtime_identity("polkadot")


def test_runtime_identity_uses_sha1_snap_instance_key():
    from core import runtime_identity

    app_name = "foo-bar-and-something-more"
    instance_key = hashlib.sha1(app_name.encode("utf-8")).hexdigest()[:10]

    try:
        runtime_identity.configure_runtime_identity(app_name)

        assert c.SNAP_INSTANCE_KEY == instance_key
        assert c.SNAP_CONFIG["polkadot"]["snap_name"] == f"polkadot_{instance_key}"
        assert c.SNAP_CONFIG["polkadot"]["base_path"].as_posix() == f"/var/snap/polkadot_{instance_key}/common/polkadot_base"
        assert c.SNAP_CONFIG["polkadot"]["cli_command"] == f"polkadot_{instance_key}.polkadot-cli"
        assert c.SNAP_CONFIG["polkadot"]["systemd_service"] == f"snap.polkadot_{instance_key}.polkadot.service"
    finally:
        runtime_identity.configure_runtime_identity("polkadot")


def test_default_runtime_identity_keeps_non_parallel_snap_names():
    from core import runtime_identity

    try:
        runtime_identity.configure_runtime_identity("polkadot")

        assert c.SNAP_INSTANCE_KEY == ""
        assert c.SNAP_CONFIG["polkadot"]["snap_name"] == "polkadot"
        assert c.SNAP_CONFIG["polkadot"]["cli_command"] == "polkadot.polkadot-cli"
        assert c.SNAP_CONFIG["polkadot"]["systemd_service"] == "snap.polkadot.polkadot.service"
    finally:
        runtime_identity.configure_runtime_identity("polkadot")


def test_snap_manager_bootstraps_missing_parallel_instance_from_base_snap(monkeypatch):
    from core import runtime_identity
    from core.managers.polkadot_snap import PolkadotSnapManager

    class FakeSnapCache:
        def __getitem__(self, snap_name):
            if snap_name == "polkadot_db7329d5a3":
                raise snap.SnapNotFoundError("missing instance")
            if snap_name == "polkadot":
                return SimpleNamespace(
                    channel="latest/stable",
                    revision="123",
                    confinement="strict",
                )
            raise AssertionError(f"unexpected snap lookup: {snap_name}")

    try:
        runtime_identity.configure_runtime_identity("foo-bar")
        monkeypatch.setattr(snap, "SnapCache", FakeSnapCache)
        monkeypatch.setattr(PolkadotSnapManager, "_enable_parallel_instances", lambda self: None)

        manager = PolkadotSnapManager()
        manager.configure(snap_name="polkadot", data_dir="")

        assert manager._polkadot_snap.name == "polkadot_db7329d5a3"
        assert manager._polkadot_snap.state is snap.SnapState.Available
        assert manager._polkadot_snap.channel == "latest/stable"
        assert manager._polkadot_snap.revision == "123"
        assert manager._polkadot_snap.confinement == "strict"
    finally:
        runtime_identity.configure_runtime_identity("polkadot")
