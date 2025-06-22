#!/bin/bash

CODE_PORT=${1}
JUPYTERHUB_USER=${2}
JUPYTERHUB_GENERIC_USER=${3:-jovyan}
LISTEN_PORT=${4:-8888}

$(which code-server) \
    --auth=none \
    --port=$CODE_PORT \
    --extensions-dir=/home/$JUPYTERHUB_GENERIC_USER/.vscode/extensions \
    --auth=none \
    --disable-update-check \
    --disable-file-uploads \
    --disable-file-downloads \
    --ignore-last-opened &

exec python3 proxy_wrapper.py \
    --port $CODE_PORT \
    --prefix /user/$JUPYTERHUB_USER/vscode \
    --listen $LISTEN_PORT