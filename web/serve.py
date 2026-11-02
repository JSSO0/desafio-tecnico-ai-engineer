from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Sem estes arquivos a pagina abre em branco e o console acusa erro de rede,
# que parece falha de CORS mas nao e. Melhor falhar na largada, com o nome do que falta.
ARQUIVOS_OBRIGATORIOS = (
    "index.html",
    "app.js",
    "styles.css",
    "vendor/react.production.min.js",
    "vendor/react-dom.production.min.js",
    "vendor/htm.umd.js",
)


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print("  " + format % args)


def faltando(base: Path) -> list[str]:
    return [nome for nome in ARQUIVOS_OBRIGATORIOS if not (base / nome).exists()]


def porta_em_uso(host: str, port: int) -> bool:
    """Sonda a porta antes de abrir.

    No Windows, `SO_REUSEADDR` faz o segundo `ThreadingHTTPServer` assumir a mesma porta em
    silêncio: dois processos servindo o mesmo endereço e requisições caindo no servidor errado.
    O `OSError` nunca aparece, então a checagem tem de ser ativa.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sonda:
        sonda.settimeout(0.3)
        return sonda.connect_ex((host, port)) == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve a interface da Emporio da Musica")
    parser.add_argument("--port", type=int, default=5173)
    # o mesmo IP do bind e usado na URL: evita localhost resolver para ::1 e nao conectar
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    base = Path(__file__).resolve().parent
    os.chdir(base)

    ausentes = faltando(base)
    if ausentes:
        print("A interface nao vai abrir: faltam arquivos.", file=sys.stderr)
        for nome in ausentes:
            print(f"  - {nome}", file=sys.stderr)
        print(
            "\nO pacote original veio sem a pasta vendor/. Use a versao deste repositorio "
            "ou rode: docker compose up --build  (interface em http://localhost:8080)",
            file=sys.stderr,
        )
        return 1

    if porta_em_uso(args.host, args.port):
        print(
            f"A porta {args.port} já está em uso — parece haver outra instância servindo.",
            file=sys.stderr,
        )
        print(
            "Feche o outro processo. Não troque de porta às cegas: a origem precisa estar em "
            "CORS_ORIGINS no .env da API, senão o navegador bloqueia as chamadas.",
            file=sys.stderr,
        )
        return 1

    try:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
    except OSError as exc:
        print(f"Nao consegui abrir {args.host}:{args.port} — {exc}", file=sys.stderr)
        return 1

    url = f"http://{args.host}:{args.port}/"
    print("Emporio da Musica — interface de atendimento")
    print(f"Servindo {base} em {url}")
    print("A API precisa estar em http://localhost:8000 e liberar esta origem (CORS_ORIGINS).")
    print("Ctrl+C para parar.")

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
