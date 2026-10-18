# 仅用于本地预览：Python 自带服务器会把 .webp 报成 octet-stream，
# Chrome 对 MIME 很挑，这里补上正确的类型。
import http.server
import socketserver
import sys

socketserver.TCPServer.allow_reuse_address = True
socketserver.TCPServer.allow_reuse_port = True


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".webp": "image/webp",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".mp4": "video/mp4",
        ".json": "application/json",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        print("serving on", port)
        httpd.serve_forever()
