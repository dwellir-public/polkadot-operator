#!/usr/bin/env python3

import subprocess as sp
from pathlib import Path
import utils
import os


class Docker():

    def __init__(self, chain_name, docker_tag):
        self.chain_name = chain_name
        self.docker_tag = docker_tag

    def extract_resources_from_docker(self):
        if self.chain_name in ['spiritnet', 'peregrine', 'peregrine-stg-kilt']:
            self.__extract_from_docker('kiltprotocol/kilt-node', '/usr/local/bin/node-executable', '/node/dev-specs')
        elif self.chain_name == 'centrifuge' or self.chain_name == 'altair':
            self.__extract_from_docker('centrifugeio/centrifuge-chain', '/usr/local/bin/centrifuge-chain')
        elif self.chain_name == 'nodle' or self.chain_name == 'arcadia' or self.chain_name == 'eden':
            self.__extract_from_docker('nodlecode/chain', '/usr/local/bin/nodle-parachain')
        elif self.chain_name == 'acala' or self.chain_name == 'karura':
            self.__extract_from_docker(f'acala/{self.chain_name}-node', '/usr/local/bin/acala')
        elif self.chain_name == 'astar' or self.chain_name == 'shiden' or self.chain_name == 'shibuya':
            self.__extract_from_docker('staketechnologies/astar-collator', '/usr/local/bin/astar-collator')
        elif self.chain_name == 'darwinia' or self.chain_name == 'crab':
            self.__extract_from_docker('ghcr.io/darwinia-network/darwinia', '/home/darwinia/darwinia-nodes/darwinia')
        elif self.chain_name == 'moonbeam' or self.chain_name == 'moonriver' or self.chain_name == 'alphanet':
            self.__extract_from_docker('purestake/moonbeam', '/moonbeam/moonbeam')
        elif self.chain_name == 'zeitgeist':
            self.__extract_from_docker('zeitgeistpm/zeitgeist-node-parachain', '/usr/local/bin/zeitgeist')
        elif self.chain_name in ['phala', 'khala']:
            self.__extract_from_docker(f'phalanetwork/{self.chain_name}-node', '/usr/local/bin/khala-node')
        elif self.chain_name == 'heiko' or self.chain_name == 'parallel':
            self.__extract_from_docker('parallelfinance/parallel', '/usr/local/bin/parallel')
        elif self.chain_name == 'turing':
            self.__extract_from_docker('oaknetwork/turing', '/oak/oak-collator')
        elif self.chain_name == 'efinity':
            self.__extract_from_docker('enjin/efinity-node', '/efinity/efinity')
        elif self.chain_name == 'joystream':
            self.__extract_from_docker('joystream/node', '/joystream/node')
        elif self.chain_name == 'aleph-zero-mainnet' or self.chain_name == 'aleph-zero-testnet':
            self.__extract_from_docker('public.ecr.aws/p6e8q1z1/aleph-node', '/usr/local/bin/aleph-node')
        elif self.chain_name == 'equilibrium':
            self.__extract_from_docker('equilab/eq-para', '/usr/local/bin/paranode', '/etc/chainspec.json')
        elif self.chain_name in ['pendulum', 'amplitude']:
            self.__extract_from_docker('pendulumchain/pendulum-collator', '/usr/local/bin/pendulum-collator')
        elif self.chain_name == 'kapex':
            self.__extract_from_docker('totemlive/totem-parachain-collator', '/usr/local/bin/totem-parachain-collator')
        elif self.chain_name == 'clover':
            self.__extract_from_docker('cloverio/clover-para', '/opt/clover/bin/clover', '/opt/specs')
        elif self.chain_name == 'polkadex':
            self.__extract_from_docker('polkadex/parachain', '/data/bin/parachain-polkadex-node', '/data/polkadot-parachain-raw.json')
        elif self.chain_name in ['crust-mainnet', 'crust-maxwell', 'crust-rocky']:
            self.__extract_from_docker('crustio/crust', '/opt/crust/crust')
        else:
            raise ValueError(f"{self.chain_name} is not a supported chain using Docker!")

    def __extract_from_docker(self, docker_image: str, docker_binary_path: str, docker_specs_path: str = None) -> None:
        docker_image_and_tag = f'{docker_image}:{self.docker_tag}'

        try:
            sp.run(['docker', 'pull', docker_image_and_tag], stderr=sp.PIPE, check=True)
        except sp.CalledProcessError as err:
            raise ValueError(f"Could not pull {docker_image_and_tag} check 'docker-tag'!") from err

        sp.run(['docker', 'create', '--name', 'tmp', docker_image_and_tag], check=False)
        utils.stop_polkadot()
        sp.run(['docker', 'cp', f'tmp:{docker_binary_path}', utils.BINARY_PATH], check=True)
        if docker_specs_path:
            sp.run(['docker', 'cp', f'tmp:{docker_specs_path}', utils.HOME_PATH], check=True)
            sp.run(['chown', '-R', 'polkadot:polkadot', Path(utils.HOME_PATH, Path(docker_specs_path).name)], check=True)
        utils.start_polkadot()
        sp.run(['docker', 'rm', 'tmp'], check=True)
        sp.run(['docker', 'rmi', docker_image_and_tag], check=True)
