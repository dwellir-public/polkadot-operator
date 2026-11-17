# Validator and session-key checks

`Validating: Yes` means the node holds a public/private key pair in the current
finalized BABE or Aura authority set. It does not establish recent accepted block
production, complete consensus readiness, or staking rewards. Continue to use
canonical block-author monitoring for those production checks.

`Validating: No` means no current authority key matched the local keystore.
`Validating: Unknown` means the check failed or the runtime's consensus mechanism
is unsupported. BABE/Aura authority lists must align with `Session.Validators`;
an incompatible list is an unknown check, not a negative result.

## Enjin and auxiliary keys

The live Enjin runtimes inspected on 2026-11-17 have these layouts:

- Relaychain spec 1080: grandpa, babe, para_validator, para_assignment,
  authority_discovery, offchain_worker.
- Matrixchain spec 1043: aura, offchain_worker.

A node can hold its active BABE/Aura key while lacking an offchain-worker key.
The charm reports current authority membership independently. When the same
consensus key is present in the queued bundle, it also reports missing queued
keys, for example `Validating: Yes, queued keys missing: offchain_worker`.
Missing auxiliary keys can affect separate services and need investigation.

Queued keys can already target another node during a rotation. The charm does
not attribute that incoming bundle's readiness to the outgoing current node.
If an auxiliary readiness check fails after a current key is found, status
retains `Validating: Yes` and reports `queued key readiness: Unknown`.

## Read-only actions

```bash
juju run polkadot/0 find-validator-address
juju run polkadot/0 is-validating-next-era address=<validator-address>
juju run polkadot/0 has-session-key key=<complete-hex-bundle>
```

`find-validator-address` returns `validator-address`, `authority-key` and
`key-type`. It returns `session-key` and `queued-missing-keys` only when the
queued bundle still uses the current consensus key. That bundle describes the
next session, not necessarily the current keys. If readiness could not be
checked, `queued-key-readiness` is `unknown`.

`is-validating-next-era` retains its existing action name for compatibility.
It now reports `registered`, `all-keys-present`, `missing-keys` and
`session-key`. `registered` means `Session.NextKeys` exists for the account.
It does not establish selection for a future session or staking era. A missing
registration returns `registered: false` without a bundle.

`has-session-key` uses `author_hasSessionKeys` and checks the entire supplied
bundle, including auxiliary keys. Its result must not be interpreted as current
participation. Individual keys require `author_hasKey(public_key, key_type)`.
RPC errors fail these actions explicitly; they are not reported as missing keys.

## Mutating actions

`get-session-key` and `get-session-key-with-owner` generate new local keys;
they are not read-only checks. `start-validating` generates keys and submits
`Session.set_keys`, optionally through the configured proxy. It first checks
SessionKeys metadata, the runtime key decoder and (for Enjin) signing-extension
compatibility using an existing queued bundle. Unsupported layouts fail before
rotation. A runtime with no queued key sample cannot pass that preflight.

The layout and field order come from `Session.set_keys` metadata; key-type IDs
come from `SessionKeys_decode_session_keys`. This supports variable-size keys,
including a 33-byte BEEFY key, without guessing names or lengths from a chain
name. The submitted bundle is decoded as a whole; trailing/truncated data fails.

Where advertised, `author_rotateKeysWithOwner` provides the owner-bound proof.
For proxies the owner is the real validator account. Older nodes fall back to
`author_rotateKeys` with proof `0x00`; runtime transaction acceptance still needs
validation in a test environment. Enjin signing preserves its custom extension
order and rejects unsupported nonempty extensions before generating keys.

Registration requires a funded signer. It does not bond funds, call
`Staking.validate`, obtain election, register a collator candidate, or change
service arguments. Those prerequisites and activation must be checked separately.

`insert-key` accepts an optional four-character `key-type`, defaulting to `aura`
for compatibility. Examples include `babe`, `gran` and Enjin's `ofcw`. It reports
RPC failures. Do not insert consensus signing keys on multiple active nodes.

## Validation and rollout

Unit tests use compressed public runtime metadata captured from Enjin on
2026-11-17. They exercise real SCALE codecs, owner/proxy registration and local
signature verification against the recorded extension order. They do not submit
transactions or prove live runtime acceptance of key registration.

Run `uv run --group dev tox -e lint,unit`. Before rolling out a repaired action,
verify registration/signing in an explicitly selected nonproduction model. After
a charm refresh, compare fresh status/actions with current authorities and
canonical production. No production keys need to be rotated to verify the status
fix. Fleet inventory, missing offchain keys and inaccessible models require
separate operational follow-up.
