#!/usr/bin/env python3

import constants as c
import utils
from pathlib import Path
from os.path import exists
import re
from ops.model import ConfigData


class ServiceArgs():

    def __init__(self, config: ConfigData, relay_rpc_urls: dict):
        service_args = self.__encode_for_emoji(config.get('service-args'))
        self._relay_rpc_urls = relay_rpc_urls
        self._chain_spec_url = config.get('chain-spec-url')
        self._local_relaychain_spec_url = config.get('local-relaychain-spec-url')
        self._runtime_wasm_override = True if config.get('wasm-runtime-url') else False
        self.__check_service_args(service_args)
        self.service_args_list = self.__service_args_to_list(service_args)
        self.__check_service_args(self.service_args_list)
        # Service args that is modified to use for the service.
        self.service_args_list_customized = self.service_args_list
        self.__customize_service_args()

    @property
    def service_args_string(self) -> list:
        """Get the modified service args as string. This is what should be used for the service."""
        return ' '.join(str(x) for x in self.service_args_list_customized)

    @property
    def chain_name(self) -> str:
        """Get the value of '--chain' current set in the service-args config parameter."""
        try:
            i = self.service_args_list.index('--chain')
            return self.service_args_list[i + 1]
        except ValueError:
            return ''

    @property
    def is_validator(self) -> bool:
        """Check if the node is running as a validator or collator."""
        return '--validator' in self.service_args_list or '--collator' in self.service_args_list

    @property
    def rpc_port(self) -> str:
        """Get the value of '--rpc-port' current set in the service-args config parameter."""
        try:
            i = self.service_args_list.index('--rpc-port')
            return self.service_args_list[i + 1]
        except ValueError:
            return ''

    @property
    def ws_port(self) -> str:
        """Get the value of '--ws-port' current set in the service-args config parameter."""
        try:
            i = self.service_args_list.index('--ws-port')
            return self.service_args_list[i + 1]
        except ValueError:
            return ''

    def __check_service_args(self, service_args: str or list):
        msg = ""
        # Check for service arguments that must be set.
        if "--chain" not in service_args:
            msg = "'--chain' must be set in 'service-args'."
        elif "--rpc-port" not in service_args:
            msg = "'--rpc-port' must be set in 'service-args'."

        # Check for service arguments that must NOT be set.
        elif "--prometheus-port" in service_args:
            msg = "'--prometheus-port' may not be set! Charm assumes default port 9615."
        elif "--node-key-file" in service_args:
            msg = f'\'--node-key-file\' may not be set! Path is hardcoded to {c.NODE_KEY_FILE}'

        if msg:
            raise ValueError(msg)

    def __service_args_to_list(self, service_args: str) -> list:
        # Split on any number of spaces and '='. Hence, this will support both '--key value' and '--key=value' in the config.
        service_args = re.split(' +|=', service_args)
        return service_args

    def __encode_for_emoji(self, text):
        # encoding to support emoji codes, typically used in '--name'.
        text = text.encode('latin_1').decode("raw_unicode_escape").encode('utf-16', 'surrogatepass').decode('utf-16')
        return text

    def __set_chain_name(self, value: str, position: int):
        try:
            # Try to change the value of '--chain' if it already exists in the service args.
            # Position 0 would be the first occurrence, 1 the second.
            chain_key_index = [i for i, n in enumerate(self.service_args_list_customized) if n == '--chain'][position]
            self.service_args_list_customized[chain_key_index + 1] = value
        except IndexError:
            # If '--chain' does not exist for the given position, add it.
            if position == 0:
                self.__add_firstchain_args(['--chain', value])
            elif position == 1:
                self.__add_secondchain_args(['--chain', value])

    def __add_firstchain_args(self, args: list):
        """First part (to the left of --) in service args. Typically the parachain part for parachains."""
        self.service_args_list_customized = args + self.service_args_list_customized

    def __add_secondchain_args(self, args: list):
        """Second part (to the right of --) in service args. Typically the relay chain for parachains."""
        if '--' not in self.service_args_list_customized:
            self.service_args_list_customized = self.service_args_list_customized + ['--']
        self.service_args_list_customized = self.service_args_list_customized + args

    def __customize_service_args(self):
        self.__add_firstchain_args(['--node-key-file', c.NODE_KEY_FILE])
        if self._relay_rpc_urls:
            self.__add_firstchain_args(['--relay-chain-rpc-urls'] + list(self._relay_rpc_urls.values()))

        # All hardcoded --chain overrides in the functions below are deprecated and the values should be set in the new chain-spec configs instead.
        if self.chain_name.startswith('aleph-zero'):
            self.__aleph_zero()
        elif self.chain_name in ['crust-mainnet', 'crust-maxwell', 'crust-rocky']:
            self.__crust()

        # The chain spec configs should be applied after hardcoded chain customizations above since this should override any hardcoded --chain overrides.
        if self._chain_spec_url:
            utils.download_chain_spec(self._chain_spec_url, 'chain-spec.json')
            self.__set_chain_name(f'{c.CHAIN_SPEC_DIR}/chain-spec.json', 0)
        if self._local_relaychain_spec_url:
            utils.download_chain_spec(self._local_relaychain_spec_url, 'relaychain-spec.json')
            self.__set_chain_name(f'{c.CHAIN_SPEC_DIR}/relaychain-spec.json', 1)
        if self._runtime_wasm_override:
            self.__add_firstchain_args(['--wasm-runtime-overrides', c.WASM_DIR])

    def __aleph_zero(self):
        if self.chain_name.endswith('testnet'):
            self.__set_chain_name('testnet', 0)
        elif self.chain_name.endswith('mainnet'):
            self.__set_chain_name('mainnet', 0)

    def __crust(self):
        if self.chain_name == 'crust-mainnet':
            self.__set_chain_name('mainnet', 0)
        elif self.chain_name == 'crust-maxwell':
            self.__set_chain_name('maxwell', 0)
        elif self.chain_name == 'crust-rocky':
            self.__set_chain_name('rocky', 0)
