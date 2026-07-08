import pytest
from scalecodec.base import ScaleBytes

import polkadot_rpc_wrapper
from polkadot_rpc_wrapper import PolkadotRpcWrapper


def test_set_session_key_on_chain_reports_substrate_request_errors(monkeypatch):
    class FakeSubstrateRequestError(Exception):
        pass

    class FakeKeypair:
        @classmethod
        def create_from_mnemonic(cls, mnemonic):
            return cls()

    class FakeSubstrate:
        def __init__(self, url):
            self.url = url

        def compose_call(self, *args, **kwargs):
            return {"args": args, "kwargs": kwargs}

        def create_signed_extrinsic(self, call, keypair):
            return {"call": call, "keypair": keypair}

        def submit_extrinsic(self, extrinsic, wait_for_inclusion):
            raise FakeSubstrateRequestError({"code": 1002, "message": "Verification Error: Runtime error"})

    monkeypatch.setattr(polkadot_rpc_wrapper, "SubstrateRequestException", FakeSubstrateRequestError)
    monkeypatch.setattr(polkadot_rpc_wrapper, "Keypair", FakeKeypair)
    monkeypatch.setattr(polkadot_rpc_wrapper, "SubstrateInterface", FakeSubstrate)
    monkeypatch.setattr(PolkadotRpcWrapper, "get_chain_name", lambda self: "Polkadot")
    monkeypatch.setattr(PolkadotRpcWrapper, "get_session_key", lambda self: "0x" + "11" * 32 * 6)

    with pytest.raises(ValueError, match="Verification Error: Runtime error"):
        PolkadotRpcWrapper("9933").set_session_key_on_chain(
            "test mnemonic",
            "Staking",
            "enBU8hyQvkP7qJLxyfNYRiviNcUQXZtB1Xg1FNifJZnZBaTRE",
        )


def test_create_enjin_signed_extrinsic_uses_runtime_signed_extension_order():  # noqa: C901
    signed_extensions = {
        "CheckMortality": {"extrinsic": "EraType", "additional_signed": "BlockHashType"},
        "CheckMetadataHash": {"extrinsic": "ModeType", "additional_signed": "MetadataHashType"},
        "CheckNonce": {"extrinsic": "NonceType", "additional_signed": "UnitType"},
        "ChargeTransactionPayment": {"extrinsic": "TipType", "additional_signed": "UnitType"},
        "CheckSpecVersion": {"extrinsic": "UnitType", "additional_signed": "SpecVersionType"},
        "CheckTxVersion": {"extrinsic": "UnitType", "additional_signed": "TxVersionType"},
        "CheckGenesis": {"extrinsic": "UnitType", "additional_signed": "GenesisHashType"},
    }

    class FakeMetadata:
        def get_signed_extensions(self):
            return signed_extensions

    class FakePayload:
        def __init__(self):
            self.type_mapping = []
            self.encoded = None
            self.data = ScaleBytes("0x1234")

        def encode(self, value):
            self.encoded = value

    class FakeExtrinsic:
        def __init__(self):
            self.encoded = None

        def encode(self, value):
            self.encoded = value

    class FakeRuntimeConfig:
        def __init__(self):
            self.type_registry_updates = []
            self.payload = FakePayload()
            self.extrinsic = FakeExtrinsic()

        def update_type_registry_types(self, types):
            self.type_registry_updates.append(types)

        def create_scale_object(self, type_string, **kwargs):
            if type_string == "ExtrinsicPayloadValue":
                return self.payload
            if type_string == "Extrinsic":
                return self.extrinsic
            raise AssertionError(f"unexpected scale object: {type_string}")

    class FakeSubstrate:
        def __init__(self):
            self.metadata = FakeMetadata()
            self.runtime_config = FakeRuntimeConfig()
            self.runtime_version = 1070
            self.transaction_version = 18
            self.initialized = False

        def init_runtime(self):
            self.initialized = True

        def get_account_nonce(self, address):
            assert address == "signer"
            return 51

        def get_block_hash(self, block_number):
            assert block_number == 0
            return "0x" + "aa" * 32

    class FakeCall:
        data = "0x1234"
        value = {
            "call_function": "proxy",
            "call_module": "Proxy",
            "call_args": {"real": "validator"},
        }

    class FakeKeypair:
        ss58_address = "signer"
        public_key = bytes.fromhex("11" * 32)
        crypto_type = 1

        def sign(self, payload):
            assert str(payload) == "0x1234"
            return bytes.fromhex("22" * 64)

    substrate = FakeSubstrate()

    extrinsic = PolkadotRpcWrapper._create_enjin_signed_extrinsic(substrate, FakeCall(), FakeKeypair())

    assert substrate.initialized is True
    assert substrate.runtime_config.type_registry_updates == [
        {
            "ExtrinsicV4": {
                "type": "struct",
                "type_mapping": [
                    ["address", "Address"],
                    ["signature", "ExtrinsicSignature"],
                    ["era", "EraType"],
                    ["mode", "ModeType"],
                    ["nonce", "NonceType"],
                    ["tip", "TipType"],
                    ["call", "Call"],
                ],
            }
        }
    ]
    assert substrate.runtime_config.payload.type_mapping == [
        ["call", "CallBytes"],
        ["era", "EraType"],
        ["mode", "ModeType"],
        ["nonce", "NonceType"],
        ["tip", "TipType"],
        ["spec_version", "SpecVersionType"],
        ["transaction_version", "TxVersionType"],
        ["genesis_hash", "GenesisHashType"],
        ["block_hash", "BlockHashType"],
        ["metadata_hash", "MetadataHashType"],
    ]
    assert substrate.runtime_config.payload.encoded["mode"] == "Disabled"
    assert substrate.runtime_config.payload.encoded["nonce"] == 51
    assert extrinsic.encoded["mode"] == "Disabled"
    assert extrinsic.encoded["nonce"] == 51
    assert extrinsic.encoded["signature"] == "0x" + "22" * 64
