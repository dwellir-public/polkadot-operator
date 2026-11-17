from hashlib import blake2b

import pytest
from scalecodec.base import ScaleBytes
from substrateinterface import Keypair
from substrateinterface.exceptions import SubstrateRequestException

import polkadot_rpc_wrapper
from polkadot_rpc_wrapper import PolkadotRpcWrapper
from session_keys import SessionKeyCodec

TEST_MNEMONIC = "bottom drive obey lake curtain smoke basket hold race lonely fit walk"


@pytest.fixture
def wrapper(runtime, monkeypatch):
    instance = PolkadotRpcWrapper("9933")
    instance.recorded_rpc = []
    instance.owner_rotation = True

    def rpc(method, params=None):
        params = params or []
        instance.recorded_rpc.append((method, params))
        if method == "author_hasKey":
            return tuple(params) in runtime.local_keys
        if method == "rpc_methods":
            return {"methods": ["author_rotateKeysWithOwner"] if instance.owner_rotation else []}
        if method in ("author_rotateKeys", "author_rotateKeysWithOwner"):
            bundle = SessionKeyCodec(runtime, runtime.block_hash).encode(runtime.keys)
            return {"keys": bundle, "proof": "0x1234"} if method.endswith("WithOwner") else bundle
        if method == "system_chain":
            return runtime.chain_name
        raise AssertionError(method)

    monkeypatch.setattr(instance, "_rpc", rpc)
    monkeypatch.setattr(polkadot_rpc_wrapper, "SubstrateInterface", lambda **kwargs: runtime)
    return instance


@pytest.mark.parametrize("runtime", ["relay", "matrix"], indirect=True)
def test_current_authority_is_found_when_offchain_key_is_missing(runtime, wrapper):
    runtime.local_keys = {key for key in runtime.local_keys if key[1] != "ofcw"}
    result = wrapper.is_validating_this_era()
    assert result["validator"] == runtime.address
    assert result["key_type"] == ("babe" if runtime.kind == "relay" else "aura")
    assert result["missing_keys"] == ["offchain_worker"]
    assert runtime.closed
    assert all(call[3] == runtime.block_hash for call in runtime.query_calls)


@pytest.mark.parametrize("runtime", ["relay", "matrix"], indirect=True)
def test_current_authority_does_not_depend_on_incoming_queued_keys(runtime, wrapper):
    keys = dict(runtime.keys)
    field = "babe" if runtime.kind == "relay" else "aura"
    keys[field] = "0x" + "99" * 32
    runtime.storage[("Session", "QueuedKeys")] = [[runtime.address, keys]]
    result = wrapper.is_validating_this_era()
    assert result["authority_key"] == runtime.keys[field]
    assert "session_key" not in result
    assert "missing_keys" not in result


@pytest.mark.parametrize("runtime", ["relay", "matrix"], indirect=True)
def test_incoming_node_is_not_reported_as_current_authority(runtime, wrapper):
    field = "babe" if runtime.kind == "relay" else "aura"
    runtime.local_keys = {("0x" + "99" * 32, runtime.key_types[field])}
    incoming = dict(runtime.keys, **{field: "0x" + "99" * 32})
    runtime.storage[("Session", "QueuedKeys")] = [[runtime.address, incoming]]
    assert wrapper.is_validating_this_era() is False


def test_unalignable_authorities_fail_instead_of_claiming_no_validation(runtime, wrapper):
    runtime.storage[("Session", "Validators")] = []
    with pytest.raises(ValueError, match="aligned"):
        wrapper.is_validating_this_era()
    assert runtime.closed


def test_unsupported_consensus_fails_explicitly(runtime, wrapper, monkeypatch):
    monkeypatch.setattr(runtime, "get_metadata_storage_function", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="no supported"):
        wrapper.is_validating_this_era()


def test_readiness_failure_preserves_current_authority_result(runtime, wrapper, monkeypatch):
    monkeypatch.setattr(wrapper, "_key_readiness", lambda *args: (_ for _ in ()).throw(ValueError("runtime failure")))
    result = wrapper.is_validating_this_era()
    assert result["validator"] == runtime.address
    assert result["readiness_unknown"]


@pytest.mark.parametrize("runtime", ["relay", "matrix"], indirect=True)
def test_registered_keys_report_missing_auxiliary_key_without_promising_election(runtime, wrapper):
    runtime.local_keys = {key for key in runtime.local_keys if key[1] != "ofcw"}
    runtime.storage[("Session", "Validators")] = []
    result = wrapper.is_validating_next_era(runtime.address)
    assert result["missing_keys"] == ["offchain_worker"]
    assert result["session_key"] == SessionKeyCodec(runtime, runtime.block_hash).encode(runtime.keys)


def test_unregistered_account_has_no_readiness(runtime, wrapper):
    runtime.storage[("Session", "NextKeys")] = None
    assert wrapper.is_validating_next_era(runtime.address) is None


@pytest.mark.parametrize("runtime", ["relay", "matrix"], indirect=True)
@pytest.mark.parametrize("proxy", [False, True])
def test_registration_uses_real_runtime_codec_and_owner_proof(runtime, wrapper, proxy):
    owner = Keypair.create_from_seed("0x" + "22" * 32)
    address = owner.ss58_address if proxy else None
    assert wrapper.set_session_key_on_chain(TEST_MNEMONIC, "Staking" if proxy else None, address) == "1-2"
    expected_owner = owner if proxy else Keypair.create_from_mnemonic(TEST_MNEMONIC)
    assert ("author_rotateKeysWithOwner", ["0x" + expected_owner.public_key.hex()]) in wrapper.recorded_rpc
    assert runtime.calls[0].value["call_function"] == "set_keys"
    assert runtime.calls[-1].value["call_function"] == ("proxy" if proxy else "set_keys")
    args = runtime.calls[0].value["call_args"]
    assert args["keys"] == runtime.keys
    assert args["proof"] == "0x1234"
    assert len(runtime.submitted) == 1
    assert runtime.closed


def test_registration_preserves_legacy_rotation_fallback(runtime, wrapper):
    wrapper.owner_rotation = False
    assert wrapper.set_session_key_on_chain(TEST_MNEMONIC, None, None) == "1-2"
    assert ("author_rotateKeys", []) in wrapper.recorded_rpc
    args = runtime.calls[0].value["call_args"]
    assert args["proof"] == "0x00"


def test_unsupported_key_layout_fails_before_rotation(runtime, wrapper, monkeypatch):
    monkeypatch.setattr(runtime, "get_metadata_call_function", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="does not support"):
        wrapper.set_session_key_on_chain(TEST_MNEMONIC, None, None)
    assert not any("rotate" in method for method, _ in wrapper.recorded_rpc)
    assert not runtime.submitted
    assert runtime.closed


def test_unsupported_signing_layout_fails_before_rotation(runtime, wrapper, monkeypatch):
    extensions = runtime.metadata.get_signed_extensions()
    extensions["UnknownPayment"] = {"extrinsic": "u32", "additional_signed": "()"}
    monkeypatch.setattr(runtime.metadata, "get_signed_extensions", lambda: extensions)
    with pytest.raises(ValueError, match="Unsupported Enjin"):
        wrapper.set_session_key_on_chain(TEST_MNEMONIC, None, None)
    assert not any("rotate" in method for method, _ in wrapper.recorded_rpc)
    assert not runtime.submitted


def test_submission_errors_are_reported_and_sdk_is_closed(runtime, wrapper, monkeypatch):
    monkeypatch.setattr(runtime, "submit_extrinsic", lambda *args, **kwargs: (_ for _ in ()).throw(SubstrateRequestException("Verification Error")))
    with pytest.raises(ValueError, match="Verification Error"):
        wrapper.set_session_key_on_chain(TEST_MNEMONIC, None, None)
    assert runtime.closed


@pytest.mark.parametrize("runtime", ["relay", "matrix"], indirect=True)
def test_enjin_signature_matches_captured_signed_extension_metadata(runtime):
    PolkadotRpcWrapper._validate_enjin_signed_extensions(runtime)
    call = runtime.compose_call("Session", "set_keys", {"keys": runtime.keys, "proof": "0x00"})
    signer = Keypair.create_from_mnemonic(TEST_MNEMONIC)
    extrinsic = PolkadotRpcWrapper._create_enjin_signed_extrinsic(runtime, call, signer)
    extras = {"CheckMortality": "00", "CheckMetadataHash": "Disabled", "CheckNonce": 51, "ChargeTransactionPayment": 0}
    additional = {
        "CheckSpecVersion": runtime.runtime_version,
        "CheckTxVersion": runtime.transaction_version,
        "CheckGenesis": runtime.get_block_hash(0),
        "CheckMortality": runtime.get_block_hash(0),
        "CheckMetadataHash": None,
    }
    payload = call.data
    for part, values in [("extrinsic", extras), ("additional_signed", additional)]:
        for name, types in runtime.metadata.get_signed_extensions().items():
            codec = runtime.runtime_config.create_scale_object(types[part])
            value = values[name] if name in values else codec.decode(ScaleBytes("0x"))
            payload = payload + codec.encode(value)
    signed = blake2b(payload.data, digest_size=32).digest() if payload.length > 256 else bytes(payload.data)
    assert signer.verify(signed, next(iter(extrinsic.value["signature"].values())))


@pytest.mark.parametrize("method,params", [("author_hasKey", ["0x00", "babe"]), ("author_hasSessionKeys", ["0x00"]), ("author_insertKey", ["ofcw", "secret mnemonic", "0x00"])])
def test_rpc_errors_surface_without_echoing_params(monkeypatch, method, params):
    def post(url, headers, data, timeout):
        assert timeout == 30
        return type("Response", (), {"raise_for_status": lambda self: None, "json": lambda self: {"error": {"message": "Method not found"}}})()

    monkeypatch.setattr(polkadot_rpc_wrapper.requests, "post", post)
    with pytest.raises(ValueError, match="Method not found") as error:
        PolkadotRpcWrapper("9933")._rpc(method, params)
    assert "secret mnemonic" not in str(error.value)


def test_insert_key_defaults_to_aura_and_accepts_explicit_runtime_key_type(monkeypatch):
    wrapper = PolkadotRpcWrapper("9933")
    calls = []
    monkeypatch.setattr(wrapper, "_rpc", lambda *args: calls.append(args))
    wrapper.insert_key("mnemonic", "0x00")
    wrapper.insert_key("mnemonic", "0x00", "ofcw")
    assert [args[1][0] for args in calls] == ["aura", "ofcw"]
    with pytest.raises(ValueError, match="four ASCII"):
        wrapper.insert_key("mnemonic", "0x00", "invalid")


def test_queued_query_failure_preserves_current_authority(runtime, wrapper, monkeypatch):
    original = runtime.query

    def query(module, storage_function, **kwargs):
        if storage_function == "QueuedKeys":
            raise SubstrateRequestException("State unavailable")
        return original(module, storage_function, **kwargs)

    monkeypatch.setattr(runtime, "query", query)
    assert wrapper.is_validating_this_era()["readiness_unknown"]


def test_registration_keeps_websocket_transport_for_inclusion(runtime, wrapper, monkeypatch):
    connections = []
    monkeypatch.setattr(polkadot_rpc_wrapper, "SubstrateInterface", lambda **kwargs: connections.append(kwargs) or runtime)
    wrapper.set_session_key_on_chain(TEST_MNEMONIC, None, None)
    assert connections == [{"url": "ws://localhost:9933", "ws_options": {"timeout": 120}}]


def test_insert_key_redacts_mnemonic_echoed_in_rpc_error(monkeypatch):
    def post(*args, **kwargs):
        return type("Response", (), {"raise_for_status": lambda self: None, "json": lambda self: {"error": {"message": "Invalid seed: secret mnemonic"}}})()

    monkeypatch.setattr(polkadot_rpc_wrapper.requests, "post", post)
    with pytest.raises(ValueError, match="Invalid seed: <redacted>"):
        PolkadotRpcWrapper("9933").insert_key("secret mnemonic", "0x01")
