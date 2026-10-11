"""
Static server for local preview of site/, on $PORT.

index.html is authored as a fragment: the Artifact host wraps it in a document
skeleton at publish time. Serving the bare fragment locally is misleading -- with
no viewport meta a phone lays the page out at 980px and scales it down, so a
mobile check against the raw file tests nothing. This server therefore wraps the
fragment in the same skeleton the host applies, so what the preview shows is
what gets published.
"""
import functools
import http.server
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "site"))
PORT = int(os.environ.get("PORT", "8000"))

# Mirrors the Artifact runtime's wrapper: charset + viewport meta and a small
# reset. Keep in step with the Artifact tool's documented skeleton.
HEAD = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root { color-scheme: light; }
body { margin: 0; font: 14px system-ui, -apple-system, sans-serif; background: #fdfdfc; }
img { max-width: 100%; }
[hidden] { display: none !important; }
</style>
</head>
<body>
"""
TAIL = "\n</body>\n</html>\n"


class Handler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        if os.path.basename(path) == "index.html" and os.path.isfile(path):
            with open(path, "rb") as fh:
                body = HEAD.encode("utf-8") + fh.read() + TAIL.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return io.BytesIO(body)
        return super().send_head()

    def log_message(self, fmt, *args):
        pass


handler = functools.partial(Handler, directory=ROOT)
# Threading: a single-threaded server deadlocks as soon as the preview pane
# holds a connection open while anything else requests a file.
http.server.ThreadingHTTPServer.allow_reuse_address = True
with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler) as httpd:
    print(f"serving {ROOT} on http://127.0.0.1:{PORT} (artifact skeleton applied)",
          flush=True)
    httpd.serve_forever()
