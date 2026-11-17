"""Offline runtime fixtures captured from the Enjin chains on 2026-11-17."""

import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from scalecodec.base import ScaleBytes
from substrateinterface import SubstrateInterface

from session_keys import SessionKeyCodec


class RecordedRuntime(SubstrateInterface):
    """Real metadata/codecs with an in-memory chain and local key inventory."""

    def __init__(self, kind):
        super().__init__(url="http://fixture.invalid", auto_discover=False)
        recorded = json.loads(gzip.decompress((Path(__file__).parents[1] / "fixtures" / f"enjin-{kind}-metadata.json.gz").read_bytes()))
        self.metadata = self.runtime_config.create_scale_object("MetadataVersioned", data=ScaleBytes(recorded["metadata"]))
        self.metadata.decode()
        self.runtime_config.add_portable_registry(self.metadata)
        self.runtime_version = recorded["runtime"]["specVersion"]
        self.transaction_version = recorded["runtime"]["transactionVersion"]
        self.block_hash = recorded["block_hash"]
        self.kind = kind
        self.chain_name = recorded["chain"]
        self.closed = False
        self.calls = []
        self.submitted = []
        self.query_calls = []
        self.key_types = {
            "grandpa": "gran",
            "babe": "babe",
            "para_validator": "para",
            "para_assignment": "asgn",
            "authority_discovery": "audi",
            "offchain_worker": "ofcw",
            "aura": "aura",
            "beefy": "beef",
        }
        fields = list(self.key_types)[:6] if kind == "relay" else ["aura", "offchain_worker"]
        self.keys = {field: "0x" + f"{index + 1:02x}" * 32 for index, field in enumerate(fields)}
        self.address = "validator-address"
        self.storage = {
            ("Session", "Validators"): [self.address],
            ("Session", "QueuedKeys"): [[self.address, self.keys]],
            ("Session", "NextKeys"): self.keys,
            ("Babe", "Authorities"): [(self.keys.get("babe"), 1)],
            ("Aura", "Authorities"): [self.keys.get("aura")],
        }
        self.local_keys = {(public, self.key_types[name]) for name, public in self.keys.items()}

    def init_runtime(self, *args, **kwargs):
        pass

    def get_chain_finalised_head(self):
        return self.block_hash

    def get_block_hash(self, block_id=None):
        return "0x" + "aa" * 32 if block_id == 0 else self.block_hash

    def get_account_nonce(self, address):
        return 51

    def query(self, module, storage_function, params=None, block_hash=None):
        self.query_calls.append((module, storage_function, params, block_hash))
        return SimpleNamespace(value_serialized=self.storage[(module, storage_function)])

    def rpc_request(self, method, params, **kwargs):
        assert method == "state_call"
        assert params[0] == "SessionKeys_decode_session_keys"
        assert params[2] == self.block_hash
        raw = self.runtime_config.create_scale_object("Bytes").decode(ScaleBytes(params[1]))
        keys = SessionKeyCodec(self, self.block_hash).decode(raw if raw.startswith("0x") else "0x" + raw.encode().hex())
        typed = [(public, "0x" + self.key_types[name].encode().hex()) for name, public in keys.items()]
        codec = self.runtime_config.create_scale_object("Option<Vec<(Bytes, [u8; 4])>>")
        return {"result": str(codec.encode(typed))}

    def compose_call(self, *args, **kwargs):
        call = super().compose_call(*args, **kwargs)
        self.calls.append(call)
        return call

    def submit_extrinsic(self, extrinsic, wait_for_inclusion):
        assert wait_for_inclusion
        self.submitted.append(extrinsic)
        return SimpleNamespace(is_success=True, get_extrinsic_identifier=lambda: "1-2")

    def close(self):
        self.closed = True
        super().close()


@pytest.fixture
def runtime(request):
    instance = RecordedRuntime(getattr(request, "param", "relay"))
    yield instance
    instance.close()
