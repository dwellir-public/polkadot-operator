class PolkadotError(Exception):
    """Base exception for Polkadot workload errors."""
    pass


class InstallError(PolkadotError):
    """Raised when installation fails."""
    pass


class ServiceError(PolkadotError):
    """Raised when service operations fail."""
    pass
