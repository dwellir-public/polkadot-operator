import subprocess as sp
from tarfile import open as open_tarfile

from core import runtime as r


class Tarball:
    def __init__(self, tarball_path, chain_name):
        self.chain_name = chain_name
        self.tarball_path = tarball_path

    def extract_resources_from_tarball(self):
        tarball = open_tarfile(self.tarball_path, mode="r")

        if self.chain_name == "goldberg":  # Avail
            if "data-avail" in tarball.getnames():
                member = tarball.getmember("data-avail")
                if member.isfile():
                    tarball.extract(member, path=r.home_dir)
                    sp.run(["mv", r.home_dir / "data-avail", r.binary_file, "--force"])
                    sp.run(["rm", self.tarball_path])
                    sp.run(["chown", f"{r.user}:{r.user}", r.binary_file])
                else:
                    raise ValueError("Expected client binary 'data-avail' in tarball is not a file.")
            else:
                raise ValueError("Expected client binary 'data-avail' not found in tarball!")
        else:
            raise ValueError(f"Could not extract tarball since {self.chain_name} lacks a tarball handler!")
