#!/usr/bin/env python3

import requests
import subprocess as sp
from pathlib import Path
import shutil
import sys
import hashlib
import logging
import re
from docker import Docker

logger = logging.getLogger(__name__)

USER = 'polkadot'
HOME_PATH = Path('/home/polkadot')
BINARY_PATH = Path(HOME_PATH, 'polkadot')
CHAIN_SPEC_PATH = Path(HOME_PATH, 'spec')
NODE_KEY_PATH = Path(HOME_PATH, 'node-key')
DB_CHAIN_PATH = Path(HOME_PATH, '.local/share/polkadot/chains')
DB_RELAY_PATH = Path(HOME_PATH, '.local/share/polkadot/polkadot')


def install_docker() -> None:
    try:
        sp.check_call(["docker", "--version"])
    except FileNotFoundError:
        sp.run(['curl', '-fsSL', 'https://get.docker.com', '-o', 'get-docker.sh'], check=False)
        sp.run(['sh', 'get-docker.sh'], check=False)
        sp.run(['usermod', '-aG', 'docker', USER], check=False)


def install_binary(config, chain_name):
    if config.get('binary-url') and config.get('docker-tag'):
        raise ValueError("Only one of 'binary-url' or 'docker-tag' can be set at the same time!")
    if config.get('binary-url'):
        install_binary_from_url(config.get('binary-url'), config.get('binary-check'))
    elif config.get('docker-tag'):
        install_docker()
        Docker(chain_name, config.get('docker-tag')).extract_resources_from_docker()
    else:
        raise ValueError("Either 'binary-url' or 'docker-tag' must be set!")


def install_binary_from_url(url, binary_check):
    # Download polkadot binary to memory and compute sha256 hash
    binary_response = requests.get(url, allow_redirects=True, timeout=None)
    if binary_response.status_code != 200:
        raise ValueError(f"Download binary failed with: {binary_response.text}. Check 'binary-url'!")
    if binary_check:
        binary_hash = hashlib.sha256(binary_response.content).hexdigest()

        # Download and extract target sha256
        sha256_url = url + '.sha256'
        sha256_response = requests.get(sha256_url, allow_redirects=True, timeout=None)
        data = sha256_response.text
        target_hash = data.split(' ')[0]

        # Save polkadot binary iff hash is correct
        if (binary_hash != target_hash):
            raise ValueError("Binary downloaded has wrong hash!")
    stop_polkadot()
    with open(BINARY_PATH, 'wb') as f:
        f.write(binary_response.content)
    start_polkadot()


def download_chain_spec(url, filename):
    # Download file
    file_response = requests.get(url, timeout=None)
    if not CHAIN_SPEC_PATH.exists():
        CHAIN_SPEC_PATH.mkdir(parents=True)
    with open(Path(CHAIN_SPEC_PATH, filename), 'wb') as f:
        f.write(file_response.content)
    sp.run(['chown', '-R', f'{USER}:{USER}', CHAIN_SPEC_PATH], check=False)


def setup_group_and_user():
    sp.run(['addgroup', '--system', USER], check=False)
    sp.run(['adduser', '--system', '--home', HOME_PATH, '--disabled-password', '--ingroup', USER, USER], check=False)
    sp.run(['chown', f'{USER}:{USER}', HOME_PATH], check=False)
    sp.run(['chmod', '700', HOME_PATH], check=False)


def create_env_file_for_service():
    with open(f'/etc/default/{USER}', 'w', encoding='utf-8') as f:
        f.write(f'{USER.upper()}_CLI_ARGS=\'\'')


def install_service_file(source_path):
    target_path = Path(f'/etc/systemd/system/{USER}.service')
    shutil.copyfile(source_path, target_path)
    sp.run(['systemctl', 'daemon-reload'], check=False)


def update_service_args(service_args):
    args = f"{USER.upper()}_CLI_ARGS='{service_args}'"

    with open(f'/etc/default/{USER}', 'w', encoding='utf-8') as f:
        f.write(args + '\n')
    sp.run(['systemctl', 'restart', f'{USER}.service'], check=False)


def install_node_exporter():
    try:
        packages = ['prometheus-node-exporter']
        command = ["sudo", "apt", "install", "-y"]
        command.extend(packages)
        sp.run(command, check=True)
    except sp.CalledProcessError as e:
        print(e)
        sys.exit(-1)


def get_binary_version() -> str:
    if BINARY_PATH.exists():
        command = [BINARY_PATH, "--version"]
        output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        version = re.search(r'([\d.]+)', output).group(1)
        return version
    return ""


def get_binary_md5sum() -> str:
    if BINARY_PATH.exists():
        command = ['md5sum', BINARY_PATH]
        md5sum_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        return md5sum_output.split(' ')[0]  # Output inclkudes path of binary, which we skip including
    return ""


def get_binary_last_changed() -> str:
    if BINARY_PATH.exists():
        command = ['stat', BINARY_PATH]
        stat_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        stat_split = re.split('Change: ', stat_output)[1].split(' ')
        date = stat_split[0]
        time = stat_split[1].split('.')[0]
        return date + ' ' + time + ' UTC'  # TODO: makek this confirm that system time is in UTC?
    return ""


def stop_polkadot():
    sp.run(['systemctl', 'stop', f'{USER}.service'], check=False)


def start_polkadot():
    sp.run(['chown', f'{USER}:{USER}', BINARY_PATH], check=False)
    sp.run(['chmod', '+x', BINARY_PATH], check=False)
    sp.run(['systemctl', 'start', f'{USER}.service'], check=False)


def write_node_key_file(key):
    with open(NODE_KEY_PATH, "w", encoding='utf-8') as f:
        f.write(key)
    sp.run(['chown', f'{USER}:{USER}', NODE_KEY_PATH], check=False)
    sp.run(['chmod', '0600', NODE_KEY_PATH], check=False)


def get_disk_usage(path: Path) -> str:
    if not path.exists():
        return ''
    command = ['du', str(path), '-hs']
    output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8')
    size = re.search(r'(\d+(\.\d+)?[GMT])', output).group(1)
    return size


def get_chain_disk_usage() -> str:
    if DB_CHAIN_PATH.exists():
        return get_disk_usage(DB_CHAIN_PATH)
    return ""


def get_relay_disk_usage() -> str:
    if DB_RELAY_PATH.exists():
        return get_disk_usage(DB_RELAY_PATH)
    return ""


def get_service_args() -> str:
    command = ['cat', f'/etc/default/{USER}']
    cat_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
    return cat_output.split('=')[1]  # cat:ed file includes the env variable name, which we skip including


def get_polkadot_process_id() -> str:
    command = ['pgrep', f'{USER}']
    pgrep_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
    return pgrep_output


def get_polkadot_proc_cmdline() -> str:
    proc_id = get_polkadot_process_id()
    if proc_id:
        command = f'cat /proc/{proc_id}/cmdline'  # Uses NUL bytes as delimiter
        cat_output = sp.run(command, stdout=sp.PIPE, shell=True, check=False).stdout.decode().split('\x00')
        str_output = ' '.join(cat_output)
        return str_output
    return ""


def is_relay_chain_node() -> bool:
    return not is_parachain_node()


def is_parachain_node() -> bool:
    # TODO: should both of these be required to satsify the node being a parachain, or is one enough?
    if DB_CHAIN_PATH.exists() and DB_RELAY_PATH.exists():
        return True
    if BINARY_PATH.exists():
        command = f'.{BINARY_PATH} --help | grep -i "\-\-collator"'
        output = sp.run(command, stdout=sp.PIPE, cwd='/', shell=True, check=False)
        if output.returncode == 0:
            return True
    return False


def get_relay_for_parachain() -> str:
    if not is_parachain_node():
        return 'error, this is not a parachain'
    try:
        chains_dir = Path(DB_RELAY_PATH, 'chains')
        chains_subdirs = [d for d in chains_dir.iterdir() if d.is_dir()]
        if len(chains_subdirs) == 1:
            db_dir = str(chains_subdirs[0])
            relay_chain = db_dir
            if 'polkadot' in db_dir:
                relay_chain = 'Polkadot'
            if 'ksm' in db_dir:
                relay_chain = 'Kusama'
            if 'westend' in db_dir:
                relay_chain = 'Westend'
            return relay_chain
        return 'error finding Relay Chain DB directory'
    except Exception as e:
        logger.warning(e)
        return 'error finding Relay Chain'
