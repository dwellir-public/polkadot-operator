import subprocess as sp
from core import constants as c

def setup_group_and_user():
    sp.run(['addgroup', '--system', c.USER], check=False)
    sp.run(['adduser', '--system', '--home', c.HOME_DIR, '--disabled-password', '--ingroup', c.USER, c.USER], check=False)
    sp.run(['chown', f'{c.USER}:{c.USER}', c.HOME_DIR], check=False)
    sp.run(['chmod', '700', c.HOME_DIR], check=False)
