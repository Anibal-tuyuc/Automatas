"""
motor.py
Motor de automatas para el Proyecto 1 de Automatas y Lenguajes Formales.

Pipeline implementado (sin usar el modulo `re` para reconocer):

    Expresion regular  ->  Analisis sintactico (AST)
                       ->  AFN con transiciones vacias (Thompson)
                       ->  AFD (construccion de subconjuntos)
                       ->  Simulacion caracter por caracter

El modulo `re` solo se usa en revisor.py para leer el FORMATO del archivo
de expresiones (NOMBRE = "patron"), nunca para clasificar las cadenas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAXCP = 0x10FFFF
MAX_ESTADOS_AFD = 4000


# =====================================================================
# 1. CONJUNTOS DE CARACTERES (intervalos de puntos de codigo)
# =====================================================================

def _normalizar(rangos):
    """Ordena y fusiona intervalos solapados o contiguos."""
    limpios = sorted((lo, hi) for lo, hi in rangos if lo <= hi)
    salida = []
    for lo, hi in limpios:
        if salida and lo <= salida[-1][1] + 1:
            salida[-1] = (salida[-1][0], max(salida[-1][1], hi))
        else:
            salida.append([lo, hi])
    return tuple((lo, hi) for lo, hi in salida)


class ConjuntoCaracteres:
    """Conjunto de caracteres representado como intervalos disjuntos."""

    __slots__ = ("rangos", "etiqueta")

    def __init__(self, rangos, etiqueta=""):
        self.rangos = _normalizar(rangos)
        self.etiqueta = etiqueta or self._auto_etiqueta()

    @staticmethod
    def literal(ch):
        cp = ord(ch)
        return ConjuntoCaracteres([(cp, cp)], _mostrar(ch))

    @staticmethod
    def vacio():
        return ConjuntoCaracteres([], "0")

    def _auto_etiqueta(self):
        if not self.rangos:
            return "0"
        partes = []
        for lo, hi in self.rangos[:4]:
            if lo == hi:
                partes.append(_mostrar(chr(lo)))
            else:
                partes.append(f"{_mostrar(chr(lo))}-{_mostrar(chr(hi))}")
        if len(self.rangos) > 4:
            partes.append("...")
        return "[" + "".join(partes) + "]"

    def contiene(self, cp):
        izq, der = 0, len(self.rangos) - 1
        while izq <= der:
            med = (izq + der) // 2
            lo, hi = self.rangos[med]
            if cp < lo:
                der = med - 1
            elif cp > hi:
                izq = med + 1
            else:
                return True
        return False

    def complemento(self, etiqueta=""):
        resultado = []
        anterior = 0
        for lo, hi in self.rangos:
            if lo > anterior:
                resultado.append((anterior, lo - 1))
            anterior = hi + 1
        if anterior <= MAXCP:
            resultado.append((anterior, MAXCP))
        return ConjuntoCaracteres(resultado, etiqueta)

    def union(self, otro, etiqueta=""):
        return ConjuntoCaracteres(list(self.rangos) + list(otro.rangos), etiqueta)

    def ignorar_mayusculas(self):
        """Agrega la variante mayuscula/minuscula de cada caracter."""
        extra = []
        for lo, hi in self.rangos:
            if hi - lo > 2000:          # intervalos enormes ya cubren ambos casos
                continue
            for cp in range(lo, hi + 1):
                ch = chr(cp)
                for variante in (ch.lower(), ch.upper()):
                    extra.append((ord(variante), ord(variante)))
        return ConjuntoCaracteres(list(self.rangos) + extra, self.etiqueta)

    def esta_vacio(self):
        return not self.rangos

    def __repr__(self):
        return f"ConjuntoCaracteres({self.etiqueta})"


def _mostrar(ch):
    """Nombre legible de un caracter para la interfaz."""
    especiales = {" ": "ESP", "\t": "TAB", "\n": "NL", "\r": "CR"}
    if ch in especiales:
        return especiales[ch]
    if ord(ch) < 32 or ord(ch) == 127:
        return f"\\x{ord(ch):02x}"
    return ch


# --- clases predefinidas -------------------------------------------------

DIGITO = ConjuntoCaracteres([(48, 57)], "0-9")
NO_DIGITO = DIGITO.complemento("no digito")
PALABRA = ConjuntoCaracteres(
    [(48, 57), (65, 90), (97, 122), (95, 95), (0xC0, 0x24F)], "a-zA-Z0-9_"
)
NO_PALABRA = PALABRA.complemento("no alfanumerico")
ESPACIO = ConjuntoCaracteres([(9, 13), (32, 32)], "espacio")
NO_ESPACIO = ESPACIO.complemento("no espacio")
PUNTO = ConjuntoCaracteres([(0, 9), (11, MAXCP)], "cualquiera")

CLASES_ESCAPE = {
    "d": DIGITO, "D": NO_DIGITO,
    "w": PALABRA, "W": NO_PALABRA,
    "s": ESPACIO, "S": NO_ESPACIO,
}
ESCAPES_LITERAL = {
    "n": "\n", "t": "\t", "r": "\r", "f": "\f", "v": "\v", "0": "\0",
}


# =====================================================================
# 2. ARBOL DE SINTAXIS ABSTRACTA
# =====================================================================

class Nodo:
    pass


@dataclass
class Vacio(Nodo):
    """Cadena vacia (epsilon)."""


@dataclass
class Simbolo(Nodo):
    conjunto: ConjuntoCaracteres


@dataclass
class Concatenacion(Nodo):
    izquierda: Nodo
    derecha: Nodo


@dataclass
class Alternativa(Nodo):
    izquierda: Nodo
    derecha: Nodo


@dataclass
class Repeticion(Nodo):
    hijo: Nodo
    minimo: int
    maximo: int | None      # None = sin limite


class ErrorExpresion(ValueError):
    """Error de sintaxis o construccion en una expresion regular."""


# =====================================================================
# 3. ANALIZADOR SINTACTICO DESCENDENTE RECURSIVO
# =====================================================================

class Analizador:
    """
    Gramatica reconocida:

        alternativa   := concatenacion ('|' concatenacion)*
        concatenacion := repeticion*
        repeticion    := atomo cuantificador?
        cuantificador := '*' | '+' | '?' | '{n}' | '{n,}' | '{n,m}'
        atomo         := '(' alternativa ')' | '[' clase ']' | '.'
                       | '\\' escape | literal
    """

    def __init__(self, patron):
        self.patron = patron
        self.pos = 0
        self.ignorar_caso = False

    # -- utilidades ----------------------------------------------------
    def _fin(self):
        return self.pos >= len(self.patron)

    def _ver(self):
        return None if self._fin() else self.patron[self.pos]

    def _consumir(self):
        ch = self.patron[self.pos]
        self.pos += 1
        return ch

    def _esperar(self, ch):
        if self._ver() != ch:
            raise ErrorExpresion(
                f"Se esperaba '{ch}' en la posicion {self.pos} de: {self.patron}"
            )
        self.pos += 1

    def _aplicar_caso(self, conjunto):
        return conjunto.ignorar_mayusculas() if self.ignorar_caso else conjunto

    # -- reglas --------------------------------------------------------
    def analizar(self):
        nodo = self._alternativa()
        if not self._fin():
            raise ErrorExpresion(
                f"Caracter inesperado '{self._ver()}' en la posicion {self.pos}"
            )
        return nodo

    def _alternativa(self):
        nodo = self._concatenacion()
        while self._ver() == "|":
            self._consumir()
            nodo = Alternativa(nodo, self._concatenacion())
        return nodo

    def _concatenacion(self):
        piezas = []
        while not self._fin() and self._ver() not in ("|", ")"):
            piezas.append(self._repeticion())
        if not piezas:
            return Vacio()
        nodo = piezas[0]
        for siguiente in piezas[1:]:
            nodo = Concatenacion(nodo, siguiente)
        return nodo

    def _repeticion(self):
        nodo = self._atomo()
        while True:
            ch = self._ver()
            if ch == "*":
                self._consumir()
                nodo = Repeticion(nodo, 0, None)
            elif ch == "+":
                self._consumir()
                nodo = Repeticion(nodo, 1, None)
            elif ch == "?":
                self._consumir()
                nodo = Repeticion(nodo, 0, 1)
            elif ch == "{":
                guardado = self.pos
                limites = self._llaves()
                if limites is None:
                    self.pos = guardado
                    break
                nodo = Repeticion(nodo, limites[0], limites[1])
            else:
                break
            if self._ver() in ("?", "+"):   # perezoso/posesivo: se ignora
                self._consumir()
        return nodo

    def _llaves(self):
        self._consumir()                       # '{'
        texto = ""
        while not self._fin() and self._ver() != "}":
            texto += self._consumir()
        if self._fin():
            return None
        self._consumir()                       # '}'
        texto = texto.strip()
        try:
            if "," in texto:
                a, b = texto.split(",", 1)
                minimo = int(a) if a.strip() else 0
                maximo = int(b) if b.strip() else None
            else:
                minimo = maximo = int(texto)
        except ValueError:
            return None
        if maximo is not None and maximo < minimo:
            raise ErrorExpresion(f"Rango invalido {{{texto}}}")
        if (maximo or minimo) > 200:
            raise ErrorExpresion(f"Repeticion demasiado grande {{{texto}}}")
        return minimo, maximo

    def _atomo(self):
        ch = self._ver()
        if ch is None:
            return Vacio()

        if ch == "(":
            self._consumir()
            if self._ver() == "?":
                return self._grupo_especial()
            nodo = self._alternativa()
            self._esperar(")")
            return nodo

        if ch == "[":
            return Simbolo(self._aplicar_caso(self._clase()))

        if ch == ".":
            self._consumir()
            return Simbolo(PUNTO)

        if ch == "\\":
            return Simbolo(self._aplicar_caso(self._escape()))

        if ch in "^$":
            self._consumir()                   # anclas: redundantes con fullmatch
            return Vacio()

        if ch in "*+?":
            raise ErrorExpresion(f"Cuantificador '{ch}' sin elemento previo")

        self._consumir()
        return Simbolo(self._aplicar_caso(ConjuntoCaracteres.literal(ch)))

    def _grupo_especial(self):
        """Maneja (?i), (?: ), (?i: ), (?P<n> ). Lookahead no soportado."""
        self._consumir()                       # '?'
        bandera = ""
        while not self._fin() and self._ver() in "imsxu":
            bandera += self._consumir()

        if self._ver() == ")":                 # (?i)  -> directiva global
            self._consumir()
            if "i" in bandera:
                self.ignorar_caso = True
            return Vacio()

        if self._ver() == ":":                 # (?:...) o (?i:...)
            self._consumir()
            previo = self.ignorar_caso
            if "i" in bandera:
                self.ignorar_caso = True
            nodo = self._alternativa()
            self._esperar(")")
            if "i" in bandera:
                self.ignorar_caso = previo
            return nodo

        if self._ver() in ("P", "<"):          # grupo con nombre
            while not self._fin() and self._ver() != ">":
                self._consumir()
            self._esperar(">")
            nodo = self._alternativa()
            self._esperar(")")
            return nodo

        raise ErrorExpresion(
            "Construccion '(?...' no soportada por el motor de automatas "
            "(lookahead/lookbehind/backreference no son lenguajes regulares)"
        )

    def _clase(self):
        self._consumir()                       # '['
        negada = False
        if self._ver() == "^":
            self._consumir()
            negada = True

        rangos = []
        primero = True
        while True:
            if self._fin():
                raise ErrorExpresion("Falta ']' que cierre la clase")
            ch = self._ver()
            if ch == "]" and not primero:
                self._consumir()
                break
            primero = False

            if ch == "\\":
                conjunto = self._escape()
                rangos.extend(conjunto.rangos)
                continue

            self._consumir()
            inicio = ch
            if (self._ver() == "-" and self.pos + 1 < len(self.patron)
                    and self.patron[self.pos + 1] != "]"):
                self._consumir()
                fin = self._consumir()
                if fin == "\\":
                    fin = self._consumir()
                    fin = ESCAPES_LITERAL.get(fin, fin)
                if ord(inicio) > ord(fin):
                    raise ErrorExpresion(f"Rango invalido {inicio}-{fin}")
                rangos.append((ord(inicio), ord(fin)))
            else:
                rangos.append((ord(inicio), ord(inicio)))

        conjunto = ConjuntoCaracteres(rangos)
        return conjunto.complemento("[^...]") if negada else conjunto

    def _escape(self):
        self._consumir()                       # '\'
        if self._fin():
            raise ErrorExpresion("La expresion termina en '\\'")
        ch = self._consumir()
        if ch in CLASES_ESCAPE:
            return CLASES_ESCAPE[ch]
        if ch in ESCAPES_LITERAL:
            return ConjuntoCaracteres.literal(ESCAPES_LITERAL[ch])
        if ch == "x":
            hexa = self.patron[self.pos:self.pos + 2]
            self.pos += 2
            return ConjuntoCaracteres.literal(chr(int(hexa, 16)))
        if ch.isdigit():
            raise ErrorExpresion(
                f"Referencia hacia atras '\\{ch}' no es un lenguaje regular"
            )
        return ConjuntoCaracteres.literal(ch)


# =====================================================================
# 4. AUTOMATA FINITO NO DETERMINISTA (construccion de Thompson)
# =====================================================================

@dataclass
class AFN:
    transiciones: list = field(default_factory=list)   # [(conjunto, destino)]
    vacias: list = field(default_factory=list)         # [destino]
    inicial: int = 0
    final: int = 0

    def nuevo_estado(self):
        self.transiciones.append([])
        self.vacias.append([])
        return len(self.transiciones) - 1

    @property
    def total_estados(self):
        return len(self.transiciones)


def construir_afn(ast):
    """Construccion de Thompson: cada nodo produce un AFN con 1 inicio y 1 fin."""
    afn = AFN()

    def construir(nodo):
        if isinstance(nodo, Vacio):
            i = afn.nuevo_estado()
            f = afn.nuevo_estado()
            afn.vacias[i].append(f)
            return i, f

        if isinstance(nodo, Simbolo):
            i = afn.nuevo_estado()
            f = afn.nuevo_estado()
            afn.transiciones[i].append((nodo.conjunto, f))
            return i, f

        if isinstance(nodo, Concatenacion):
            i1, f1 = construir(nodo.izquierda)
            i2, f2 = construir(nodo.derecha)
            afn.vacias[f1].append(i2)
            return i1, f2

        if isinstance(nodo, Alternativa):
            i = afn.nuevo_estado()
            i1, f1 = construir(nodo.izquierda)
            i2, f2 = construir(nodo.derecha)
            f = afn.nuevo_estado()
            afn.vacias[i] += [i1, i2]
            afn.vacias[f1].append(f)
            afn.vacias[f2].append(f)
            return i, f

        if isinstance(nodo, Repeticion):
            inicio = afn.nuevo_estado()
            actual = inicio
            # parte obligatoria: n copias en serie
            for _ in range(nodo.minimo):
                i, f = construir(nodo.hijo)
                afn.vacias[actual].append(i)
                actual = f
            final = afn.nuevo_estado()
            if nodo.maximo is None:
                i, f = construir(nodo.hijo)       # cierre de Kleene
                afn.vacias[actual].append(i)
                afn.vacias[actual].append(final)
                afn.vacias[f].append(i)
                afn.vacias[f].append(final)
            else:
                afn.vacias[actual].append(final)
                for _ in range(nodo.maximo - nodo.minimo):
                    i, f = construir(nodo.hijo)
                    afn.vacias[actual].append(i)
                    afn.vacias[f].append(final)
                    actual = f
            return inicio, final

        raise ErrorExpresion(f"Nodo desconocido: {nodo!r}")

    inicial, final = construir(ast)
    afn.inicial, afn.final = inicial, final
    return afn


# =====================================================================
# 5. AUTOMATA FINITO DETERMINISTA (construccion de subconjuntos)
# =====================================================================

@dataclass
class AFD:
    """AFD con alfabeto particionado en clases atomicas disjuntas."""
    clases: list = field(default_factory=list)      # [ConjuntoCaracteres]
    tabla: list = field(default_factory=list)       # tabla[estado][clase] = destino|-1
    aceptacion: list = field(default_factory=list)  # [bool]
    conjuntos: list = field(default_factory=list)   # subconjunto AFN de cada estado
    inicial: int = 0

    @property
    def total_estados(self):
        return len(self.tabla)

    def clase_de(self, ch):
        cp = ord(ch)
        for indice, conjunto in enumerate(self.clases):
            if conjunto.contiene(cp):
                return indice
        return -1

    def mover(self, estado, ch):
        indice = self.clase_de(ch)
        if indice < 0:
            return -1, -1
        return self.tabla[estado][indice], indice


def _particionar(afn):
    """Divide el alfabeto en intervalos atomicos disjuntos."""
    puntos = {0, MAXCP + 1}
    for lista in afn.transiciones:
        for conjunto, _ in lista:
            for lo, hi in conjunto.rangos:
                puntos.add(lo)
                puntos.add(hi + 1)
    ordenados = sorted(p for p in puntos if 0 <= p <= MAXCP + 1)

    clases = []
    for a, b in zip(ordenados, ordenados[1:]):
        if a > MAXCP:
            break
        usado = any(
            conjunto.contiene(a)
            for lista in afn.transiciones
            for conjunto, _ in lista
        )
        if usado:
            clases.append(ConjuntoCaracteres([(a, min(b - 1, MAXCP))]))
    return clases


def _cerradura_vacia(afn, estados):
    pila = list(estados)
    vistos = set(estados)
    while pila:
        actual = pila.pop()
        for destino in afn.vacias[actual]:
            if destino not in vistos:
                vistos.add(destino)
                pila.append(destino)
    return frozenset(vistos)


def construir_afd(afn):
    clases = _particionar(afn)
    inicial = _cerradura_vacia(afn, [afn.inicial])

    indices = {inicial: 0}
    pendientes = [inicial]
    conjuntos = [inicial]
    tabla = []
    aceptacion = []

    while pendientes:
        actual = pendientes.pop(0)
        fila = []
        for conjunto_clase in clases:
            muestra = conjunto_clase.rangos[0][0]
            alcanzados = set()
            for estado in actual:
                for conjunto, destino in afn.transiciones[estado]:
                    if conjunto.contiene(muestra):
                        alcanzados.add(destino)
            if not alcanzados:
                fila.append(-1)
                continue
            cerradura = _cerradura_vacia(afn, alcanzados)
            if cerradura not in indices:
                if len(indices) >= MAX_ESTADOS_AFD:
                    raise ErrorExpresion(
                        "La expresion genera un AFD demasiado grande "
                        f"(mas de {MAX_ESTADOS_AFD} estados)"
                    )
                indices[cerradura] = len(indices)
                conjuntos.append(cerradura)
                pendientes.append(cerradura)
            fila.append(indices[cerradura])
        tabla.append(fila)
        aceptacion.append(afn.final in actual)

    return AFD(clases, tabla, aceptacion, conjuntos, 0)


# =====================================================================
# 6. AUTOMATA COMPILADO + SIMULACION PASO A PASO
# =====================================================================

class AutomataCompilado:
    """Expresion regular lista para reconocer cadenas con traza de pasos."""

    def __init__(self, nombre, patron):
        self.nombre = nombre
        self.patron = patron
        self.ast = Analizador(patron).analizar()
        self.afn = construir_afn(self.ast)
        self.afd = construir_afd(self.afn)

    # -- reconocimiento rapido (sin traza) -----------------------------
    def acepta(self, cadena):
        estado = self.afd.inicial
        for ch in cadena:
            estado, _ = self.afd.mover(estado, ch)
            if estado < 0:
                return False
        return self.afd.aceptacion[estado]

    # -- reconocimiento con traza para la animacion --------------------
    def simular(self, cadena):
        """Devuelve la traza completa: un paso por cada caracter consumido."""
        pasos = []
        estado = self.afd.inicial
        motivo = None

        for indice, ch in enumerate(cadena):
            siguiente, clase = self.afd.mover(estado, ch)
            pasos.append({
                "indice": indice,
                "caracter": ch,
                "caracter_vista": _mostrar(ch),
                "desde": f"q{estado}",
                "hacia": f"q{siguiente}" if siguiente >= 0 else "RECHAZO",
                "clase": self.afd.clases[clase].etiqueta if clase >= 0 else "-",
                "valido": siguiente >= 0,
                "consumido": cadena[: indice + 1],
                "pendiente": cadena[indice + 1:],
            })
            if siguiente < 0:
                motivo = (
                    f"No existe transicion desde q{estado} "
                    f"con el caracter '{_mostrar(ch)}' (posicion {indice + 1})"
                )
                estado = -1
                break
            estado = siguiente

        if estado < 0:
            aceptada = False
        else:
            aceptada = self.afd.aceptacion[estado]
            if not aceptada:
                motivo = (
                    f"La cadena se consumio completa pero q{estado} "
                    "no es estado de aceptacion"
                )

        return {
            "expresion": self.nombre,
            "patron": self.patron,
            "cadena": cadena,
            "pasos": pasos,
            "aceptada": aceptada,
            "estado_final": f"q{estado}" if estado >= 0 else "RECHAZO",
            "motivo": motivo,
            "estados_afn": self.afn.total_estados,
            "estados_afd": self.afd.total_estados,
        }

    # -- descripcion del automata para la interfaz ---------------------
    def descripcion(self):
        filas = []
        for estado, fila in enumerate(self.afd.tabla):
            destinos = {}
            for indice, destino in enumerate(fila):
                if destino >= 0:
                    destinos.setdefault(destino, []).append(
                        self.afd.clases[indice].etiqueta
                    )
            filas.append({
                "estado": f"q{estado}",
                "aceptacion": self.afd.aceptacion[estado],
                "inicial": estado == self.afd.inicial,
                "transiciones": [
                    {"simbolos": _resumir(simbolos), "destino": f"q{destino}"}
                    for destino, simbolos in sorted(destinos.items())
                ],
            })
        return {
            "nombre": self.nombre,
            "patron": self.patron,
            "estados_afn": self.afn.total_estados,
            "estados_afd": self.afd.total_estados,
            "tabla": filas,
        }


def _resumir(simbolos, limite=6):
    if len(simbolos) <= limite:
        return ", ".join(simbolos)
    return ", ".join(simbolos[:limite]) + f" (+{len(simbolos) - limite})"


def compilar(nombre, patron):
    """Compila una expresion regular a AFD, lanzando ErrorExpresion si falla."""
    try:
        return AutomataCompilado(nombre, patron)
    except ErrorExpresion:
        raise
    except RecursionError as exc:
        raise ErrorExpresion(f"Expresion demasiado anidada: {exc}") from exc
    except Exception as exc:
        raise ErrorExpresion(f"No se pudo construir el automata: {exc}") from exc
