import os
import json
import glob
import tempfile
import shutil
import logging
import requests
import subprocess as sp
from pathlib import Path
from tarfile import open as open_tarfile


logger = logging.getLogger(__name__)


def download_chain_spec(url: str, filename: Path, spec_dir: Path, owner: str) -> str:
    """Download a chain spec file from a given URL to a given filepath."""
    if not spec_dir.exists():
        spec_dir.mkdir(parents=True)
    download_file(url, Path(spec_dir, f"{filename}"), owner)
    validate_file(Path(spec_dir, filename), file_type='json')
    return Path(spec_dir, filename)


def validate_file(filename: Path, file_type: str):
    if file_type == 'json':
        try:
            file_obj = open(filename, 'r')
            _ = json.load(file_obj)
        except json.JSONDecodeError as e:
            raise ValueError(f"Validating chain spec {filename} failed with error: {e}")

def download_wasm_runtime(url: str, wasm_path: Path, owner: str)-> None:
    if not url:
        logger.debug('No wasm runtime url provided, skipping download')
        return
    filename = Path(url.split('/')[-1])
    if not filename.name.endswith('.tar.gz') and not filename.suffix == '.wasm':
        raise ValueError(f'Invalid file format provided for wasm-runtime-url: {filename.name}')
    if not wasm_path.exists():
        wasm_path.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            download_file(url, Path(temp_dir, filename), owner)
        except ValueError as e:
            logger.error(f'Failed to download wasm runtime: {e}')
            raise e
        if filename.name.endswith('.tar.gz'):
            tarball = open_tarfile(Path(temp_dir, filename), mode='r')
            tarball.extractall(temp_dir)
            tarball.close()
        files = glob.glob(f'{wasm_path}/*.wasm')
        for f in files:
            os.remove(f)
        files_in_temp_dir = glob.glob(f'{temp_dir}/*')
        logger.debug('Files in temp_dir: %s', str(files_in_temp_dir))
        wasm_files = glob.glob(f'{temp_dir}/*.wasm')
        for wasm_file in wasm_files:
            shutil.move(wasm_file, wasm_path)
    sp.run(['chown', '-R', f'{owner}:{owner}', wasm_path], check=False)


def download_file(url: str, filepath: Path, owner: str) -> None:
    """Download a file from a given URL to a given filepath."""
    logger.debug(f'Downloading file from {url} to {filepath}')
    response = requests.get(url, timeout=None)
    if response.status_code != 200:
        raise ValueError(f"Download of file failed with: {response.text}")
    with open(filepath, 'wb') as f:
        f.write(response.content)
    sp.run(['chown', '-R', f'{owner}:{owner}', filepath], check=False)
