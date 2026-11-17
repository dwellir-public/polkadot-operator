#!/usr/bin/env python3

import json
import re
from hashlib import blake2b
from typing import Tuple

import requests
from requests.exceptions import RequestException
from scalecodec.base import ScaleBytes
from scalecodec.exceptions import InvalidScaleTypeValueException, RemainingScaleBytesNotEmptyException
from substrateinterface import Keypair, SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException
from substrateinterface.utils.ss58 import ss58_decode

from session_keys import SessionKeyCodec


class PolkadotRpcWrapper:
    def __init__(self, port):
        self.__server_address = f"http://localhost:{port}"
        self.__server_address_ws = f"ws://localhost:{port}"
        self.__headers = {"Content-Type": "application/json"}

    def _rpc(self, method, params=None):
        """Call local RPC with bounded IO and explicit protocol errors."""
        response = requests.post(
            self.__server_address,
            headers=self.__headers,
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}),
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        if "error" in result:
            # Do not include params: insertKey contains a mnemonic.
            message = result["error"].get("message", "RPC error")
            if method == "author_insertKey" and params and params[1]:
                message = message.replace(params[1], "<redacted>")
            raise ValueError(f"{method} failed: {message}")
        if "result" not in result:
            raise ValueError(f"{method} returned no result")
        return result["result"]

    def get_session_key(self):
        """Generate a new complete session-key bundle on the node."""
        return self._rpc("author_rotateKeys")

    def rpc_method_exists(self, method):
        """Check method availability without treating RPC errors as absence."""
        return method in self._rpc("rpc_methods")["methods"]

    def get_session_key_with_owner(self, owner_public_key):
        """Generate a session-key bundle and its owner-bound proof."""
        result = self._rpc("author_rotateKeysWithOwner", [owner_public_key])
        return result["keys"], result["proof"]

    def is_syncing(self) -> str:
        """
        Checks if polkadot service is still syncing.
        Should return False when node is done syncing and ready to use as a validator.
        (E.g. is_syncing() -> True)
        :return: boolean
        """
        data = '{"id":1, "jsonrpc":"2.0", "method": "system_health", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data)
        response_json = json.loads(response.text)
        return response_json["result"]["isSyncing"]

    def get_version(self) -> str:
        """
        Checks which version polkadot service is running (E.g. get_version() -> '0.9.3')
        :return: string
        """
        data = '{"id":1, "jsonrpc":"2.0", "method": "system_version", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data, timeout=None)
        response_json = json.loads(response.text)
        result = response_json["result"]
        version_number = re.search(r"([\d.]+)", result).group(1)
        return version_number

    def get_block_height(self) -> int:
        """
        Checks the current block height of this node.
        :return: string
        """
        data = '{"id": 1, "jsonrpc": "2.0", "method": "chain_getHeader", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data, timeout=None)
        response_json = json.loads(response.text)
        block_height = int(response_json["result"]["number"], 16)
        return block_height

    def get_genesis_hash(self) -> str:
        """
        Gets the genesis hash of the chain this node is connected to.
        :return: string
        """
        data = '{"jsonrpc": "2.0", "id": 1, "method": "chain_getBlockHash", "params": [0]}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data, timeout=None)
        response_json = json.loads(response.text)
        return response_json["result"]

    def get_system_peers(self) -> Tuple[list, bool]:
        """
        Gets the list of currently connected peers for this node.

        NOTE! Requires that the node has `--rpc-methods unsafe` enabled.

        :return: Tuple[list, bool]
        """
        data = '{"id": 1, "jsonrpc": "2.0", "method": "system_peers", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data, timeout=None)
        response_json = json.loads(response.text)
        if "error" in response_json.keys():
            return [response_json["error"]["message"]], False
        peer_list = response_json["result"]
        return peer_list, True

    def get_chain_name(self) -> str:
        """
        Get the name of the chain this node is connected to.
        :return: str
        """
        return self._rpc("system_chain")

    def has_session_key(self, session_key):
        """Check possession of the complete supplied bundle, including auxiliary keys."""
        result = self._rpc("author_hasSessionKeys", [session_key])
        if not isinstance(result, bool):
            raise ValueError("author_hasSessionKeys returned no boolean result")
        return result

    def has_key(self, public_key, key_type):
        """Check one public key under its runtime key-type ID."""
        result = self._rpc("author_hasKey", [public_key, key_type])
        if not isinstance(result, bool):
            raise ValueError("author_hasKey returned no boolean result")
        return result

    def insert_key(self, mnemonic, address, key_type="aura"):
        """Insert a key of the specified four-byte type, surfacing RPC failures."""
        if not re.fullmatch(r"[a-zA-Z0-9]{4}", key_type):
            raise ValueError("key-type must contain exactly four ASCII letters or digits")
        self._rpc("author_insertKey", [key_type, mnemonic, address])

    def _key_readiness(self, substrate, block_hash, keys):
        """Inspect a registered or queued bundle without asserting election."""
        codec = SessionKeyCodec(substrate, block_hash)
        bundle = codec.encode(keys)
        missing = [name for name, public, key_type in codec.key_types(bundle) if not self.has_key(public, key_type)]
        return {"session_key": bundle, "missing_keys": missing}

    def is_validating_this_era(self):
        """Find a current BABE/Aura authority key held locally, not block production."""
        with SubstrateInterface(url=self.__server_address) as substrate:
            block_hash = substrate.get_chain_finalised_head()
            if substrate.get_metadata_storage_function("Babe", "Authorities", block_hash=block_hash):
                pallet, field, key_type = "Babe", "babe", "babe"
            elif substrate.get_metadata_storage_function("Aura", "Authorities", block_hash=block_hash):
                pallet, field, key_type = "Aura", "aura", "aura"
            else:
                raise ValueError("Runtime has no supported BABE/Aura authority list")
            authorities = substrate.query(pallet, "Authorities", block_hash=block_hash).value_serialized
            validators = substrate.query("Session", "Validators", block_hash=block_hash).value_serialized
            if len(authorities) != len(validators):
                raise ValueError("Authority list cannot be aligned with Session.Validators")
            for validator, authority in zip(validators, authorities):
                public = authority[0] if pallet == "Babe" else authority
                if self.has_key(public, key_type):
                    result = {"validator": validator, "authority_key": public, "key_type": key_type}
                    try:
                        result.update(self._queued_key_readiness(substrate, block_hash, validator, field, public))
                    except (ValueError, SubstrateRequestException, RequestException):
                        result["readiness_unknown"] = True
                    return result
        return False

    def _queued_key_readiness(self, substrate, block_hash, validator, field, public):
        """Only attribute a queued bundle to the same current consensus key."""
        queued = substrate.query("Session", "QueuedKeys", block_hash=block_hash).value_serialized
        keys = next((keys for address, keys in queued if address == validator), None)
        # Queued keys can already target a different node after rotation.
        if keys and keys.get(field) == public:
            return self._key_readiness(substrate, block_hash, keys)
        return {}

    def is_validating_next_era(self, address):
        """Inspect registered NextKeys; this cannot establish future election."""
        with SubstrateInterface(url=self.__server_address) as substrate:
            block_hash = substrate.get_chain_finalised_head()
            keys = substrate.query("Session", "NextKeys", [address], block_hash=block_hash).value_serialized
            return self._key_readiness(substrate, block_hash, keys) if keys else None

    @staticmethod
    def _validate_enjin_signed_extensions(substrate):
        """Reject layouts the Enjin signer cannot encode before rotating keys."""
        extensions = substrate.metadata.get_signed_extensions()
        expected = {
            "extrinsic": ["CheckMortality", "CheckMetadataHash", "CheckNonce", "ChargeTransactionPayment"],
            "additional_signed": ["CheckSpecVersion", "CheckTxVersion", "CheckGenesis", "CheckMortality", "CheckMetadataHash"],
        }
        for part, supported in expected.items():
            present = []
            for name, types in extensions.items():
                if name in supported:
                    present.append(name)
                else:
                    codec = substrate.runtime_config.create_scale_object(types[part])
                    try:
                        codec.decode(ScaleBytes("0x"), check_remaining=True)
                    except (ValueError, InvalidScaleTypeValueException, RemainingScaleBytesNotEmptyException) as exc:
                        raise ValueError(f"Unsupported Enjin signed extension: {name}") from exc
            if present != supported:
                raise ValueError(f"Unsupported Enjin signed-extension order for {part}")

    @staticmethod
    def _create_enjin_signed_extrinsic(substrate, call, keypair):
        substrate.init_runtime()
        PolkadotRpcWrapper._validate_enjin_signed_extensions(substrate)
        signed_extensions = substrate.metadata.get_signed_extensions()

        substrate.runtime_config.update_type_registry_types(
            {
                "ExtrinsicV4": {
                    "type": "struct",
                    "type_mapping": [
                        ["address", "Address"],
                        ["signature", "ExtrinsicSignature"],
                        ["era", signed_extensions["CheckMortality"]["extrinsic"]],
                        ["mode", signed_extensions["CheckMetadataHash"]["extrinsic"]],
                        ["nonce", signed_extensions["CheckNonce"]["extrinsic"]],
                        ["tip", signed_extensions["ChargeTransactionPayment"]["extrinsic"]],
                        ["call", "Call"],
                    ],
                }
            }
        )

        nonce = substrate.get_account_nonce(keypair.ss58_address) or 0
        era = "00"
        genesis_hash = substrate.get_block_hash(0)
        block_hash = genesis_hash

        signature_payload = substrate.runtime_config.create_scale_object("ExtrinsicPayloadValue")
        signature_payload.type_mapping = [
            ["call", "CallBytes"],
            ["era", signed_extensions["CheckMortality"]["extrinsic"]],
            ["mode", signed_extensions["CheckMetadataHash"]["extrinsic"]],
            ["nonce", signed_extensions["CheckNonce"]["extrinsic"]],
            ["tip", signed_extensions["ChargeTransactionPayment"]["extrinsic"]],
            ["spec_version", signed_extensions["CheckSpecVersion"]["additional_signed"]],
            ["transaction_version", signed_extensions["CheckTxVersion"]["additional_signed"]],
            ["genesis_hash", signed_extensions["CheckGenesis"]["additional_signed"]],
            ["block_hash", signed_extensions["CheckMortality"]["additional_signed"]],
            ["metadata_hash", signed_extensions["CheckMetadataHash"]["additional_signed"]],
        ]
        signature_payload.encode(
            {
                "call": str(call.data),
                "era": era,
                "mode": "Disabled",
                "nonce": nonce,
                "tip": 0,
                "spec_version": substrate.runtime_version,
                "transaction_version": substrate.transaction_version,
                "genesis_hash": genesis_hash,
                "block_hash": block_hash,
                "metadata_hash": None,
            }
        )

        payload_data = signature_payload.data
        if payload_data.length > 256:
            payload_data = ScaleBytes(data=blake2b(payload_data.data, digest_size=32).digest())
        signature = keypair.sign(payload_data)

        extrinsic = substrate.runtime_config.create_scale_object("Extrinsic", metadata=substrate.metadata)
        extrinsic.encode(
            {
                "account_id": f"0x{keypair.public_key.hex()}",
                "signature": f"0x{signature.hex()}",
                "signature_version": keypair.crypto_type,
                "call_function": call.value["call_function"],
                "call_module": call.value["call_module"],
                "call_args": call.value["call_args"],
                "nonce": nonce,
                "era": era,
                "tip": 0,
                "mode": "Disabled",
            }
        )
        return extrinsic

    def set_session_key_on_chain(self, mnemonic, proxy_type, address):
        """
        Sets a session key on-chain for a validator/collator.
        :param mnemonic: string
        :return: the receipt of the extrinsic.
        """

        keypair = Keypair.create_from_mnemonic(mnemonic)
        with SubstrateInterface(url=self.__server_address_ws, ws_options={"timeout": 120}) as substrate:
            block_hash = substrate.get_chain_finalised_head()
            codec = SessionKeyCodec(substrate, block_hash)
            queued = substrate.query("Session", "QueuedKeys", block_hash=block_hash).value_serialized
            if not queued:
                raise ValueError("Cannot preflight SessionKeys without a queued key sample")
            codec.key_types(codec.encode(queued[0][1]))
            chain_name = self.get_chain_name()
            if "enjin" in chain_name.lower():
                self._validate_enjin_signed_extensions(substrate)
            if self.rpc_method_exists("author_rotateKeysWithOwner"):
                owner_public_key = f"0x{ss58_decode(address)}" if address else f"0x{keypair.public_key.hex()}"
                session_key, proof = self.get_session_key_with_owner(owner_public_key)
            else:
                session_key, proof = self.get_session_key(), "0x00"
            if not session_key:
                raise ValueError("Failed to generate a new session key")
            keys = codec.decode(session_key)
            call = substrate.compose_call("Session", "set_keys", {"keys": keys, "proof": proof})
            if address and proxy_type:
                call = substrate.compose_call(
                    call_module="Proxy",
                    call_function="proxy",
                    call_params={"real": address, "force_proxy_type": proxy_type, "call": call},
                )
            if "enjin" in chain_name.lower():
                extrinsic = self._create_enjin_signed_extrinsic(substrate, call, keypair)
            else:
                if "kilt" in chain_name.lower():
                    substrate.runtime_config.update_type_registry_types({"Index": "U64"})
                extrinsic = substrate.create_signed_extrinsic(call=call, keypair=keypair)
            try:
                receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            except SubstrateRequestException as exc:
                raise ValueError(str(exc)) from exc
            if not receipt.is_success:
                raise ValueError(receipt.error_message)
            return receipt.get_extrinsic_identifier()
