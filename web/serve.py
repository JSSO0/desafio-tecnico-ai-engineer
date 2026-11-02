from __future__ import annotations

import os
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 5173


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print("  " + format % args)


def main() -> None:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    url = f"http://localhost:{PORT}/"
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print(f"A porta {PORT} já está em uso.")
        print(
            "Feche o outro processo ou ajuste CORS_ORIGINS na API "
            "para a origem que estiver usando."
        )
        return

    print("Empório da Música — interface de atendimento")
    print(f"Servindo em {url}")
    print("A API precisa estar em http://localhost:8000 e liberar a origem http://localhost:5173.")
    print("Ctrl+C para parar.")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
