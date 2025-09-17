from enum import Enum

from abc import ABC, abstractmethod


class WorkloadType(Enum):
    BINARY = 'binary'
    SNAP = 'snap'

class WorkloadManager(ABC):
    def __init__(self, type: WorkloadType):
        self.type = type

    def get_type(self) -> WorkloadType:
        return self.type

    @abstractmethod
    def install(self, **kwargs) -> None:
        """Installing a new version of the workload would involve downloading the latest
        version, verifying its integrity, and replacing the old version with the new one.
        The service is stopped during this process and would require the caller to restart it afterwards.
        """
        pass

    @abstractmethod
    def start_service(self):
        pass

    @abstractmethod
    def stop_service(self):
        pass

    @abstractmethod
    def restart_service(self):
        pass

    @abstractmethod
    def is_service_installed(self) -> bool:
        pass

    @abstractmethod
    def get_service_args(self) -> str:
        pass

    @abstractmethod
    def set_service_args(self, args: str):
        pass

    @abstractmethod
    def is_service_running(self, iterations=1) -> bool:
        pass

    @abstractmethod
    def get_service_version(self) -> str:
        pass

    @abstractmethod
    def get_client_binary_help_output() -> str:
        pass

    @abstractmethod
    def get_wasm_info() -> str:
        pass

    @abstractmethod
    def service_args_differ_from_disk(self, argument_string: str) -> bool:
        pass

    @abstractmethod
    def generate_node_key(self) -> None:
        pass

    @abstractmethod
    def configure(self, **kwargs) -> None:
        pass

    @abstractmethod
    def download_wasm_runtime(self, url: str) -> None:
        pass

    @abstractmethod
    def get_binary_version(self) -> str:
        pass

    @abstractmethod
    def is_service_started(self, iterations: int) -> bool:
        pass

    @abstractmethod
    def get_chain_disk_usage(self) -> str:
        pass

    @abstractmethod
    def get_relay_disk_usage(self) -> str:
        pass

    @abstractmethod
    def get_binary_last_changed(self) -> str:
        return None

    @abstractmethod
    def get_binary_md5sum(self) -> str:
        return None
    
    @abstractmethod
    def get_proc_cmdline(self) -> str:
        return None

    @abstractmethod
    def is_relay_chain_node(self) -> bool:
        pass

    @abstractmethod
    def is_parachain_node(self) -> bool:
        pass

    @abstractmethod
    def write_node_key_file(self, key) -> None:
        pass

    @abstractmethod
    def get_relay_for_parachain(self):
        pass
