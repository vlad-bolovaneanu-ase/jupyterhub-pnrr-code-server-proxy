from shutil import which
import os
from subprocess import run
from tempfile import mkstemp

_HERE = os.path.dirname(os.path.abspath(__file__))


def which_code_server():
    command = which('code-server')
    if not command:
        raise FileNotFoundError('Could not find executable code-server!')
    return command


def setup_code_server():
    which_code_server()
    proxy_config_dict = {
        "new_browser_window": True,
        "timeout": 30,
        "launcher_entry": {
            "enabled": True,
            "title": "VSCode Web IDE",
            "path_info": "vscode",
            "icon_path": os.path.join(_HERE, 'icons/vscode.svg')
            }
        }

    try:
        code_server_port = int(os.environ.get('CODE_PORT', '13777'))
    except Exception:
        code_server_port = 13777

    jh_generic_user = os.environ.get('NB_USER', 'jovyan')
    jh_username = os.environ.get("JUPYTERHUB_USER", None)

    proxy_command = ["/bin/bash", "start_proxy.sh", code_server_port, jh_username, jh_generic_user]

    return proxy_config_dict.update({"command": proxy_command})
