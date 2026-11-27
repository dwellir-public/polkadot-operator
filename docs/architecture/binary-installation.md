# Multi-binary installation

Space-separated raw binary URLs are handled by
[`binary_util.py`](../../src/core/utils/binary_util.py) in four stages:

1. `resolve_binary_targets` selects destinations without IO. Each `BinaryTarget`
   keeps the source URL, checksum URL, and destination path.
2. The installer downloads every binary and records its response, destination,
   and SHA256 in a `DownloadedBinary`. This named tuple preserves the interface
   consumed by checksum verification.
3. Configured checksums are verified before stopping the service. Verification
   is skipped when no checksum URLs are configured.
4. The service is stopped and the staged binaries are written with executable
   permissions. The calling lifecycle code handles restarting the service.

Naming policy belongs in the resolver. It recognizes the exact zkVerify relay
and two-worker bundle, independent of URL order and query strings. Other bundles
use the existing chain-specific worker paths or the default Polkadot paths;
the relay executable keeps the configured runtime binary path.

When adding a bundle, extend the resolver and the mapping tests in
[`test_relay_binary_bundle.py`](../../tests/unit/test_relay_binary_bundle.py).
Cover both matching and nonmatching bundles without changing download or write
orchestration.
