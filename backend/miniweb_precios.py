from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Importamos tu lógica de procesamiento
from procesar_precios import procesar_csv_desde_web, CSV_URL, OUTPUT_TXT

import ssl
import time

from procesar_precios import generar_precios_txt, OUTPUT_TXT, REFRESH_SECONDS


HOST = "127.0.0.1"
PORT = 8080

_last_refresh = 0.0

def asegurar_precios_actualizados():
    """
    Si pasó más de REFRESH_SECONDS desde la última actualización
    o no existe precios.txt, lo regeneramos.
    """
    global _last_refresh
    ahora = time.time()

    if (not OUTPUT_TXT.exists()) or (ahora - _last_refresh > REFRESH_SECONDS):
        print("[INFO] Regenerando precios.txt (trigger desde servidor HTTPS)...")
        generar_precios_txt()
        _last_refresh = ahora
    else:
        print("[INFO] Usando precios.txt en caché.")


class PreciosHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Normalizamos path (ignoramos querystring)
        path = self.path.split("?", 1)[0]

        if path in ("/", "/precios.txt"):
            # Intentamos actualizar (si falla, por lo menos servimos lo último que haya)
            asegurar_precios_actualizados()

            try:
                data = OUTPUT_TXT.read_bytes()
            except FileNotFoundError:
                self.send_response(503)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"No hay precios.txt disponible\n")
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        elif path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK\n")

        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found\n")

    # Para que no spamee logs feos
    def log_message(self, format, *args):
        print(f"[HTTP] {self.address_string()} {self.requestline} -> {format % args}")


def run():
    server = HTTPServer((HOST, PORT), PreciosHandler)
    print(f"[INFO] Mini web levantada en http://{HOST}:{PORT}/precios.txt")
    server.serve_forever()


if __name__ == "__main__":
    run()
