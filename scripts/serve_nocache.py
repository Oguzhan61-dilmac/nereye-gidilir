from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import sys

class NoCacheHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("0.0.0.0", port), NoCacheHTTPRequestHandler)
    print(f"Serving with NO-CACHE on http://localhost:{port}/")
    server.serve_forever()
