"""
Proyecto 1 - Revisor y clasificador de cadenas
Autómatas y Lenguajes Formales
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


PATRON_LINEA = re.compile(
    r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"(.*)"\s*$'
)


@dataclass
class ExpresionRegular:
    nombre: str
    patron: str
    compilada: re.Pattern[str]


@dataclass
class Resultado:
    cadena: str
    categoria: str


@dataclass
class Resumen:
    total_leidas: int = 0
    vacias: int = 0
    clasificadas: int = 0
    errores: int = 0
    por_categoria: dict[str, int] = field(default_factory=dict)
    resultados: list[Resultado] = field(default_factory=list)


class RevisorCadenas:
    """Lee cadenas y regex, clasifica por pertenencia y genera Salida.txt."""

    def __init__(self) -> None:
        self.ruta_entrada: Path | None = None
        self.ruta_expresiones: Path | None = None
        self.ruta_salida: Path = Path("Salida.txt")
        self.cadenas: list[str] = []
        self.expresiones: list[ExpresionRegular] = []
        self.resumen: Resumen | None = None

    def cargar_entrada(self, ruta: str) -> int:
        path = Path(ruta.strip().strip('"'))
        if not path.is_file():
            raise FileNotFoundError(f"No existe el archivo de entrada: {path}")
        texto = path.read_text(encoding="utf-8-sig")
        self.cadenas = [linea.strip() for linea in texto.splitlines()]
        self.ruta_entrada = path
        self.resumen = None
        return len(self.cadenas)

    def cargar_expresiones(self, ruta: str) -> list[ExpresionRegular]:
        path = Path(ruta.strip().strip('"'))
        if not path.is_file():
            raise FileNotFoundError(f"No existe el archivo de expresiones: {path}")

        expresiones: list[ExpresionRegular] = []
        for numero, linea in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
            limpia = linea.strip()
            if not limpia or limpia.startswith("#"):
                continue
            coincidencia = PATRON_LINEA.fullmatch(limpia)
            if coincidencia is None:
                raise ValueError(
                    f"Línea {numero} inválida: {linea}\n"
                    'Formato: NOMBRE = "expresion"'
                )
            nombre, patron = coincidencia.group(1), coincidencia.group(2)
            try:
                compilada = re.compile(patron)
            except re.error as exc:
                raise ValueError(
                    f"Regex inválida en '{nombre}' (línea {numero}): {exc}"
                ) from exc
            expresiones.append(ExpresionRegular(nombre, patron, compilada))

        if not expresiones:
            raise ValueError("El archivo no contiene expresiones.")

        self.expresiones = expresiones
        self.ruta_expresiones = path
        self.resumen = None
        return expresiones

    def establecer_salida(self, ruta: str) -> None:
        path = Path(ruta.strip().strip('"'))
        if path.is_dir():
            path = path / "Salida.txt"
        self.ruta_salida = path

    def clasificar(self) -> Resumen:
        if self.ruta_entrada is None:
            raise RuntimeError("Primero indique el archivo de entrada.")
        if not self.expresiones:
            raise RuntimeError("Primero indique el archivo de expresiones.")

        resumen = Resumen()
        for cadena in self.cadenas:
            resumen.total_leidas += 1
            if cadena == "":
                resumen.vacias += 1
                continue
            categoria = self._pertenece(cadena)
            resumen.resultados.append(Resultado(cadena, categoria))
            resumen.por_categoria[categoria] = resumen.por_categoria.get(categoria, 0) + 1
            if categoria == "ERROR":
                resumen.errores += 1
            else:
                resumen.clasificadas += 1

        self.resumen = resumen
        return resumen

    def generar_salida(self) -> Path:
        if self.resumen is None:
            self.clasificar()
        assert self.resumen is not None

        lineas = [f"{item.cadena} - {item.categoria}" for item in self.resumen.resultados]
        contenido = "\n".join(lineas)
        if lineas:
            contenido += "\n"
        self.ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        self.ruta_salida.write_text(contenido, encoding="utf-8")
        return self.ruta_salida

    def _pertenece(self, cadena: str) -> str:
        # Primera regex del archivo que acepta la cadena completa.
        # fullmatch exige que todo w esté en L(r), no solo un substring.
        for expresion in self.expresiones:
            if expresion.compilada.fullmatch(cadena):
                return expresion.nombre
        return "ERROR"


def mostrar_resumen(revisor: RevisorCadenas) -> None:
    resumen = revisor.resumen
    if resumen is None:
        print("Todavía no se ha clasificado.")
        return
    print("\n---------- RESUMEN DEL PROCESO ----------")
    print(f"Entrada      : {revisor.ruta_entrada}")
    print(f"Expresiones  : {revisor.ruta_expresiones}")
    print(f"Salida       : {revisor.ruta_salida}")
    print(f"Líneas leídas: {resumen.total_leidas}")
    print(f"Vacías       : {resumen.vacias}")
    print(f"Clasificadas : {resumen.clasificadas}")
    print(f"ERROR        : {resumen.errores}")
    print("Por categoría:")
    for categoria, cantidad in resumen.por_categoria.items():
        print(f"  {categoria}: {cantidad}")
    print("-----------------------------------------\n")


def menu() -> None:
    revisor = RevisorCadenas()
    while True:
        print("\n==============================================")
        print("  REVISOR DE CADENAS")
        print("  Autómatas y Lenguajes Formales - Proyecto 1")
        print("==============================================")
        print(f"Entrada     : {revisor.ruta_entrada or '(no indicado)'}")
        print(f"Expresiones : {revisor.ruta_expresiones or '(no indicado)'}")
        print(f"Salida      : {revisor.ruta_salida}")
        print("----------------------------------------------")
        print("1. Indicar archivo de entrada")
        print("2. Indicar archivo de expresiones")
        print("3. Indicar archivo de salida")
        print("4. Clasificar cadenas y generar Salida.txt")
        print("5. Ver resumen del proceso")
        print("6. Salir")
        opcion = input("Seleccione una opción: ").strip()

        try:
            if opcion == "1":
                ruta = input("Ruta de Entrada.txt: ")
                total = revisor.cargar_entrada(ruta)
                print(f"Se leyeron {total} líneas.")
            elif opcion == "2":
                ruta = input("Ruta de Expresion.txt: ")
                expresiones = revisor.cargar_expresiones(ruta)
                print(f"Se cargaron {len(expresiones)} expresiones:")
                for expr in expresiones:
                    print(f"  {expr.nombre} = {expr.patron}")
            elif opcion == "3":
                ruta = input("Ruta de Salida.txt: ")
                if ruta.strip():
                    revisor.establecer_salida(ruta)
                print(f"Salida: {revisor.ruta_salida}")
            elif opcion == "4":
                revisor.clasificar()
                destino = revisor.generar_salida()
                print(f"Archivo generado: {destino.resolve()}")
                mostrar_resumen(revisor)
            elif opcion == "5":
                mostrar_resumen(revisor)
            elif opcion == "6":
                print("Finaliza la ejecución del programa.")
                break
            else:
                print("Opción no válida.")
        except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        print("\nEjecución interrumpida.")
        sys.exit(0)