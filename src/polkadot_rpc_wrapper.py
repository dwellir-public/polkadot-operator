#!/usr/bin/env python3

import requests
import json
import re
from typing import Tuple


class PolkadotRpcWrapper():

    def __init__(self, port):
        self.__server_address = f'http://localhost:{port}'
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

    def is_validating(self) -> bool:
        """
        Checks if polkadot service is started as Authority (E.g. is_validating() -> True)
        :return: boolean
        """
        data = '{"id":1, "jsonrpc":"2.0", "method": "system_nodeRoles", "params": []}'
        response = requests.post(url=self.__server_address, headers=self.__headers, data=data)
        response_json = json.loads(response.text)
        if response_json['result'][0] == 'Authority':
            return True
        else:
            return False

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
