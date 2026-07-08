#!/usr/bin/env python3

import json
import re
from hashlib import blake2b
from typing import Tuple

import requests
from scalecodec.base import ScaleBytes
from substrateinterface import Keypair, SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException

from core.utils import general_util


class PolkadotRpcWrapper:
    def __init__(self, port):
        self.__server_address = f"http://localhost:{port}"
        self.__server_address_ws = f"ws://localhost:{port}"
        self.__headers = {"Content-Type": "application/json"}

    def get_session_key(self):
        """
        Get a new session key from node. (E.g. get_session_key() -> '0xb75f94a5eec...')
        :return: boolean
        """
        data = '{"id":1, "jsonrpc":"2.0", "method": "author_rotateKeys", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data)
        response_json = json.loads(response.text)
        return response_json["result"]

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
        data = '{"id":1, "jsonrpc":"2.0", "method": "system_chain", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data)
        response_json = json.loads(response.text)
        return response_json["result"]

    def has_session_key(self, session_key):
        """
        Checks if this node has the supplied session_key (E.g. 0xb75f94a5eec... )
        :param session_key: string
        :return: boolean
        """
        data = '{"id": 1, "jsonrpc":"2.0", "method": "author_hasSessionKeys", "params":["' + session_key + '"]}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data)
        response_json = json.loads(response.text)
        result = response_json["result"]
        return result

    def insert_key(self, mnemonic, address):
        """
        Inserts a key to keystore.
        :param mnemonic: string
        :param address: string
        :return: boolean
        """
        data = '{"id": 1,"jsonrpc":"2.0", "method": "author_insertKey", "params":["aura","' + mnemonic + '","' + address + '"]}'
        requests.post(url=self.__server_address, headers=self.__headers, data=data)

    def is_validating_this_era(self):
        """
        Check if this node is currently producing block for a validator/collator.
        It does so by checking if any session key currently on-chain is present on this node.
        :return: the validator/collator address or False.
        """
        substrate = SubstrateInterface(url=self.__server_address)
        result = substrate.query("Session", "QueuedKeys").value_serialized
        for validator in result:
            keys = validator[1]
            session_key = "0x"
            for k in keys.values():
                # Some chains uses multiple keys. Before checking if it exist on the node they need to be concatenated removing preceding '0x'.
                session_key += k[2:]
            if self.has_session_key(session_key):
                return {"validator": validator[0], "session_key": session_key}
        return False

    def is_validating_next_era(self, address):
        """
        Check if this node has the intetion to validate for validator/collator 'address' next era.
        It checks on-chain which session key is set to be used for validating next era for 'address'.
        And if that session key exist on this node.
        :return: the session key if found on this node, else False.
        """
        substrate = SubstrateInterface(url=self.__server_address)
        result = substrate.query("Session", "NextKeys", [address]).value_serialized
        if result:
            session_key = "0x"
            for k in result.values():
                session_key += k[2:]
            if self.has_session_key(session_key):
                return session_key
        return False

    @staticmethod
    def _create_enjin_signed_extrinsic(substrate, call, keypair):
        substrate.init_runtime()
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

        # Generate a new session key
        session_key = self.get_session_key()
        if not session_key:
            raise ValueError("Failed to generate a new session key")

        session_key_split = general_util.split_session_key(session_key)

        chain_name = self.get_chain_name()

        keys = general_util.name_session_keys(chain_name, session_key_split)

        substrate = SubstrateInterface(url=self.__server_address_ws)
        keypair = Keypair.create_from_mnemonic(mnemonic)
        # Set the new session key on-chain for the validator/collator
        call = substrate.compose_call(
            "Session",
            "set_keys",
            {
                "keys": keys,
                "proof": "0x00",
            },
        )
        # If using proxy account, wrap the set_keys call in a proxy call
        if address and proxy_type:
            final_call = substrate.compose_call(
                call_module="Proxy",
                call_function="proxy",
                call_params={
                    "real": address,
                    "force_proxy_type": proxy_type,
                    "call": call,
                },
            )
        else:
            final_call = call

        if "enjin" in chain_name.lower():
            extrinsic = self._create_enjin_signed_extrinsic(substrate, final_call, keypair)
        # A work around to deal with this issue: https://github.com/JAMdotTech/py-polkadot-sdk/issues/412
        elif "kilt" in chain_name.lower():
            substrate.runtime_config.update_type_registry_types({"Index": "U64"})
            extrinsic = substrate.create_signed_extrinsic(call=final_call, keypair=keypair)
        else:
            extrinsic = substrate.create_signed_extrinsic(call=final_call, keypair=keypair)

        try:
            result = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        except SubstrateRequestException as e:
            raise ValueError(str(e)) from e
        if not result.is_success:
            raise ValueError(result.error_message)
        return result.get_extrinsic_identifier()
