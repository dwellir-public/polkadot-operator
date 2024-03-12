#!/usr/bin/env python3

import glob
import requests
import subprocess as sp
import shutil
import sys
import os
import hashlib
import time
import logging
import re
import constants as c
from pathlib import Path
from ops.model import ConfigData
from docker import Docker
from tarball import Tarball
from tarfile import open as open_tarfile


logger = logging.getLogger(__name__)


def install_docker() -> None:
    try:
        sp.check_call(["docker", "--version"])
    except FileNotFoundError:
        sp.run(['curl', '-fsSL', 'https://get.docker.com', '-o', 'get-docker.sh'], check=False)
        sp.run(['sh', 'get-docker.sh'], check=False)
        sp.run(['usermod', '-aG', 'docker', c.USER], check=False)


def install_binary(config: ConfigData, chain_name: str) -> None:
    if config.get('binary-url') and config.get('docker-tag'):
        raise ValueError("Only one of 'binary-url' or 'docker-tag' can be set at the same time!")
    if config.get('binary-url'):
        if config.get('binary-url').endswith('.deb'):
            install_deb_from_url(config.get('binary-url'))
        elif config.get('binary-url').endswith('.tar.gz') or config.get('binary-url').endswith('.tgz'):
            install_tarball_from_url(config.get('binary-url'), config.get('binary-sha256-url'), chain_name)
        elif len(config.get('binary-url').split()) > 1:
            install_binaries_from_urls(config.get('binary-url'), config.get('binary-sha256-url'))
        else:
            install_binary_from_url(config.get('binary-url'), config.get('binary-sha256-url'))
    elif config.get('docker-tag'):
        install_docker()
        Docker(chain_name, config.get('docker-tag')).extract_resources_from_docker()
    else:
        raise ValueError("Either 'binary-url' or 'docker-tag' must be set!")


def find_binary_installed_by_deb(package_name: str, ) -> str:
    files = sp.check_output(['dpkg', '-L', package_name]).decode().split('\n')[:-1]
    bin_files = [file for file in files if file.startswith('/bin/')]
    logger.debug('Found files in /bin/ %s', str(bin_files))
    if len(bin_files) > 1:
        raise Exception(f'Found more than one file installed in /bin/ by package {package_name}. Cannot be sure which one to use.')
    return bin_files[0]


def install_deb_from_url(url: str) -> None:
    deb_response = requests.get(url, allow_redirects=True, timeout=None)
    deb_path = Path(c.HOME_PATH, url.split('/')[-1])
    with open(deb_path, 'wb') as f:
        f.write(deb_response.content)
    package_name = sp.check_output(['dpkg-deb', '-f', deb_path, 'Package']).decode('utf-8').strip()
    logger.debug('Installing package %s from deb file %s', package_name, str(deb_path))
    stop_service()
    sp.check_call(['dpkg', '--purge', package_name])
    sp.check_call(['dpkg', '--install', deb_path])
    installed_binary = find_binary_installed_by_deb(package_name)
    if os.path.exists(c.BINARY_PATH):
        os.remove(c.BINARY_PATH)
    os.symlink(installed_binary, c.BINARY_PATH)
    start_service()
    os.remove(deb_path)

def install_tarball_from_url(url, sha256_url, chain_name):
    tarball_response = requests.get(url, allow_redirects=True, timeout=None)
    tarball_path = Path(c.HOME_PATH, url.split('/')[-1])
    if tarball_response.status_code != 200:
        raise ValueError(f"Download binary failed with: {tarball_response.text}. Check 'binary-url'!")

    # TODO: Add sha256 checksum verification here in case some future chain provides them    
    with open(tarball_path, 'wb') as f:
        f.write(tarball_response.content)

    stop_service()
    tarball = Tarball(tarball_path, chain_name)
    tarball.extract_resources_from_tarball()
    start_service()

def parse_install_urls(binary_urls: str, sha256_urls: str) -> list:
    binary_url_list = binary_urls.split()
    sha256_url_list = sha256_urls.split()
    url_pairs = []
    for i in range(max(len(binary_url_list), len(sha256_url_list))):
        binary_url = binary_url_list[i] if i < len(binary_url_list) else ""
        sha256_url = sha256_url_list[i] if i < len(sha256_url_list) else ""
        url_pairs.append((binary_url, sha256_url))
    return url_pairs


def install_binaries_from_urls(binary_urls: str, sha256_urls: str) -> None:
    logger.debug('Installing multiple binaries!')
    binary_sha256_pairs = parse_install_urls(binary_urls, sha256_urls)
    responses = []
    for binary_url, sha256_url in binary_sha256_pairs:
        logger.debug("Download binary from URL: %s", binary_url)
        # Download polkadot binary to memory and compute sha256 hash
        response = requests.get(binary_url, allow_redirects=True, timeout=None)
        if response.status_code != 200:
            raise ValueError(f"Download binary failed with: {response.text}. Check 'binary-url'!")
        binary_hash = hashlib.sha256(response.content).hexdigest()
        # TODO: keeping the binary name won't work for the charm if it's not exactly 'polkadot', adjust this if more chains start using multiple binaries
        binary_name = binary_url.split('/')[-1]
        responses += [(binary_url, sha256_url, response, binary_name, binary_hash)]
    perform_sha256_checksums(responses, sha256_urls)
    stop_service()
    for binary_url, _, response, binary_name, _ in responses:
        logger.debug("Unpack binary downloaded from: %s", binary_url)
        binary_path = c.HOME_PATH / binary_name
        with open(binary_path, 'wb') as f:
            f.write(response.content)
            sp.run(['chown', f'{c.USER}:{c.USER}', binary_path], check=False)
            sp.run(['chmod', '+x', binary_path], check=False)
    start_service()


def install_binary_from_url(url: str, sha256_url: str) -> None:
    logger.debug("Install binary from URL: %s", url)
    # Download polkadot binary to memory and compute sha256 hash
    binary_response = requests.get(url, allow_redirects=True, timeout=None)
    if binary_response.status_code != 200:
        raise ValueError(f"Download binary failed with: {binary_response.text}. Check 'binary-url'!")
    if sha256_url:
        binary_hash = hashlib.sha256(binary_response.content).hexdigest()
        perform_sha256_checksum(binary_hash, sha256_url)
    stop_service()
    with open(c.BINARY_PATH, 'wb') as f:
        f.write(binary_response.content)
        sp.run(['chown', f'{c.USER}:{c.USER}', c.BINARY_PATH], check=False)
        sp.run(['chmod', '+x', c.BINARY_PATH], check=False)
    start_service()


def perform_sha256_checksums(responses: list, sha256_urls: str) -> None:
    if len(sha256_urls.split()) == 1:
        sha256_response = get_sha256_response(sha256_urls)
        sha256_target_map = {}
        for binary_hash_pair in sha256_response.text.split('\n'):
            if binary_hash_pair:
                binary_name = binary_hash_pair.split()[1]
                sha256 = binary_hash_pair.split()[0]
                sha256_target_map[binary_name] = sha256
        for _, _, _, binary_name, binary_hash in responses:
            try:
                target_hash = sha256_target_map[binary_name]
            except KeyError:
                raise ValueError(f"Could not find target hash for {binary_name}. Was the correct sha256 url provided?")
            # Raise error if hash is incorrect
            if binary_hash != target_hash:
                raise ValueError(f"Binary {binary_name} downloaded has wrong hash!")
    else:
        for _, sha256_url, _, _, binary_hash in responses:
            if sha256_url:
                perform_sha256_checksum(binary_hash, sha256_url)


def perform_sha256_checksum(binary_hash: str, sha256_url: str) -> None:
    sha256_response = get_sha256_response(sha256_url)
    data = sha256_response.text
    target_hash = data.split(' ')[0]
    # Raise error if hash is incorrect
    if (binary_hash != target_hash):
        raise ValueError("Binary downloaded has wrong hash!")


def get_sha256_response(sha256_url: str) -> requests.Response:
    sha256_response = requests.get(sha256_url, allow_redirects=True, timeout=None)
    if len(sha256_response.content) > 1024:  # 1 KB
        raise ValueError("Sha256 file is larger than 1KB. Was the correct sha256 url provided?")
    return sha256_response


def download_chain_spec(url, filename):
    if not c.CHAIN_SPEC_PATH.exists():
        c.CHAIN_SPEC_PATH.mkdir(parents=True)
    try:
        download_file(url, Path(c.CHAIN_SPEC_PATH, filename))
    except ValueError as e:
        logger.error(f'Failed to download chain spec: {e}')
        raise e


def download_wasm_runtime(url):
    if not url:
        logger.debug('No wasm runtime url provided, skipping download')
        return
    filepath = Path(c.WASM_PATH, url.split('/')[-1])
    if not c.WASM_PATH.exists():
        c.WASM_PATH.mkdir(parents=True)
    try:
        download_file(url, Path(c.WASM_PATH, filepath))
    except ValueError as e:
        logger.error(f'Failed to download wasm runtime: {e}')
        raise e
    tarball = open_tarfile(Path(c.WASM_PATH, filepath), mode='r')
    files = glob.glob(f'{c.WASM_PATH}/*.wasm')
    for f in files:
        os.remove(f)
    tarball.extractall(c.WASM_PATH)
    tarball.close()
    sp.run(['rm', filepath], check=False)
    sp.run(['chown', '-R', f'{c.USER}:{c.USER}', c.WASM_PATH], check=False)


def download_file(url, filepath):
    logger.debug(f'Downloading file from {url} to {filepath}')
    response = requests.get(url, timeout=None)
    if response.status_code != 200:
        raise ValueError(f"Download binary failed with: {response.text}")
    with open(filepath, 'wb') as f:
        f.write(response.content)
    sp.run(['chown', '-R', f'{c.USER}:{c.USER}', c.WASM_PATH], check=False)


def setup_group_and_user():
    sp.run(['addgroup', '--system', c.USER], check=False)
    sp.run(['adduser', '--system', '--home', c.HOME_PATH, '--disabled-password', '--ingroup', c.USER, c.USER], check=False)
    sp.run(['chown', f'{c.USER}:{c.USER}', c.HOME_PATH], check=False)
    sp.run(['chmod', '700', c.HOME_PATH], check=False)


def create_env_file_for_service():
    with open(f'/etc/default/{c.USER}', 'w', encoding='utf-8') as f:
        f.write(f'{c.USER.upper()}_CLI_ARGS=\'\'')


def install_service_file(source_path):
    target_path = Path(f'/etc/systemd/system/{c.USER}.service')
    shutil.copyfile(source_path, target_path)
    sp.run(['systemctl', 'daemon-reload'], check=False)


def update_service_args(service_args):
    args = f"{c.USER.upper()}_CLI_ARGS='{service_args}'"

    with open(f'/etc/default/{c.USER}', 'w', encoding='utf-8') as f:
        f.write(args + '\n')
    sp.run(['systemctl', 'restart', f'{c.USER}.service'], check=False)


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
    if c.BINARY_PATH.exists():
        command = [c.BINARY_PATH, "--version"]
        output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        version = re.search(r'([\d.]+)', output).group(1)
        return version
    return ""


def get_binary_md5sum() -> str:
    if c.BINARY_PATH.exists():
        command = ['md5sum', c.BINARY_PATH]
        md5sum_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        return md5sum_output.split(' ')[0]  # Output includes path of binary, which we skip including
    return ""


def get_binary_last_changed() -> str:
    if c.BINARY_PATH.exists():
        command = ['stat', c.BINARY_PATH]
        stat_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        stat_split = re.split('Change: ', stat_output)[1].split(' ')
        date = stat_split[0]
        timestamp = stat_split[1].split('.')[0]
        return date + ' ' + timestamp  # TODO: make this check if system time is in UTC, and print that?
    return ""


def restart_service():
    sp.run(['systemctl', 'restart', f'{c.USER}.service'], check=False)


def start_service():
    # TODO: remove chown and chmod from here? Runs in the install hook already
    sp.run(['chown', f'{c.USER}:{c.USER}', c.BINARY_PATH], check=False)
    sp.run(['chmod', '+x', c.BINARY_PATH], check=False)
    sp.run(['systemctl', 'start', f'{c.USER}.service'], check=False)


def stop_service():
    sp.run(['systemctl', 'stop', f'{c.USER}.service'], check=False)


def service_started(iterations: int = 3) -> bool:
    for _ in range(iterations):
        service_status = os.system('service polkadot status')
        if service_status == 0:
            return True
        time.sleep(4)
    return False


def write_node_key_file(key):
    with open(c.NODE_KEY_PATH, "w", encoding='utf-8') as f:
        f.write(key)
    sp.run(['chown', f'{c.USER}:{c.USER}', c.NODE_KEY_PATH], check=False)
    sp.run(['chmod', '0600', c.NODE_KEY_PATH], check=False)


def get_disk_usage(path: Path) -> str:
    if not path.exists():
        return ''
    command = ['du', str(path), '-hs']
    output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8')
    try:
        size = re.search(r'(\d+(\.\d+)?[GKMT])', output).group(1)
        return size
    except AttributeError as e:
        logger.warning("Couldn't parse return from 'du' command: %s", {e})
        return "Error parsing disk usage"


def get_chain_disk_usage() -> str:
    if c.DB_CHAIN_PATH.exists():
        return get_disk_usage(c.DB_CHAIN_PATH)
    return ""


def get_relay_disk_usage() -> str:
    if c.DB_RELAY_PATH.exists():
        return get_disk_usage(c.DB_RELAY_PATH)
    return ""


def get_service_args() -> str:
    command = ['cat', f'/etc/default/{c.USER}']
    cat_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
    return cat_output.split('=')[1]  # cat:ed file includes the env variable name, which we skip including


def get_polkadot_process_id() -> str:
    command = ['pgrep', f'{c.USER}']
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
    # TODO: should both of these be required to satisfy the node being a parachain, or is one enough?
    if c.DB_CHAIN_PATH.exists() and c.DB_RELAY_PATH.exists():
        return True
    if c.BINARY_PATH.exists():
        command = f'.{c.BINARY_PATH} --help | grep -i "\-\-collator"'
        output = sp.run(command, stdout=sp.PIPE, cwd='/', shell=True, check=False)
        if output.returncode == 0:
            return True
    return False


def get_relay_for_parachain() -> str:
    if not is_parachain_node():
        return 'Error, this is not a parachain'
    try:
        chains_dir = Path(c.DB_RELAY_PATH, 'chains')
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
        return 'Error finding Relay Chain DB directory'
    except Exception as e:
        logger.warning(e)
        return 'Error finding Relay Chain'


def get_wasm_info() -> str:
    if c.WASM_PATH.exists():
        files = list(c.WASM_PATH.glob('*.wasm'))
        if not files:
            return "No wasm files found in ~/wasm directory"
        files = [str(f.name) for f in files]
        return ', '.join(files)
    return "~/wasm directory not found"


def get_client_binary_help_output() -> str:
    if c.BINARY_PATH.exists():
        command = f'.{c.BINARY_PATH} --help'
        process = sp.run(command, stdout=sp.PIPE, cwd='/', shell=True, check=False)
        if process.returncode == 0:
            return process.stdout.decode('utf-8').strip()
        return "Could not parse client binary '--help' command"
    return "Client binary not found"
