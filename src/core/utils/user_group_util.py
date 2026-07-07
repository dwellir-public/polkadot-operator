import subprocess as sp

from core import runtime as r


def setup_group_and_user():
    sp.run(["addgroup", "--system", r.user], check=False)
    sp.run(["adduser", "--system", "--home", r.home_dir, "--disabled-password", "--ingroup", r.user, r.user], check=False)
    sp.run(["chown", f"{r.user}:{r.user}", r.home_dir], check=False)
    sp.run(["chmod", "700", r.home_dir], check=False)
