"""
app.py
Servidor web local para el Proyecto 1 de Autómatas y Lenguajes Formales.

Uso:
    python app.py
    luego abrir  http://127.0.0.1:5000

Si Flask está instalado se utiliza Flask; de lo contrario el programa
levanta un servidor equivalente con la librería estándar de Python,
de modo que no se requiere instalar nada.
"""

from __future__ import annotations

import os
import json
import mimetypes
import sys
import webbrowser
from pathlib import Path

from revisor import RevisorCadenas

BASE = Path(__file__).resolve().parent
ESTATICOS = BASE / "static"
PLANTILLAS = BASE / "templates"
PUERTO = 5000
HOST = os.environ.get("APP_HOST", "127.0.0.1")


# =====================================================================
# Lógica compartida entre los dos servidores
# =====================================================================

def procesar(datos):
    """
    Recibe {entrada: str, expresiones: str, guardar: bool}
    Devuelve el plan completo de animación + resultado + Salida.txt
    """
    texto_entrada = datos.get("entrada", "")
    texto_expresiones = datos.get("expresiones", "")
    nombre_entrada = datos.get("nombre_entrada", "Entrada.txt")
    nombre_expr = datos.get("nombre_expresiones", "Expresion.txt")
    guardar = bool(datos.get("guardar", True))

    revisor = RevisorCadenas(carpeta_salida=BASE)

    expresiones, avisos = revisor.cargar_expresiones_texto(
        texto_expresiones, nombre_expr
    )
    revisor.cargar_entrada_texto(texto_entrada, nombre_entrada)
    revisor.clasificar()

    # Traza de animación: solo líneas no vacías
    trazas = [
        revisor.simular_una(cadena)
        for cadena in revisor.cadenas
        if cadena != ""
    ]

    salida_texto = revisor.texto_salida()
    ruta_guardada = None
    if guardar:
        try:
            ruta_guardada = str(revisor.generar_salida())
        except OSError as exc:
            avisos.append(f"No se pudo escribir Salida.txt: {exc}")

    return {
        "ok": True,
        "archivos": {
            "entrada": nombre_entrada,
            "expresiones": nombre_expr,
            "salida": ruta_guardada,
        },
        "expresiones": [
            {"nombre": e.nombre, "patron": e.patron} for e in expresiones
        ],
        "automatas": revisor.descripcion_automatas(),
        "trazas": trazas,
        "resumen": revisor.resumen.a_dict(),
        "salida_texto": salida_texto,
        "avisos": avisos,
    }


def manejar_peticion(cuerpo):
    """Envuelve procesar() devolviendo errores en formato JSON."""
    try:
        datos = json.loads(cuerpo or "{}")
    except json.JSONDecodeError as exc:
        return 400, {"ok": False, "error": f"JSON inválido: {exc}"}

    try:
        return 200, procesar(datos)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        return 400, {"ok": False, "error": str(exc)}
    except Exception as exc:                        # noqa: BLE001
        return 500, {"ok": False, "error": f"Error interno: {exc}"}


def leer_plantilla():
    return (PLANTILLAS / "index.html").read_text(encoding="utf-8")


def banner(motor):
    print("=" * 62)
    print("  REVISOR DE CADENAS  -  Proyecto 1")
    print("  Autómatas y Lenguajes Formales")
    print("=" * 62)
    print(f"  Servidor  : {motor}")
    print(f"  Carpeta   : {BASE}")
    print(f"  Dirección : http://127.0.0.1:{PUERTO}")
    print("  Detener   : Ctrl + C")
    print("=" * 62)


# =====================================================================
# Servidor con Flask (si está disponible)
# =====================================================================

def arrancar_flask():
    from flask import Flask, Response, request, send_from_directory

    app = Flask(__name__, static_folder=None)

    @app.route("/")
    def inicio():
        return Response(leer_plantilla(), mimetype="text/html; charset=utf-8")

    @app.route("/static/<path:recurso>")
    def estatico(recurso):
        return send_from_directory(ESTATICOS, recurso)

    @app.route("/api/procesar", methods=["POST"])
    def api_procesar():
        codigo, cuerpo = manejar_peticion(request.get_data(as_text=True))
        return Response(
            json.dumps(cuerpo, ensure_ascii=False),
            status=codigo,
            mimetype="application/json; charset=utf-8",
        )

    @app.route("/api/ejemplos")
    def api_ejemplos():
        return Response(
            json.dumps(cargar_ejemplos(), ensure_ascii=False),
            mimetype="application/json; charset=utf-8",
        )

    banner("Flask")
    app.run(host=HOST, port=PUERTO, debug=False)


# =====================================================================
# Servidor con la librería estándar (sin dependencias)
# =====================================================================

def arrancar_estandar():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Manejador(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, formato, *args):
            if "/api/" in str(args):
                super().log_message(formato, *args)

        def _responder(self, codigo, cuerpo, tipo):
            datos = cuerpo if isinstance(cuerpo, bytes) else cuerpo.encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(datos)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(datos)

        def do_GET(self):
            ruta = self.path.split("?")[0]

            if ruta in ("/", "/index.html"):
                self._responder(200, leer_plantilla(), "text/html; charset=utf-8")
                return

            if ruta == "/api/ejemplos":
                self._responder(
                    200,
                    json.dumps(cargar_ejemplos(), ensure_ascii=False),
                    "application/json; charset=utf-8",
                )
                return

            if ruta.startswith("/static/"):
                archivo = (ESTATICOS / ruta[len("/static/"):]).resolve()
                if archivo.is_file() and ESTATICOS.resolve() in archivo.parents:
                    tipo = mimetypes.guess_type(archivo.name)[0] or "text/plain"
                    self._responder(
                        200,
                        archivo.read_bytes(),
                        f"{tipo}; charset=utf-8",
                    )
                    return

            self._responder(404, "No encontrado", "text/plain; charset=utf-8")

        def do_POST(self):
            if self.path.split("?")[0] != "/api/procesar":
                self._responder(404, "No encontrado", "text/plain; charset=utf-8")
                return
            largo = int(self.headers.get("Content-Length", 0))
            cuerpo = self.rfile.read(largo).decode("utf-8")
            codigo, respuesta = manejar_peticion(cuerpo)
            self._responder(
                codigo,
                json.dumps(respuesta, ensure_ascii=False),
                "application/json; charset=utf-8",
            )

    banner("Librería estándar (Flask no instalado)")
    servidor = ThreadingHTTPServer((HOST, PUERTO), Manejador)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        servidor.server_close()


# =====================================================================
# Archivos de ejemplo
# =====================================================================

def cargar_ejemplos():
    def leer(nombre, respaldo):
        archivo = BASE / nombre
        if archivo.is_file():
            return archivo.read_text(encoding="utf-8-sig")
        return respaldo

    return {
        "entrada": leer("Entrada.txt", EJEMPLO_ENTRADA),
        "expresiones": leer("Expresion.txt", EJEMPLO_EXPRESIONES),
    }


EJEMPLO_ENTRADA = """11/01/2017
9/09/2017
09/09/2017
11/12/14perico
09/SEP/2017
9/Sep/2017
09-sep-2017
09/Sep/2017
JUAN
DKAKDJDKJFDK
Dsdsadadfdf
aaaaaaa
9x^2+6x+10
SQRT(45)
128.120.10.238
https://www.umg.edu.gt
test@miumg.edu.gt
AUTOMAS Y LENGUAJES FORMALES
"""

EJEMPLO_EXPRESIONES = (
    'FECHA_CORTA_NUMEROS = "\\d{1,2}/\\d{1,2}/\\d{4}"\n'
    'FECHA_MES_LETRAS = "\\d{1,2}[/-](?i)(ene|feb|mar|abr|may|jun|jul|ago|'
    'sep|oct|nov|dic)[/-]\\d{4}"\n'
    'CADENA_MAYUSCULAS = "[A-Z]+"\n'
    'CADENA_MINUSCULAS = "[a-z]+"\n'
)


def crear_ejemplos_si_faltan():
    for nombre, contenido in (
        ("Entrada.txt", EJEMPLO_ENTRADA),
        ("Expresion.txt", EJEMPLO_EXPRESIONES),
    ):
        archivo = BASE / nombre
        if not archivo.exists():
            archivo.write_text(contenido, encoding="utf-8")
            print(f"  Creado archivo de ejemplo: {nombre}")


# =====================================================================

def main():
    if not (PLANTILLAS / "index.html").is_file():
        print("ERROR: falta templates/index.html")
        sys.exit(1)

    crear_ejemplos_si_faltan()

    if "--no-abrir" not in sys.argv:
        try:
            webbrowser.open(f"http://127.0.0.1:{PUERTO}")
        except Exception:
            pass

    try:
        import flask  # noqa: F401
    except ImportError:
        arrancar_estandar()
    else:
        arrancar_flask()


if __name__ == "__main__":
    main()
