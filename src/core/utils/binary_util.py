import os
import re
import shutil
import logging
import hashlib
import time
import requests
import subprocess as sp
from pathlib import Path
from core.utils.docker import Docker
from core.utils.tarball import Tarball
from core import constants as c
from core.utils import general_util

logger = logging.getLogger(__name__)

def install_fuse_overlay_fs() -> None:
    try:
        sp.run(['sudo', 'apt', 'install', '-y', 'fuse-overlay-fs'], check=True)
    except sp.CalledProcessError as e:
        logger.error(f"failed to install fuse-oveerlay-fs: {e}")
        raise e

def install_docker_runtime() -> None:
    try:
        sp.check_call(["docker", "--version"])
    except FileNotFoundError:
        install_fuse_overlay_fs()
        c.DOCKER_DEAMON_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        c.DOCKER_DEAMON_CONFIG_PATH.write_text(c.DOCKER_DEAMON_JSON_CONFIG)
        sp.run(['curl', '-fsSL', 'https://get.docker.com', '-o', 'get-docker.sh'], check=False)
        sp.run(['sh', 'get-docker.sh'], check=False)
        sp.run(['usermod', '-aG', 'docker', c.USER], check=False)

def install_binary(chain_name: str, binary_url: str, binary_sha256_url: str | None = None) -> None:
    if binary_url.endswith('.deb'):
        install_deb_from_url(binary_url)
    elif binary_url.endswith('.tar.gz') or binary_url.endswith('.tgz'):
        install_tarball_from_url(binary_url, chain_name)
    elif len(binary_url.split()) > 1:
        install_binaries_from_urls(binary_url, binary_sha256_url, chain_name)
    else:
        install_binary_from_url(binary_url, binary_sha256_url)


def install_binary_from_docker_container(chain_name: str, docker_tag: str) -> None:
        install_docker_runtime()
        Docker(chain_name, docker_tag).extract_resources_from_docker()


def find_binary_installed_by_deb(package_name: str, ) -> str:
    files = sp.check_output(['dpkg', '-L', package_name]).decode().split('\n')[:-1]
    bin_files = [file for file in files if file.startswith('/bin/')]
    logger.debug('Found files in /bin/ %s', str(bin_files))
    if len(bin_files) > 1:
        raise Exception(f'Found more than one file installed in /bin/ by package {package_name}. Cannot be sure which one to use.')
    return bin_files[0]


def install_deb_from_url(url: str) -> None:
    deb_response = requests.get(url, allow_redirects=True, timeout=None)
    deb_path = Path(c.HOME_DIR, url.split('/')[-1])
    with open(deb_path, 'wb') as f:
        f.write(deb_response.content)
    package_name = sp.check_output(['dpkg-deb', '-f', deb_path, 'Package']).decode('utf-8').strip()
    logger.debug('Installing package %s from deb file %s', package_name, str(deb_path))

    stop_service()
    sp.check_call(['dpkg', '--purge', package_name])
    sp.check_call(['dpkg', '--install', deb_path])
    installed_binary = find_binary_installed_by_deb(package_name)
    if os.path.exists(c.BINARY_FILE):
        os.remove(c.BINARY_FILE)
    os.symlink(installed_binary, c.BINARY_FILE)
    os.remove(deb_path)


def install_tarball_from_url(url, chain_name):
    tarball_response = requests.get(url, allow_redirects=True, timeout=None)
    tarball_path = Path(c.HOME_DIR, url.split('/')[-1])
    if tarball_response.status_code != 200:
        raise ValueError(f"Download binary failed with: {tarball_response.text}. Check 'binary-url'!")

    # TODO: Add sha256 checksum verification here in case some future chain provides them
    with open(tarball_path, 'wb') as f:
        f.write(tarball_response.content)

    stop_service()
    tarball = Tarball(tarball_path, chain_name)
    tarball.extract_resources_from_tarball()

def parse_install_urls(binary_urls: str, sha256_urls: str) -> list:
    binary_url_list = binary_urls.split()
    sha256_url_list = sha256_urls.split()
    url_pairs = []
    for i in range(max(len(binary_url_list), len(sha256_url_list))):
        binary_url = binary_url_list[i] if i < len(binary_url_list) else ""
        sha256_url = sha256_url_list[i] if i < len(sha256_url_list) else ""
        url_pairs.append((binary_url, sha256_url))
    return url_pairs


def install_binaries_from_urls(binary_urls: str, sha256_urls: str, chain_name: str) -> None:
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
        # Get correct execute worker binary name
        if 'execute-worker' in binary_url.split('/')[-1]:
            if chain_name in c.EXECUTE_WORKER_BINARY_FILE:
                binary_name = c.EXECUTE_WORKER_BINARY_FILE[chain_name]
            else:
                binary_name = c.EXECUTE_WORKER_BINARY_FILE['default']
        # Get correct prepare worker binary name
        elif 'prepare-worker' in binary_url.split('/')[-1]:
            if chain_name in c.PREPARE_WORKER_BINARY_FILE:
                binary_name = c.PREPARE_WORKER_BINARY_FILE[chain_name]
            else:
                binary_name = c.PREPARE_WORKER_BINARY_FILE['default']
        else:
            binary_name = c.BINARY_FILE
        responses += [(binary_url, sha256_url, response, binary_name, binary_hash)]
    
    perform_sha256_checksums(responses, sha256_urls)
    stop_service()
    for binary_url, _, response, binary_name, _ in responses:
        logger.debug("Unpack binary downloaded from: %s", binary_url)
        binary_path = c.HOME_DIR / binary_name
        with open(binary_path, 'wb') as f:
            f.write(response.content)
            sp.run(['chown', f'{c.USER}:{c.USER}', binary_path], check=False)
            sp.run(['chmod', '+x', binary_path], check=False)


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
    with open(c.BINARY_FILE, 'wb') as f:
        f.write(binary_response.content)
        sp.run(['chown', f'{c.USER}:{c.USER}', c.BINARY_FILE], check=False)
        sp.run(['chmod', '+x', c.BINARY_FILE], check=False)

def uninstall_binary() -> None:
    if is_installed():
        if service_started():
            stop_service()
        os.remove(c.BINARY_FILE)
    service_file = Path(f'/etc/systemd/system/{c.SERVICE_NAME}.service')
    if service_file.exists():
        os.remove(service_file)
        sp.run(['systemctl', 'daemon-reload'], check=False)

def is_installed() -> bool:
    return c.BINARY_FILE.exists()

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
                raise ValueError(f"Could not find target hash for {binary_name}. Was the correct sha256 URL provided?")
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

def create_env_file_for_service():
    with open(f'/etc/default/{c.USER}', 'w', encoding='utf-8') as f:
        f.write(f'{c.USER.upper()}_CLI_ARGS=\'\'')


def install_service_file(source_path):
    target_path = Path(f'/etc/systemd/system/{c.USER}.service')
    shutil.copyfile(source_path, target_path)
    sp.run(['systemctl', 'daemon-reload'], check=False)


def render_service_argument_file(service_args):
    return f"{c.USER.upper()}_CLI_ARGS='{service_args}'\n"


def arguments_differ_from_disk(service_args):
    try:
        with open(f'/etc/default/{c.USER}', 'r', encoding='utf-8') as f:
            args = f.read()
        return args != render_service_argument_file(service_args)
    except FileNotFoundError:
        return True


def get_service_args() -> str:
    try:
        command = ['cat', f'/etc/default/{c.USER}']
        cat_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        return cat_output.split('=')[1]  # cat:ed file includes the env variable name, which we skip including
    except Exception as e:
        logger.error("Couldn't get service args: %s", {e})
        return ""


def update_service_args(service_args):
    with open(f'/etc/default/{c.USER}', 'w', encoding='utf-8') as f:
        f.write(render_service_argument_file(service_args))


def is_relay_chain_node() -> bool:
    return not is_parachain_node()


def is_parachain_node() -> bool:
    # TODO: should both of these be required to satisfy the node being a parachain, or is one enough?
    if c.DB_CHAIN_DIR.exists() and c.DB_RELAY_DIR.exists():
        return True
    if c.BINARY_FILE.exists():
        command = f'.{c.BINARY_FILE} --help | grep -i "\-\-collator"'
        output = sp.run(command, stdout=sp.PIPE, cwd='/', shell=True, check=False)
        if output.returncode == 0:
            return True
    return False


def get_relay_for_parachain() -> str:
    if not is_parachain_node():
        return 'Error, this is not a parachain'
    return general_util.get_relay_for_parachain(c.DB_RELAY_DIR)


def get_binary_version() -> str:
    """ Returns the version of the binary client by checking the '--version' flag. """
    logger.debug("Getting binary version from client binary.")
    try:
        command = [c.BINARY_FILE, "--version"]
        output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        version = re.search(r'([\d.]+)', output).group(1)
        return version
    except (sp.SubprocessError, IndexError, AttributeError) as e:
        logger.error("Couldn't get binary version: %s", {e})


def get_binary_md5sum() -> str:
    return general_util.get_binary_md5sum(c.BINARY_FILE)


def get_binary_last_changed() -> str:
    if c.BINARY_FILE.exists():
        command = ['stat', c.BINARY_FILE]
        stat_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        stat_split = re.split('Change: ', stat_output)[1].split(' ')
        date = stat_split[0]
        timestamp = stat_split[1].split('.')[0]
        return date + ' ' + timestamp  # TODO: make this check if system time is in UTC, and print that?
    return ""


def restart_service():
    sp.run(['systemctl', 'restart', f'{c.SERVICE_NAME}.service'], check=False)


def start_service():
    # TODO: remove chown and chmod from here? Runs in the install hook already
    sp.run(['chown', f'{c.USER}:{c.USER}', c.BINARY_FILE], check=False)
    sp.run(['chmod', '+x', c.BINARY_FILE], check=False)
    sp.run(['systemctl', 'start', f'{c.SERVICE_NAME}.service'], check=False)
    sp.run(['systemctl', 'enable', f'{c.SERVICE_NAME}.service'], check=False)


def stop_service():
    sp.run(['systemctl', 'stop', f'{c.SERVICE_NAME}.service'], check=False)
    sp.run(['systemctl', 'disable', f'{c.SERVICE_NAME}.service'], check=False)


def service_started(iterations: int = 6) -> bool:
    """Checks if the service is running by running the the 'service status' command."""
    for _ in range(iterations):
        service_status = os.system(f'service {c.SERVICE_NAME} status')
        if service_status == 0:
            return True
        if iterations > 1:
            time.sleep(1)
    return False


def generate_node_key():
    if c.BINARY_FILE.exists():
        command = [c.BINARY_FILE, 'key', 'generate-node-key', '--file', c.NODE_KEY_FILE]

        # This is to make it work on Enjin relay deployments
        logger.debug("Getting binary version from client binary to check if it is Enjin.")
        get_version_command = [c.BINARY_FILE, "--version"]
        output = sp.run(get_version_command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip().lower()
        if "enjin" in output:
            command += ['--chain', 'enjin']

        sp.run(command, check=False)
        sp.run(['chown', f'{c.USER}:{c.USER}', c.NODE_KEY_FILE], check=False)
        sp.run(['chmod', '0600', c.NODE_KEY_FILE], check=False)
    else:
        raise ValueError("No binary file found to generate node key. Please check your configuration.")


def get_chain_disk_usage() -> str:
    if c.DB_CHAIN_DIR.exists():
        return general_util.get_disk_usage(c.DB_CHAIN_DIR)
    return ""


def get_relay_disk_usage() -> str:
    if c.DB_RELAY_DIR.exists():
        return general_util.get_disk_usage(c.DB_RELAY_DIR)
    return ""

def get_client_binary_help_output() -> str:
    if c.BINARY_FILE.exists():
        command = f'.{c.BINARY_FILE} --help'
        process = sp.run(command, stdout=sp.PIPE, cwd='/', shell=True, check=False)
        if process.returncode == 0:
            return process.stdout.decode('utf-8').strip()
        return "Could not parse client binary '--help' command"
    return "Client binary not found"


def get_binary_path() -> str:
    return str(c.BINARY_FILE)
