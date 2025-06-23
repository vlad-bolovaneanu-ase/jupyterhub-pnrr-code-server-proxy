import os
import sys
import socket
import logging

from contextlib import closing
from shutil import which
from subprocess import check_output
# from tempfile import mkstemp

_HERE = os.path.dirname(os.path.abspath(__file__))


def which_code_server():
    command = which('code-server')
    if not command:
        raise FileNotFoundError('Could not find executable code-server!')
    return command


def setup_logger():
    logger = logging.getLogger("jupyter_code_server_proxy")
    logger.setLevel(logging.INFO)
    if len(logger.handlers) == 0:
        formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        file_handler = logging.FileHandler("/opt/code-server/code_server_proxy.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]
    

def is_port_in_use(port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


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
    logger = setup_logger()
    logger.info("Hello!")
    try:
        code_server_port = int(os.environ.get('CODE_PORT', None))
        if is_port_in_use(code_server_port):
            code_server_port = find_free_port()
            logger.info(f"Use {code_server_port} as a random available port for code-server.")
        logger.info(f"Use {code_server_port} as the port assigned by the user for code-server.")
    except Exception:
        code_server_port = find_free_port()
        logger.info(f"Use {code_server_port} as a random available port for code-server.")

    try:
        flask_proxy_port = int(os.environ.get('CODE_PROXY_PORT', None))
        if is_port_in_use(flask_proxy_port):
            flask_proxy_port = find_free_port()
            logger.info(f"Use {flask_proxy_port} as a random available port for flask proxy.")
        logger.info(f"Use {flask_proxy_port} as the port assigned by the user for flask proxy.")
    except Exception:
        flask_proxy_port = find_free_port()
        logger.info(f"Use {flask_proxy_port} as a random available port for flaks proxy.")

    jh_generic_user = os.environ.get('NB_USER', 'jovyan')
    jh_username = os.environ.get("JUPYTERHUB_USER", None)

    for handler in logger.handlers:
        handler.flush()
        handler.close()

    if jh_username is None:
        logger.error(f"Expected to be provided the username in 'JUPYTERHUB_USER' env var. Available env vars: {','.join(os.environ.keys())}.")
        raise ValueError("Cannot find jupyterhub username.")
    
    for handler in logger.handlers:
        handler.flush()
        handler.close()

    proxy_command = ["/bin/bash", "start_proxy.sh", str(code_server_port), jh_username, jh_generic_user, str(flask_proxy_port)]
    logger.info(f"Start command: {' '.join(proxy_command)}.")
    proxy_config_dict.update({"command": proxy_command})

    return proxy_config_dict


if __name__ == "__main__":
    config_dict = setup_code_server()
    check_output(config_dict["command"])
