#!/usr/bin/env python3

import utils
from pathlib import Path
from os.path import exists
import re


class ServiceArgs():

    def __init__(self, service_args: str):
        service_args = self.__encode_for_emoji(service_args)
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
            msg = f'\'--node-key-file\' may not be set! Path is hardcoded to {utils.NODE_KEY_PATH}'

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

    def __replace_chain_name(self, value: str, position: int):
        chain_key_index = [i for i, n in enumerate(self.service_args_list_customized) if n == '--chain'][position]
        self.service_args_list_customized[chain_key_index + 1] = value

    def __add_firstchain_args(self, args: list):
        """First part (to the left of --) in service args. Typically the parachain part for parachains."""
        self.service_args_list_customized = args + self.service_args_list_customized

    def __add_secondchain_args(self, args: list):
        """Second part (to the right of --) in service args. Typically the relay chain for parachains."""
        self.service_args_list_customized = self.service_args_list_customized + args

    def __customize_service_args(self):
        self.__add_firstchain_args(['--node-key-file', utils.NODE_KEY_PATH])

        if self.chain_name == 'peregrine':
            self.__peregrine()
        elif self.chain_name == 'peregrine-stg-kilt':
            self.__peregrine_stg_kilt()
        elif self.chain_name == 'peregrine-stg-relay':
            self.__peregrine_stg_relay()
        elif self.chain_name == 'turing':
            self.__turing()
        elif self.chain_name == 'bajun':
            self.__bajun()
        elif self.chain_name == 'joystream':
            self.__joystream()
        elif self.chain_name == 'equilibrium':
            self.__equilibrium()
        elif self.chain_name.startswith('aleph-zero'):
            self.__aleph_zero()
        elif self.chain_name in ['pendulum', 'amplitude']:
            self.__pendulum()
        elif self.chain_name == 'tinkernet':
            self.__tinkernet()
        elif self.chain_name == 'clover':
            self.__clover()

    def __peregrine(self):
        self.__replace_chain_name(Path(utils.HOME_PATH, 'dev-specs/kilt-parachain/peregrine-kilt.json'), 0)
        self.__replace_chain_name(Path(utils.HOME_PATH, 'dev-specs/kilt-parachain/peregrine-relay.json'), 1)

    def __peregrine_stg_kilt(self):
        self.__replace_chain_name(Path(utils.HOME_PATH, 'dev-specs/kilt-parachain/peregrine-stg-kilt.json'), 0)
        self.__replace_chain_name(Path(utils.HOME_PATH, 'dev-specs/kilt-parachain/peregrine-stg-relay.json'), 1)

    def __peregrine_stg_relay(self):
        utils.download_chain_spec(
            "https://raw.githubusercontent.com/KILTprotocol/kilt-node/1.7.5/dev-specs/kilt-parachain/peregrine-stg-relay.json", "peregrine-stg-relay.json")
        self.__replace_chain_name(Path(utils.CHAIN_SPEC_PATH, 'peregrine-stg-relay.json'), 0)

    def __turing(self):
        chain_json_url = 'https://raw.githubusercontent.com/OAK-Foundation/OAK-blockchain/master/node/res/turing.json'
        relay_json_url = 'https://raw.githubusercontent.com/paritytech/polkadot/master/node/service/chain-specs/kusama.json'

        chain_json_path = f"{utils.CHAIN_SPEC_PATH}/turing.json"
        relay_json_path = f"{utils.CHAIN_SPEC_PATH}/kusama.json"

        if not exists(chain_json_path):
            utils.download_chain_spec(chain_json_url, 'turing.json')

        if not exists(relay_json_path):
            utils.download_chain_spec(relay_json_url, 'kusama.json')

        self.__replace_chain_name(chain_json_path, 0)
        self.__replace_chain_name(relay_json_path, 1)

    def __bajun(self):
        # TODO: The spec file did not exist on master branch yet. This URL point to a development branch that will probably not exist in the near future.
        # Update the URL to the master branch when the spec file is merged.
        chain_json_url = 'https://raw.githubusercontent.com/ajuna-network/Ajuna/el/tidy-chain-specs/resources/bajun/bajun-raw.json'
        chain_json_path = f"{utils.CHAIN_SPEC_PATH}/bajun-raw.json"

        if not exists(chain_json_path):
            utils.download_chain_spec(chain_json_url, 'bajun-raw.json')

        self.__replace_chain_name(chain_json_path, 0)

    def __joystream(self):
        chain_json_path = f"{utils.CHAIN_SPEC_PATH}/joystream.json"
        utils.download_chain_spec(
            'https://github.com/Joystream/joystream/releases/download/v11.3.0/joy-testnet-7-carthage.json', 'joystream.json')
        self.__replace_chain_name(chain_json_path, 0)

    def __equilibrium(self):
        self.__replace_chain_name(Path(utils.HOME_PATH, 'chainspec.json'), 0)

    def __aleph_zero(self):
        if self.chain_name.endswith('testnet'):
            self.__replace_chain_name('testnet', 0)
        elif self.chain_name.endswith('mainnet'):
            self.__replace_chain_name('mainnet', 0)

    def __pendulum(self):
        if self.chain_name == 'amplitude':
            chain_json_url = 'https://raw.githubusercontent.com/pendulum-chain/pendulum/main/res/amplitude-spec-raw.json'
            relay_json_url = 'https://raw.githubusercontent.com/paritytech/polkadot/master/node/service/chain-specs/kusama.json'
            chain_spec_file_name = 'amplitude.json'
            relay_spec_file_name = 'kusama.json'
        elif self.chain_name == 'pendulum':
            chain_json_url = 'https://raw.githubusercontent.com/pendulum-chain/pendulum/main/res/pendulum-spec-raw.json'
            relay_json_url = 'https://raw.githubusercontent.com/paritytech/polkadot/master/node/service/chain-specs/polkadot.json'
            chain_spec_file_name = 'pendulum.json'
            relay_spec_file_name = 'polkadot.json'

        chain_json_path = f"{utils.CHAIN_SPEC_PATH}/{chain_spec_file_name}"
        relay_json_path = f"{utils.CHAIN_SPEC_PATH}/{relay_spec_file_name}"

        if not exists(chain_json_path):
            utils.download_chain_spec(chain_json_url, chain_spec_file_name)

        if not exists(relay_json_path):
            utils.download_chain_spec(relay_json_url, relay_spec_file_name)

        self.__replace_chain_name(chain_json_path, 0)
        self.__replace_chain_name(relay_json_path, 1)

    def __tinkernet(self):
        if exists(utils.BINARY_PATH):
            chain_json_url = f'https://github.com/InvArch/InvArch-Node/releases/download/v{utils.get_binary_version()}/tinker-raw.json'
        else:
            chain_json_url = 'https://github.com/InvArch/InvArch-Node/blob/main/res/tinker/tinker-raw.json'
        chain_json_path = f"{utils.CHAIN_SPEC_PATH}/tinker-raw.json"

        utils.download_chain_spec(chain_json_url, 'tinker-raw.json')
        self.__replace_chain_name(chain_json_path, 0)

    def __clover(self):
        self.__replace_chain_name(Path(utils.HOME_PATH, 'specs/clover-para-raw.json'), 0)
