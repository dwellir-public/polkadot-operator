#!/usr/bin/env python3

import requests
import json
import re
from typing import Tuple
from substrateinterface import SubstrateInterface, Keypair
import utils

class PolkadotRpcWrapper():

    def __init__(self, port):
        self.__server_address = f'http://localhost:{port}'
        self.__server_address_ws = f'ws://localhost:{port}'
        self.__headers = {'Content-Type': 'application/json'}

    def get_session_key(self):
        """
        Get a new session key from node. (E.g. get_session_key() -> '0xb75f94a5eec...')
        :return: boolean
        """
        data = '{"id":1, "jsonrpc":"2.0", "method": "author_rotateKeys", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data)
        response_json = json.loads(response.text)
        return response_json['result']

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
        return response_json['result']['isSyncing']

    def get_version(self) -> str:
        """
        Checks which version polkadot service is running (E.g. get_version() -> '0.9.3')
        :return: string
        """
        data = '{"id":1, "jsonrpc":"2.0", "method": "system_version", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data, timeout=None)
        response_json = json.loads(response.text)
        result = response_json['result']
        version_number = re.search(r'([\d.]+)', result).group(1)
        return version_number

    def get_block_height(self) -> int:
        """
        Checks the current block height of this node.
        :return: string
        """
        data = '{"id": 1, "jsonrpc": "2.0", "method": "chain_getHeader", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data, timeout=None)
        response_json = json.loads(response.text)
        block_height = int(response_json['result']['number'], 16)
        return block_height

    def get_system_peers(self) -> Tuple[list, bool]:
        """
        Gets the list of currently connected peers for this node.

        NOTE! Requires that the node has `--rpc-methods unsafe` enabled.

        :return: Tuple[list, bool]
        """
        data = '{"id": 1, "jsonrpc": "2.0", "method": "system_peers", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data, timeout=None)
        response_json = json.loads(response.text)
        if 'error' in response_json.keys():
            return [response_json['error']['message']], False
        peer_list = response_json['result']
        return peer_list, True

    def get_chain_name(self) -> str:
        """
        Get the name of the chain this node is connected to.
        :return: str
        """
        data = '{"id":1, "jsonrpc":"2.0", "method": "system_chain", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data)
        response_json = json.loads(response.text)
        return response_json['result']

    def has_session_key(self, session_key):
        """
        Checks if this node has the supplied session_key (E.g. 0xb75f94a5eec... )
        :param session_key: string
        :return: boolean
        """
        data = '{"id": 1, "jsonrpc":"2.0", "method": "author_hasSessionKeys", "params":["' + session_key + '"]}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data)
        response_json = json.loads(response.text)
        result = response_json['result']
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
            session_key = '0x'
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
            session_key = '0x'
            for k in result.values():
                session_key += k[2:]
            if self.has_session_key(session_key):
                return session_key
        return False

    def set_session_key_on_chain(self, mnemonic):
        """
        Sets a session key on-chain for a validator/collator.
        :param mnemonic: string
        :return: the receipt of the extrinsic.
        """

        # Generate a new session key
        data = '{"id":1, "jsonrpc":"2.0", "method": "author_rotateKeys", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data)
        response_json = json.loads(response.text)
        session_key = response_json['result']
        if not session_key:
            return False

        session_key_split = utils.split_session_key(session_key)

        chain_name = self.get_chain_name()
        is_enjin = 'enjin' in chain_name.lower()

        if is_enjin:
            # Enjin ecosystem
            if len(session_key_split) == 6:
                # Enjin relay chain
                keys = {
                    'grandpa': session_key_split[0],
                    'babe': session_key_split[1],
                    'im_online': session_key_split[2],
                    'para_validator': session_key_split[3],
                    'para_assignment': session_key_split[4],
                    'authority_discovery': session_key_split[5],
                }
            elif len(session_key_split) == 2:
                # Enjin parachain
                keys = {
                    'aura': session_key_split[0],
                    'pools': session_key_split[1],
                }
            else:
                raise ValueError(f"Enjin chain with {len(session_key_split)} session keys not supported")
        elif len(session_key_split) == 6:
            # Relay chain in Polkadot ecosystem
            keys = {
                'grandpa': session_key_split[0],
                'babe': session_key_split[1],
                'para_validator': session_key_split[2],
                'para_assignment': session_key_split[3],
                'authority_discovery': session_key_split[4],
                'beefy': session_key_split[5],
            }
        elif len(session_key_split) == 1:
            # Parachain in Polkadot ecosystem
            keys = {
                'aura': session_key_split[0],
            }
        else:
            raise ValueError(f"Mismatch between chain {chain_name} and number of session keys ({len(session_key_split)})")

        substrate = SubstrateInterface(url=self.__server_address_ws)
        # Set the new session key on-chain for the validator/collator
        call = substrate.compose_call(
            'Session', 'set_keys', {
                'keys': keys,
                'proof': '0x00',
            }
        )
        keypair = Keypair.create_from_mnemonic(mnemonic)
        extrinsic = substrate.create_signed_extrinsic(call=call, keypair=keypair)
        result = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
        if not result.is_success:
            raise ValueError(result.error_message)
        return result.get_extrinsic_identifier()
