# Enjin metadata fixtures

The gzip files contain public JSON-RPC metadata, runtime versions and finalized
header/hash snapshots captured on 2026-11-17 from local Enjin node RPCs.
The Relaychain fixture has spec version 1080 / transaction version 19; the
Matrixchain fixture has spec version 1043 / transaction version 16.

They contain no private keys or credentials. Gzip timestamps are zero for
reproducibility. The offline test fixture loads these bytes into the real
substrate-interface 1.8.1 metadata and SCALE codecs. Storage queries, key
possession, the runtime key-decoder RPC and submission are simulated explicitly;
the fixtures are not evidence of transaction acceptance by a live chain.
