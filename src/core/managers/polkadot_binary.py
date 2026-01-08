from pathlib import Path
from .workload import WorkloadManager, WorkloadType
from core.utils import binary_util, download_util
from core.utils import general_util
from core import constants as c

class PolkadotBinaryManager(WorkloadManager):

    def __init__(self):
        super().__init__(WorkloadType.BINARY)

    def configure(self, **kwargs):
        self._chain_name = kwargs.get('chain_name')
        self._binary_url = kwargs.get('binary_url')
        self._binary_sha256_url = kwargs.get('binary_sha256_url')
        self._docker_tag = kwargs.get('docker_tag')
        self._service_template_path = Path(kwargs.get('charm_base_dir'), 'templates/etc/systemd/system/polkadot.service')

    def install(self):
        if not self._binary_url and not self._docker_tag:
            raise ValueError("Either 'binary_url' or 'docker_tag' must be provided for binary installation.")
        if self._binary_url:
            binary_util.install_binary(self._chain_name, self._binary_url, self._binary_sha256_url)
        else:
            binary_util.install_binary_from_docker_container(self._chain_name, self._docker_tag)
        binary_util.create_env_file_for_service()
        binary_util.install_service_file(self._service_template_path)
    
    def uninstall(self):
        binary_util.uninstall_binary()

    def start_service(self):
        return binary_util.start_service()

    def stop_service(self):
        return binary_util.stop_service()

    def restart_service(self):
        return binary_util.restart_service()

    def is_service_running(self, iterations=1) -> bool:
        return self.is_service_started(iterations)

    def is_service_installed(self) -> bool:
        return binary_util.is_installed()
    
    def is_service_started(self, iterations):
        return binary_util.service_started(iterations)

    def upgrade_service(self):
        is_running = False
        if self.is_service_installed() and self.is_service_running():
            is_running = True
            self.stop_service()
        self.install()
        if is_running:
            self.start_service()

    def service_args_differ_from_disk(self, argument_string: str) -> bool:
        return binary_util.arguments_differ_from_disk(argument_string)

    def get_client_binary_help_output(self) -> str:
        return binary_util.get_client_binary_help_output()

    def generate_node_key(self) -> None:
        binary_util.generate_node_key()

    def download_wasm_runtime(self, url: str) -> None:
        download_util.download_wasm_runtime(url, c.WASM_DIR, c.USER)

    def get_binary_version(self) -> str:
        return binary_util.get_binary_version()

    def get_chain_disk_usage(self) -> str:
        return binary_util.get_chain_disk_usage()

    def get_relay_disk_usage(self) -> str:
        return binary_util.get_relay_disk_usage()
    
    def get_service_args(self) -> str:
        return binary_util.get_service_args()

    def get_wasm_info(self):
        return general_util.get_wasm_info(c.WASM_DIR)

    def set_service_args(self, service_args: str) -> None:
        return binary_util.update_service_args(service_args)

    def get_service_version(self) -> str:
        return binary_util.get_binary_version()

    def get_binary_md5sum(self) -> str:
        return binary_util.get_binary_md5sum()

    def get_binary_last_changed(self) -> str:
        return binary_util.get_binary_last_changed()

    def get_proc_cmdline(self) -> str:
        return general_util.get_process_cmdline(c.USER)

    def is_relay_chain_node(self) -> bool:
        return binary_util.is_relay_chain_node()
    
    def is_parachain_node(self) -> bool:
        return binary_util.is_parachain_node()
    
    def write_node_key_file(self, key) -> None:
        general_util.write_node_key_file(c.NODE_KEY_FILE, key, c.USER)

    def get_relay_for_parachain(self):
        return binary_util.get_relay_for_parachain()
    
    def get_binary_path(self) -> str:
        return binary_util.get_binary_path()
