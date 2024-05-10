import subprocess as sp
from tarfile import open as open_tarfile

import constants as c


class Tarball:
    def __init__(self, tarball_path, chain_name):
        self.chain_name = chain_name
        self.tarball_path = tarball_path

    def extract_resources_from_tarball(self):
        tarball = open_tarfile(self.tarball_path, mode='r')

        if self.chain_name == 'goldberg':  # Avail
            if 'data-avail' in tarball.getnames():
                member = tarball.getmember('data-avail')
                if member.isfile():
                    tarball.extract(member, path=c.HOME_DIR)
                    sp.run(['mv', c.HOME_DIR/'data-avail', c.BINARY_PATH_FILE, '--force'])
                    sp.run(['rm', self.tarball_path])
                    sp.run(['chown', f'{c.USER}:{c.USER}', c.BINARY_PATH_FILE])
                else:
                    raise ValueError("Expected client binary 'data-avail' in tarball is not a file.")
            else:
                raise ValueError("Expected client binary 'data-avail' not found in tarball!")
        else:
            raise ValueError(f'Could not extract tarball since {self.chain_name} lacks a tarball handler!')
