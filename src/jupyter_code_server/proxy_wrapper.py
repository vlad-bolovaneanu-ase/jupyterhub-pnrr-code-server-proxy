import requests
import argparse
import os

from flask import Flask, request, redirect, Response
from werkzeug.middleware.proxy_fix import ProxyFix
from urllib.parse import urljoin, urlparse, urlunparse

from jupyter_code_server.logger import setup_logger

logger = setup_logger(name="proxy_wrapper")

def create_app(port: int, username: str) -> Flask:
    app = Flask(__name__)
    # If JupyterHub/nginx sets X-Forwarded-For, X-Forwarded-Proto, X-Forwarded-Host, etc:
    # Adjust the numbers (x_for, x_proto, x_host) to match how many proxies are in front.
    # Usually x_proto=1 and x_host=1 is enough if there is one proxy layer setting these headers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.url_map.strict_slashes = False
    URL_HOME = "http://localhost:{port}".format(port=port)
    PREFIX_BASE = "/user/{user}/vscode".format(user=username)

    # @app.before_request
    # def ensure_trailing_slash():
    #     # Only target paths under our PREFIX_BASE
    #     # Also ensure we don’t redirect root "/user/…/vscode" itself if it's exactly the base without subpath—
    #     # but if you want always slash, adjust accordingly.
    #     # Here: if path starts with PREFIX_BASE and does not end with '/', redirect.
    #     path = request.path
    #     if path.startswith(PREFIX_BASE) and not path.endswith('/'):
    #         # Build new URL preserving scheme and host via request.url / request.host_url
    #         parsed = urlparse(request.url)
    #         new_path = parsed.path + '/'
    #         # urlunparse ensures query string is kept automatically if we use parsed._replace
    #         new_url = urlunparse(parsed._replace(path=new_path))
    #         # This new_url now has scheme “https” if ProxyFix made request.scheme="https"
    #         return redirect(new_url, code=308)

    @app.route(f"{PREFIX_BASE}/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
    def proxy(path):
        upstream = f"{URL_HOME}/{path}"
        logger.info(f"Proxying request {request.method} {request.path!r} → {upstream!r}")
        # Copy headers except Host, but may want to set Host explicitly to "localhost:<port>"
        headers = {k: v for k, v in request.headers if k.lower() != 'host'}
        try:
            resp = requests.request(
                method=request.method,
                url=upstream,
                headers=headers,
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                stream=True,
            )
        except Exception as e:
            logger.exception(f"Failed to connect to upstream {upstream}")
            return ("Upstream connection failed", 502)

        # Log status & headers
        logger.info(f"Upstream responded: {resp.status_code}")
        for k, v in resp.headers.items():
            logger.debug(f"Upstream header: {k}: {v}")

        # Handle redirects: rewrite Location to include the PREFIX_BASE with correct scheme/host
        # if 300 <= resp.status_code < 400:
        #     location = resp.headers.get('Location')
        #     if location:
        #         parsed_loc = urlparse(location)
        #         # Build new path: parsed_loc.path may be absolute or relative.
        #         new_path = parsed_loc.path
        #         if parsed_loc.query:
        #             new_path += '?' + parsed_loc.query
        #         if parsed_loc.fragment:
        #             new_path += '#' + parsed_loc.fragment
        #         # Prepend PREFIX_BASE
        #         # Use urljoin to avoid duplicate slashes
        #         rewritten = urljoin(PREFIX_BASE + '/', new_path.lstrip('/'))
        #         # Now build full URL with correct scheme+host: request.host_url gives e.g. "https://hpc.ase.ro/"
        #         # strip trailing slash then append rewritten path:
        #         new_location = request.host_url.rstrip('/') + rewritten
        #         logger.info(f"Rewriting redirect Location {location!r} → {new_location!r}")
        #         # Build headers for Response, excluding content-length so Flask recalculates it
        #         headers = [(k, v) for k, v in resp.headers.items() if k.lower() != 'content-length']
        #         # Replace Location header
        #         headers = [(k, v) if k.lower() != 'location' else ('Location', new_location) for k, v in headers]
        #         return Response(resp.content, status=resp.status_code, headers=headers)

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