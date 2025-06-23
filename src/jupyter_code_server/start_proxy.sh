#!/bin/bash

CODE_PORT=${1}
JUPYTERHUB_USER=${2}
JUPYTERHUB_GENERIC_USER=${3:-jovyan}
LISTEN_PORT=${4:-8888}

code-server --auth=none --port=$CODE_PORT \
    --extensions-dir=/home/$JUPYTERHUB_GENERIC_USER/.vscode/extensions \
    --disable-update-check --disable-file-uploads --disable-file-downloads \
    --ignore-last-opened &

CS_PID=$!

python3 $(dirname "$0")/proxy_wrapper.py --port $CODE_PORT --username $JUPYTERHUB_USER --listen $LISTEN_PORT &

PROXY_PID=$!

# Ctrl+C
trap "kill $CS_PID $PROXY_PID" SIGINT SIGTERM

# Wait for both to finish
wait $CS_PID
wait $PROXY_PID