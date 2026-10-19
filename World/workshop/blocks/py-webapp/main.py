"""A local web app: python main.py  (add --share to let phones on the same Wi-Fi use it)."""
import json
import os
import sys
import threading
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
# archie:imports

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8080
DATA = {"count": 0}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=os.path.join(HERE, "web"), **k)

    def api(self, method, path, body):
        """Your API. Return something JSON-able, or None for 'not found'."""
        if path == "/api/hello":
            return {"message": "Hello from Python"}
        if path == "/api/count" and method == "POST":
            DATA["count"] += 1
            return {"count": DATA["count"]}
        return None

    def _send(self, code, obj):
        b = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _handle(self, method):
        if not self.path.startswith("/api/"):
            return super().do_GET() if method == "GET" else self._send(405, {"error": "use /api/..."})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except ValueError:
            return self._send(400, {"error": "bad JSON"})
        out = self.api(method, self.path.split("?")[0], body)
        self._send(200 if out is not None else 404, out if out is not None else {"error": "not found"})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def log_message(self, *a):
        pass                                            # keep the terminal quiet


def main():
    share = "--share" in sys.argv
    host = "0.0.0.0" if share else "127.0.0.1"          # 127.0.0.1 = only this computer
    srv = ThreadingHTTPServer((host, PORT), Handler)
    url = "http://127.0.0.1:%d/" % PORT
    if "--selftest" in sys.argv:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        r = json.loads(urllib.request.urlopen(url + "api/hello", timeout=5).read())
        page = urllib.request.urlopen(url, timeout=5).read()
        srv.shutdown()
        assert r["message"] and b"<html" in page.lower()
        print("selftest ok")
        return
    print("Running at", url, "(phones on this Wi-Fi: use this computer's IP address)" if share else "")
    webbrowser.open(url)
    srv.serve_forever()


if __name__ == "__main__":
    main()
