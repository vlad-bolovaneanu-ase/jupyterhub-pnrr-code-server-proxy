from flask import Flask, request, Response
import requests
import argparse
import os

from .logger import setup_logger

logger = setup_logger(name="proxy_wrapper")

def create_app(port: int, username: str) -> Flask:
    app = Flask(__name__)

    URL_HOME = "http://localhost:{port}".format(port=port)
    PREFIX_BASE = "/user/{user}/vscode".format(user=username)

    @app.route(f"{PREFIX_BASE}/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
    def proxy(path):
        url = f"{URL_HOME}/{path}"
        headers = {key: value for key, value in request.headers if key.lower() != 'host'}

        resp = requests.request(
            method=request.method,
            url=url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            stream=True,
        )

        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(k, v) for k, v in resp.raw.headers.items()
                            if k.lower() not in excluded_headers]
        logger.info(F"Proxy {PREFIX_BASE}/{path} -> {path}")
        return Response(resp.content, status=resp.status_code, headers=response_headers)

    @app.route(f"{PREFIX_BASE}/", defaults={"path": ""})
    @app.route(f"{PREFIX_BASE}", defaults={"path": ""})
    def root(path):
        return proxy(path)

    return app


def main():
    parser = argparse.ArgumentParser(description="Flask proxy to wrap code-server behind a subpath.")
    parser.add_argument("--port", type=int, required=True, help="Internal code-server port")
    parser.add_argument("--username", type=str, required=True, help="JupyterHub username (e.g. tdi240)")
    parser.add_argument("--listen", type=int, default=8888, help="Port to expose this proxy on")

    args = parser.parse_args()

    try:
        app = create_app(port=args.port, username=args.username)
        logger.info(f"Created app with port {args.port}, username {args.username}, listening to {args.listen}.")
        app.run(host="0.0.0.0", port=args.listen)
    except Exception as e:
        logger.error(f"Unexpected error when serving: {e}.")
        raise e

if __name__ == "__main__":
    main()