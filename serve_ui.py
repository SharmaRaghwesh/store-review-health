"""Serve ui/ on localhost and open it in the browser.

The map tiles (OpenStreetMap) are refused when the page is opened straight from disk,
so the UI has to be viewed through this local server.

Run from the project root:  python serve_ui.py     (Ctrl+C to stop)
"""
import functools
import http.server
import webbrowser

import config


def main():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(config.UI_DIR))
    url = f"http://localhost:{config.UI_PORT}/"
    with http.server.ThreadingHTTPServer(("127.0.0.1", config.UI_PORT), handler) as server:
        print(f"serving {config.UI_DIR} at {url}  (Ctrl+C to stop)")
        webbrowser.open(url)
        server.serve_forever()


if __name__ == "__main__":
    main()
