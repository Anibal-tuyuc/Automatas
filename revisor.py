"""
revisor.py
Proyecto 1 - Revisor y clasificador de cadenas.
Autómatas y Lenguajes Formales - Universidad Mariano Gálvez.

Responsabilidades:
  - Leer el archivo de entrada (una cadena por línea).
  - Leer el archivo de expresiones con formato  NOMBRE = "patrón".
  - Clasificar cada cadena usando el motor de autómatas (motor.py).
  - Generar Salida.txt y el resumen del proceso.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from motor import ErrorExpresion, compilar

# El módulo `re` se usa ÚNICAMENTE para validar el formato de las líneas
# del archivo de expresiones, nunca para clasificar las cadenas.
PATRON_LINEA = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"(.*)"\s*$')

SIN_CLASIFICAR = "ERROR"


@dataclass
class ExpresionRegular:
    nombre: str
    patron: str
    automata: object           # AutomataCompilado


@dataclass
class Resultado:
    cadena: str
    categoria: str
    linea: int


@dataclass
class Resumen:
    total_leidas: int = 0
    vacias: int = 0
    clasificadas: int = 0
    errores: int = 0
    por_categoria: dict = field(default_factory=dict)
    resultados: list = field(default_factory=list)

    def a_dict(self):
        return {
            "total_leidas": self.total_leidas,
            "vacias": self.vacias,
            "clasificadas": self.clasificadas,
            "errores": self.errores,
            "por_categoria": self.por_categoria,
            "resultados": [
                {"cadena": r.cadena, "categoria": r.categoria, "linea": r.linea}
                for r in self.resultados
            ],
        }


class RevisorCadenas:
    """Lee cadenas y expresiones, clasifica por pertenencia y genera Salida.txt."""

    def __init__(self, carpeta_salida=None):
        self.ruta_entrada = None
        self.ruta_expresiones = None
        self.carpeta_salida = Path(carpeta_salida) if carpeta_salida else Path.cwd()
        self.ruta_salida = self.carpeta_salida / "Salida.txt"
        self.cadenas = []
        self.expresiones = []
        self.resumen = None

    # ------------------------------------------------------------------
    # 3.1  Lectura del archivo de entrada
    # ------------------------------------------------------------------
    def cargar_entrada_texto(self, texto, nombre="Entrada.txt"):
        self.cadenas = [linea.strip() for linea in texto.splitlines()]
        self.ruta_entrada = nombre
        self.resumen = None
        return len(self.cadenas)

    def cargar_entrada(self, ruta):
        path = Path(str(ruta).strip().strip('"'))
        if not path.is_file():
            raise FileNotFoundError(f"No existe el archivo de entrada: {path}")
        return self.cargar_entrada_texto(
            path.read_text(encoding="utf-8-sig"), str(path)
        )

    # ------------------------------------------------------------------
    # 3.2  Lectura del archivo de expresiones
    # ------------------------------------------------------------------
    def cargar_expresiones_texto(self, texto, nombre="Expresion.txt"):
        expresiones = []
        errores = []

        for numero, linea in enumerate(texto.splitlines(), start=1):
            limpia = linea.strip()
            if not limpia or limpia.startswith("#"):
                continue

            coincidencia = PATRON_LINEA.fullmatch(limpia)
            if coincidencia is None:
                errores.append(
                    f'Línea {numero}: formato inválido. Se espera  NOMBRE = "patrón"'
                )
                continue

            nom, patron = coincidencia.group(1), coincidencia.group(2)
            try:
                automata = compilar(nom, patron)
            except ErrorExpresion as exc:
                errores.append(f"Línea {numero} [{nom}]: {exc}")
                continue
            expresiones.append(ExpresionRegular(nom, patron, automata))

        if not expresiones:
            detalle = "\n".join(errores) if errores else "El archivo está vacío."
            raise ValueError(f"No se cargó ninguna expresión válida.\n{detalle}")

        self.expresiones = expresiones
        self.ruta_expresiones = nombre
        self.resumen = None
        return expresiones, errores

    def cargar_expresiones(self, ruta):
        path = Path(str(ruta).strip().strip('"'))
        if not path.is_file():
            raise FileNotFoundError(f"No existe el archivo de expresiones: {path}")
        return self.cargar_expresiones_texto(
            path.read_text(encoding="utf-8-sig"), str(path)
        )

    # ------------------------------------------------------------------
    # 3.3  Clasificación
    # ------------------------------------------------------------------
    def clasificar_una(self, cadena):
        """Primera expresión del archivo cuyo autómata acepta la cadena completa."""
        for expresion in self.expresiones:
            if expresion.automata.acepta(cadena):
                return expresion.nombre
        return SIN_CLASIFICAR

    def simular_una(self, cadena):
        """
        Traza completa de una cadena contra TODAS las expresiones, en orden.
        Se detiene en la primera que acepta.
        """
        intentos = []
        categoria = SIN_CLASIFICAR
        for expresion in self.expresiones:
            traza = expresion.automata.simular(cadena)
            intentos.append(traza)
            if traza["aceptada"]:
                categoria = expresion.nombre
                break
        return {"cadena": cadena, "categoria": categoria, "intentos": intentos}

    def clasificar(self):
        if self.ruta_entrada is None:
            raise RuntimeError("Primero indique el archivo de entrada.")
        if not self.expresiones:
            raise RuntimeError("Primero indique el archivo de expresiones.")

        resumen = Resumen()
        for numero, cadena in enumerate(self.cadenas, start=1):
            resumen.total_leidas += 1
            if cadena == "":
                resumen.vacias += 1
                continue
            categoria = self.clasificar_una(cadena)
            resumen.resultados.append(Resultado(cadena, categoria, numero))
            resumen.por_categoria[categoria] = (
                resumen.por_categoria.get(categoria, 0) + 1
            )
            if categoria == SIN_CLASIFICAR:
                resumen.errores += 1
            else:
                resumen.clasificadas += 1

        self.resumen = resumen
        return resumen

    # ------------------------------------------------------------------
    # 4.  Reporte: Salida.txt
    # ------------------------------------------------------------------
    def texto_salida(self):
        if self.resumen is None:
            self.clasificar()
        lineas = [
            f"{item.cadena} - {item.categoria}" for item in self.resumen.resultados
        ]
        return "\n".join(lineas) + ("\n" if lineas else "")

    def generar_salida(self, ruta=None):
        destino = Path(ruta) if ruta else self.ruta_salida
        if destino.is_dir():
            destino = destino / "Salida.txt"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(self.texto_salida(), encoding="utf-8")
        self.ruta_salida = destino
        return destino

    # ------------------------------------------------------------------
    # Información de los autómatas construidos
    # ------------------------------------------------------------------
    def descripcion_automatas(self):
        return [expresion.automata.descripcion() for expresion in self.expresiones]
