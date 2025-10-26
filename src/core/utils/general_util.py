import re
import logging
import subprocess as sp
from typing import Union
from pathlib import Path

logger = logging.getLogger(__name__)

def install_node_exporter():
    try:
        packages = ['prometheus-node-exporter']
        command = ["sudo", "apt", "install", "-y"]
        command.extend(packages)
        sp.run(command, check=True)
    except sp.CalledProcessError as e:
        logger.error(f"failed to install prometheus-node-export: {e}")
        raise e

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
    
    
def get_binary_md5sum(binary_path: Union[Path, str]) -> str:
    binary_path = binary_path if isinstance(binary_path, Path) else Path(binary_path)
    if binary_path.exists():
        command = ['md5sum', binary_path]
        md5sum_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        return md5sum_output.split(' ')[0]  # Output includes path of binary, which we skip including
    return ""


def get_binary_last_changed(binary_path: Union[Path, str]) -> str:
    binary_path = binary_path if isinstance(binary_path, Path) else Path(binary_path)
    if binary_path.exists():
        command = ['stat', binary_path]
        stat_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
        stat_split = re.split('Change: ', stat_output)[1].split(' ')
        date = stat_split[0]
        timestamp = stat_split[1].split('.')[0]
        return date + ' ' + timestamp  # TODO: make this check if system time is in UTC, and print that?
    return ""

def get_process_id(process_name: str) -> str:
    command = ['pgrep', f'{process_name}']
    pgrep_output = sp.run(command, stdout=sp.PIPE, check=False).stdout.decode('utf-8').strip()
    return pgrep_output

def get_chain_name_from_service_args(service_args: str):
    """Get the value of '--chain' current set in the service-args config parameter."""
    try:
        service_args_list = re.split(' +|=', service_args)
        i = service_args_list.index('--chain')
        return service_args_list[i + 1]
    except ValueError:
        return ''


def get_process_cmdline(process_name: str) -> str:
    proc_id = get_process_id(process_name)
    if proc_id:
        command = f'cat /proc/{proc_id}/cmdline'  # Uses NUL bytes as delimiter
        cat_output = sp.run(command, stdout=sp.PIPE, shell=True, check=False).stdout.decode().split('\x00')
        str_output = ' '.join(cat_output)
        return str_output
    return ""

def split_session_key(key: str) -> list:
    # Check that the key is a valid hex string
    if not key.startswith('0x') or not all(c in '0123456789abcdef' for c in key[2:]):
        raise ValueError("Invalid session key")
    # Remove the initial '0x'
    key_without_prefix = key[2:]
    # Split the key into chunks of 64 characters
    chunks = [key_without_prefix[i:i+64] for i in range(0, len(key_without_prefix), 64)]
    # The 'beefy' key can be longer than 64 characters resulting in an extra chunk with the remaining characters
    if len(chunks[-1]) < 64:
        # Add the last chunk to the previous one if it's shorter than 64 characters
        chunks[-2] += chunks[-1]
        # Remove the last chunk which should now be empty
        chunks.pop()

    # Add '0x' to each chunk
    keys_with_prefix = [f"0x{chunk}" for chunk in chunks]

    return keys_with_prefix


def name_session_keys(chain_name: str, keys: list) -> dict:
    """
    Map the session keys in 'keys' to their names in the chain 'chain_name'.
    It's needed for extrinsics like 'session.set_keys()'
    """
    if 'enjin' in chain_name.lower():
        # Enjin ecosystem
        if len(keys) == 6:
            # Enjin relay chain
            return {
                'grandpa': keys[0],
                'babe': keys[1],
                'im_online': keys[2],
                'para_validator': keys[3],
                'para_assignment': keys[4],
                'authority_discovery': keys[5],
            }
        elif len(keys) == 2:
            # Enjin parachain
            return {
                'aura': keys[0],
                'pools': keys[1],
            }
        else:
            raise ValueError(f"Enjin chain with {len(keys)} session keys not supported")
    elif len(keys) == 6:
        # Relay chain in Polkadot ecosystem
        return {
            'grandpa': keys[0],
            'babe': keys[1],
            'para_validator': keys[2],
            'para_assignment': keys[3],
            'authority_discovery': keys[4],
            'beefy': keys[5],
        }
    elif len(keys) == 1:
        # Parachain in Polkadot ecosystem
        return {
            'aura': keys[0],
        }
    else:
        raise ValueError(f"Mismatch between chain {chain_name} and number of session keys ({len(keys)})")
    
def get_wasm_info(wasm_path: Path) -> str:
    if wasm_path.exists():
        files = list(wasm_path.glob('*.wasm'))
        if not files:
            return "No wasm files found in ~/wasm directory"
        files = [str(f.name) for f in files]
        return ', '.join(files)
    return "~/wasm directory not found"

def get_readme() -> str:
    path = Path('README.md')
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    logger.warning("README file not found.")
    return ""

def get_client_binary_help_output(help_command: str) -> str:
    try:
        process = sp.run(help_command, stdout=sp.PIPE, cwd='/', shell=True, check=False)
        if process.returncode == 0:
            return process.stdout.decode('utf-8').strip()
        return "Could not parse client binary '--help' command"
    except Exception as e:
        logger.error(f"Error occurred while getting client binary help output: {e}")
        return "Error occurred while getting client binary help output"


def write_node_key_file(key_path: Union[Path, str], key: str, owner: str) -> None:
    with open(key_path, "w", encoding='utf-8') as f:
        f.write(key)
    sp.run(['chown', f'{owner}:{owner}', key_path], check=False)
    sp.run(['chmod', '0600', key_path], check=False)


def get_relay_for_parachain(relay_db_dir: Path) -> str:
    try:
        chains_dir = Path(relay_db_dir, 'chains')
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
