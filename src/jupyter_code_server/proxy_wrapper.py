import requests
import argparse
import time

from flask import Flask, request, redirect, Response
from werkzeug.middleware.proxy_fix import ProxyFix
# from urllib.parse import urljoin, urlparse, urlunparse

from jupyter_code_server.logger import setup_logger

logger = setup_logger(name="proxy_wrapper")
MAX_RETRIES = 5
RETRY_DELAY = 0.75

def fetch_upstream_with_retries(method, url, headers, data, cookies):
    last_err = None
    for attempt in range(1, MAX_RETRIES+1):
        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=data,
                cookies=cookies,
                allow_redirects=False,
                stream=True,
                timeout=5,
            )
            return resp
        except ConnectionError as e:
            last_err = e
            logger.warning(f"Attempt {attempt}/{MAX_RETRIES} failed to connect to upstream {url}: {e}. Retrying...")
            time.sleep(RETRY_DELAY)
    logger.error(f"Failed to connect to upstream {url} after {MAX_RETRIES} attempts.")
    raise last_err

def create_app(port: int, username: str) -> Flask:
    app = Flask(__name__)
    # If JupyterHub/nginx sets X-Forwarded-For, X-Forwarded-Proto, X-Forwarded-Host, etc:
    # Adjust the numbers (x_for, x_proto, x_host) to match how many proxies are in front.
    # Usually x_proto=1 and x_host=1 is enough if there is one proxy layer setting these headers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.url_map.strict_slashes = False
    URL_HOME = "http://localhost:{port}".format(port=port)
    PREFIX_BASE = "/user/{user}/vscode".format(user=username)

    @app.route(f"{PREFIX_BASE}/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
    def proxy(path):
        upstream = f"{URL_HOME}/{path}"
        logger.info(f"Proxying request {request.method} {request.path!r} → {upstream!r}")
        # Copy headers except Host, but may want to set Host explicitly to "localhost:<port>"
        headers = {k: v for k, v in request.headers if k.lower() != 'host'}
        try:
            resp = fetch_upstream_with_retries(request.method, upstream, headers, request.get_data(), request.cookies)
        except ConnectionError:
            return ("Upstream connection failed", 502)

        # Log status & headers
        logger.info(f"Upstream responded: {resp.status_code}")
        for k, v in resp.headers.items():
            logger.debug(f"Upstream header: {k}: {v}")

        # Non-redirect: forward headers, excluding hop-by-hop
        excluded = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded]
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
    parser.add_argument("--listen", type=int, required=True, help="Port to expose this proxy on")

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