"""Exercise runtime-derived key layouts using the real SCALE codec."""

from types import SimpleNamespace

import pytest

from session_keys import SessionKeyCodec


@pytest.mark.parametrize("runtime,size", [("relay", 192), ("matrix", 64)], indirect=["runtime"])
def test_enjin_session_keys_follow_captured_metadata(runtime, size):
    codec = SessionKeyCodec(runtime, runtime.block_hash)
    # Dict insertion order must not control SCALE field order.
    bundle = codec.encode(dict(reversed(list(runtime.keys.items()))))
    assert len(bytes.fromhex(bundle[2:])) == size
    assert codec.decode(bundle) == runtime.keys
    types = codec.key_types(bundle)
    assert types[-1] == ("offchain_worker", runtime.keys["offchain_worker"], "ofcw")


@pytest.mark.parametrize("runtime", ["relay", "matrix"], indirect=True)
def test_truncated_and_trailing_bundle_data_are_rejected(runtime):
    codec = SessionKeyCodec(runtime, runtime.block_hash)
    bundle = codec.encode(runtime.keys)
    for invalid in (bundle[:-2], bundle + "00"):
        with pytest.raises(ValueError):
            codec.decode(invalid)


@pytest.mark.parametrize(
    "fields",
    [
        [("grandpa", "[u8; 32]"), ("babe", "[u8; 32]"), ("para_validator", "[u8; 32]"), ("para_assignment", "[u8; 32]"), ("authority_discovery", "[u8; 32]"), ("beefy", "[u8; 33]")],
        [("aura", "[u8; 32]")],
    ],
)
def test_polkadot_layouts_and_33_byte_beefy_key_are_not_guessed_by_count(runtime, monkeypatch, fields):
    runtime.runtime_config.update_type_registry_types({"scale_info::999999": {"type": "struct", "type_mapping": fields}})
    monkeypatch.setattr(runtime, "get_metadata_call_function", lambda *args, **kwargs: SimpleNamespace(value={"fields": [{"name": "keys", "type": 999999}]}))
    keys = {name: "0x" + "ab" * (33 if name == "beefy" else 32) for name, _ in fields}
    codec = SessionKeyCodec(runtime, runtime.block_hash)
    assert codec.decode(codec.encode(keys)) == keys
    assert [(name, kt) for name, _, kt in codec.key_types(codec.encode(keys))] == [(name, runtime.key_types[name]) for name in keys]


def test_pre_scaleinfo_metadata_uses_named_keys_argument(runtime, monkeypatch):
    runtime.runtime_config.update_type_registry_types({"LegacySessionKeys": {"type": "struct", "type_mapping": [("aura", "[u8; 32]")]}})
    call = SimpleNamespace(value={}, args=[SimpleNamespace(name="keys", type="LegacySessionKeys")])
    monkeypatch.setattr(runtime, "get_metadata_call_function", lambda *args, **kwargs: call)
    codec = SessionKeyCodec(runtime, runtime.block_hash)
    assert codec.decode("0x" + "aa" * 32) == {"aura": "0x" + "aa" * 32}


def test_invalid_runtime_decode_is_not_treated_as_missing_keys(runtime, monkeypatch):
    codec = SessionKeyCodec(runtime, runtime.block_hash)
    bundle = codec.encode(runtime.keys)
    monkeypatch.setattr(runtime, "rpc_request", lambda *args: {"result": "0x00"})
    with pytest.raises(ValueError, match="incompatible"):
        codec.key_types(bundle)
