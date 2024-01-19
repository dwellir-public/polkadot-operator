import subprocess as sp
from tarfile import open as open_tarfile
from pathlib import Path
import utils
import os


class Tarball:
    def __init__(self, tarball_path, chain_name):
        self.chain_name = chain_name
        self.tarball_path = tarball_path

    def extract_resources_from_tarball(self):
        tarball = open_tarfile(self.tarball_path, mode='r')

        if self.chain_name == 'goldberg': # Avail
            if 'data-avail' in tarball.getnames():
                member = tarball.getmember('data-avail')
                if member.isfile():
                    tarball.extract(member, path=utils.HOME_PATH)
                    sp.run(['mv', utils.HOME_PATH/'data-avail', utils.BINARY_PATH, '--force'])
                    sp.run(['rm', self.tarball_path])
                    sp.run(['chown', f'{utils.USER}:{utils.USER}', utils.BINARY_PATH])
                else:
                    raise ValueError(f"Expected client binary 'data-avail' in tarball is not a file.")
            else:
                raise ValueError(f"Expected client binary 'data-avail' not found in tarball!")
        else:
            raise ValueError(f'Could not extract tarball since {self.chain_name} lacks a tarball handler!')
        