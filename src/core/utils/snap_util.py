import re
import logging
import subprocess as sp
from pathlib import Path
from core import constants as c
from core.utils.general_util import get_disk_usage

logger = logging.getLogger(__name__)

def write_node_key_file(key):
    with open(c.SNAP_NODE_KEY_FILE, "w", encoding='utf-8') as f:
        f.write(key)
    sp.run(['chmod', '0600', c.SNAP_NODE_KEY_FILE], check=False)

def generate_node_key():
    try:
        command = f'snap run {c.SNAP_BINARY} key generate-node-key --file {c.SNAP_NODE_KEY_FILE}'

        # This is to make it work on Enjin relay deployments
        logger.debug("Getting binary version from client binary to check if it is Enjin.")
        get_version_command = [c.SNAP_BINARY, "--version"]
        output = sp.run(get_version_command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip().lower()
        if "enjin" in output:
            command += ['--chain', 'enjin']

        sp.run(command, shell=True, check=False)
    except Exception as e:
        logger.error("Failed to generate node key: %s", e)
        raise ValueError("No binary file found to generate node key. Please check your configuration.")

def get_binary_version(app_name: str) -> str:
    """ Returns the version of the binary client by checking the '--version' flag. """
    logger.debug("Getting binary version from client binary.")
    try:
        command = ["snap", "run", app_name, "--version"]
        output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        version = re.search(r'([\d.]+)', output).group(1)
        return version
    except (sp.SubprocessError, IndexError, AttributeError) as e:
        logger.error("Couldn't get binary version: %s", {e})
    return ""

def get_chain_disk_usage() -> str:
    if c.SNAP_DB_CHAIN_DIR.exists():
        return get_disk_usage(c.SNAP_DB_CHAIN_DIR)
    return ""


def get_relay_disk_usage() -> str:
    if c.SNAP_DB_RELAY_DIR.exists():
        return get_disk_usage(c.SNAP_DB_RELAY_DIR)
    return ""

def validate_chain_type(chain_type: str) -> bool:
    return chain_type in ['parachain', 'relaychain', 'systemchain']

def is_parachain_node(app_name: str) -> bool:
    # TODO: should both of these be required to satisfy the node being a parachain, or is one enough?
    command = f'snap run {app_name} --help | grep -i "\-\-collator"'
    output = sp.run(command, stdout=sp.PIPE, shell=True, check=False)
    if output.returncode == 0:
        return True
    return False

def get_relay_for_parachain(chain_dir: Path) -> str:
    if not is_parachain_node():
        return 'Error, this is not a parachain'
    try:
        chains_dir = Path(chain_dir, 'chains')
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


def get_client_binary_help_output(app_name: str) -> str:
    command = f'snap run {app_name} --help'
    process = sp.run(command, stdout=sp.PIPE, shell=True, check=False)
    if process.returncode == 0:
        return process.stdout.decode('utf-8').strip()
    return "Client binary not found"
