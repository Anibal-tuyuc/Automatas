"""
prueba.py
Verificacion del motor de automatas contra el ejemplo del enunciado.
Ejecutar con:  python prueba.py
"""

from revisor import RevisorCadenas

ENTRADA = """11/01/2017
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

EXPRESIONES = (
    'FECHA_CORTA_NUMEROS = "\\d{1,2}/\\d{1,2}/\\d{4}"\n'
    'FECHA_MES_LETRAS = "\\d{1,2}[/-](?i)(ene|feb|mar|abr|may|jun|jul|ago|'
    'sep|oct|nov|dic)[/-]\\d{4}"\n'
    'CADENA_MAYUSCULAS = "[A-Z]+"\n'
    'CADENA_MINUSCULAS = "[a-z]+"\n'
)

ESPERADO = [
    ("11/01/2017", "FECHA_CORTA_NUMEROS"),
    ("9/09/2017", "FECHA_CORTA_NUMEROS"),
    ("09/09/2017", "FECHA_CORTA_NUMEROS"),
    ("11/12/14perico", "ERROR"),
    ("09/SEP/2017", "FECHA_MES_LETRAS"),
    ("9/Sep/2017", "FECHA_MES_LETRAS"),
    ("09-sep-2017", "FECHA_MES_LETRAS"),
    ("09/Sep/2017", "FECHA_MES_LETRAS"),
    ("JUAN", "CADENA_MAYUSCULAS"),
    ("DKAKDJDKJFDK", "CADENA_MAYUSCULAS"),
    ("Dsdsadadfdf", "ERROR"),
    ("aaaaaaa", "CADENA_MINUSCULAS"),
    ("9x^2+6x+10", "ERROR"),
    ("SQRT(45)", "ERROR"),
    ("128.120.10.238", "ERROR"),
    ("https://www.umg.edu.gt", "ERROR"),
    ("test@miumg.edu.gt", "ERROR"),
    ("AUTOMAS Y LENGUAJES FORMALES", "ERROR"),
]


def main():
    revisor = RevisorCadenas()
    expresiones, avisos = revisor.cargar_expresiones_texto(EXPRESIONES)
    revisor.cargar_entrada_texto(ENTRADA)
    revisor.clasificar()

    print("=" * 66)
    print("  EXPRESIONES COMPILADAS")
    print("=" * 66)
    for expresion in expresiones:
        automata = expresion.automata
        print(f"  {expresion.nombre:<22} AFN:{automata.afn.total_estados:>4} "
              f"estados   AFD:{automata.afd.total_estados:>3} estados")
    if avisos:
        print("\n  AVISOS:")
        for aviso in avisos:
            print("   -", aviso)

    print()
    print("=" * 66)
    print("  CLASIFICACION")
    print("=" * 66)

    obtenido = [(r.cadena, r.categoria) for r in revisor.resumen.resultados]
    fallos = 0
    for (cadena, esperado), (_, real) in zip(ESPERADO, obtenido):
        if esperado == real:
            print(f"  OK    {cadena:<32} -> {real}")
        else:
            fallos += 1
            print(f"  FALLA {cadena:<32} -> {real}   (esperado: {esperado})")

    print()
    print("=" * 66)
    print(f"  RESULTADO: {len(ESPERADO) - fallos}/{len(ESPERADO)} correctas")
    print("=" * 66)

    print("\n  RESUMEN DEL PROCESO")
    resumen = revisor.resumen
    print(f"   Lineas leidas : {resumen.total_leidas}")
    print(f"   Vacias        : {resumen.vacias}")
    print(f"   Clasificadas  : {resumen.clasificadas}")
    print(f"   ERROR         : {resumen.errores}")
    for categoria, cantidad in sorted(resumen.por_categoria.items()):
        print(f"     {categoria:<22} {cantidad}")

    print("\n  TRAZA DE EJEMPLO: '9/Sep/2017'")
    traza = revisor.simular_una("9/Sep/2017")
    for intento in traza["intentos"]:
        marca = "ACEPTA" if intento["aceptada"] else "rechaza"
        print(f"\n   {intento['expresion']} -> {marca}")
        for paso in intento["pasos"][:14]:
            flecha = "->" if paso["valido"] else "-X"
            print(f"      '{paso['caracter_vista']}'  "
                  f"{paso['desde']} {flecha} {paso['hacia']}")
        if len(intento["pasos"]) > 14:
            print(f"      ... ({len(intento['pasos']) - 14} pasos mas)")

    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
