import logging.handlers
import re
import os
import logging

from shutil import which
import sys
# from tempfile import mkstemp

_HERE = os.path.dirname(os.path.abspath(__file__))

def which_code_server():
    command = which('code-server')
    if not command:
        raise FileNotFoundError('Could not find executable code-server!')
    return command

def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    if len(logger.handlers) == 0:
        formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        file_handler = logging.FileHandler("/tmp/code_server_proxy.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def setup_code_server():
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
    # _, socket_file = mkstemp()

    jh_generic_user = os.environ.get('NB_USER', 'jovyan')
    jh_username = os.environ.get("JUPYTERHUB_USER", None)

    if jh_username is None:
        raise ValueError(f"Expected 'JUPYTERHUB_USER' env var to be set. Avaialble env vars: {', '.join(os.environ.keys())}.")
    
    logger.info(f"Got username '{jh_username}'.")

    extensions_dir = f"/home/{jh_generic_user}/.vscode/extensions"
    logger.info(f"Extensions dir: '{extensions_dir}'.")
    os.makedirs(extensions_dir, exist_ok=True)

    def build_command(base_url: str):
        global prefix_url
        prefix_url = base_url
        logger.info(f"Got base_url '{base_url}'")
        code_server_arguments = [
            "--auth=none",
            "--port", "{port}",
            # "--socket", "{unix_socket}",
            "--extensions-dir", f"{extensions_dir}",
            "--disable-update-check",
            "--disable-file-uploads",
            "--disable-file-downloads",
            "--ignore-last-opened",
        ]
        return [which_code_server()] + code_server_arguments


    def proxy_path(path: str):
        prefix_path_pattern = fr"/user/{jh_username}/vscode"
        replaced_path = re.sub(prefix_path_pattern, "", path)
        logger.info(f"Proxied '{path}' -> '{replaced_path}'.")
        return replaced_path

    proxy_config_dict.update({
        "command": build_command,
        # "unix_socket": socket_file,
        "mappath": proxy_path,
    })

    return proxy_config_dict
