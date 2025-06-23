from flask import Flask, request, redirect, Response
# from urllib.parse import urljoin, urlparse, urlunparse
import requests
import argparse
import os

from jupyter_code_server.logger import setup_logger

logger = setup_logger(name="proxy_wrapper")

def create_app(port: int, username: str) -> Flask:
    app = Flask(__name__)

    app.url_map.strict_slashes = False
    URL_HOME = "http://localhost:{port}".format(port=port)
    PREFIX_BASE = "/user/{user}/vscode".format(user=username)

    @app.route(f"{PREFIX_BASE}/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
    def proxy(path):
        url = f"{URL_HOME}/{path}"
        logger.info(f"Request for {path}")
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

        # Log response status and headers
        logger.info(f"Response status: {resp.status_code}")
        logger.info(f"Response headers:\n" + "\n".join(f"{k}: {v}" for k, v in resp.headers.items()))

        # if 300 <= resp.status_code < 400:
        #     location = resp.headers.get('Location')
        #     if location:
        #         # Rewrite Location header to proxy base path
        #         # If location is absolute URL, extract path part
        #         parsed = urlparse(location)
        #         # Use path + query + fragment (ignore scheme/netloc to avoid redirecting outside proxy)
        #         new_path = parsed.path
        #         if parsed.query:
        #             new_path += '?' + parsed.query
        #         if parsed.fragment:
        #             new_path += '#' + parsed.fragment

        #         # Join with your proxy prefix base path
        #         # For example, prefix "/user/vlad/vscode"
        #         new_location = urljoin(PREFIX_BASE + '/', new_path.lstrip('/'))

        #         # Build the response with the rewritten Location header
        #         headers = [(k, v) for k, v in resp.headers.items() if k.lower() != 'content-length']
        #         # Replace Location with rewritten one
        #         headers = [(k, v) if k.lower() != 'location' else ('Location', new_location) for k, v in headers]

        #         return Response(resp.content, status=resp.status_code, headers=headers)

        # For non-redirect responses, copy headers as usual, excluding hop-by-hop
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded_headers]

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