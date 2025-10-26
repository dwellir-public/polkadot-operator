from core.managers.workload import WorkloadManager, WorkloadType
from core.managers.polkadot_binary import PolkadotBinaryManager
from core.managers.polkadot_snap import PolkadotSnapManager

class WorkloadFactory:
    BINARY_MANAGER = PolkadotBinaryManager()
    SNAP_MANAGER = PolkadotSnapManager()

    @staticmethod
    def get_workload_manager(type: WorkloadType) -> WorkloadManager:
        if type == WorkloadType.BINARY:
            return WorkloadFactory.BINARY_MANAGER
        elif type == WorkloadType.SNAP:
            return WorkloadFactory.SNAP_MANAGER
        else:
            raise ValueError(f"Unknown workload type: {type}")
