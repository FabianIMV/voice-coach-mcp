"""Alineación de fonemas esperados vs. detectados (Levenshtein con backtrace) y puntajes."""

from dataclasses import dataclass

from .base import ErrorFonema, ResultadoPalabra
from .fonemas import es_vocal, tolerado

COSTO_INDEL = 1.0
COSTO_SUSTITUCION = 1.0
COSTO_SUSTITUCION_CRUZADA = 1.5  # vocal ↔ consonante: se prefiere alinear dentro de la clase
COSTO_TOLERADO = 0.1  # variante aceptada: no es error, pero ante empates gana el fonema idéntico
PESO_INSERCION = 0.5  # en el puntaje, una inserción pesa la mitad que una sustitución u omisión


@dataclass
class Operacion:
    tipo: str  # "ok" | "sustitucion" | "omision" | "insercion"
    esperado: str | None
    detectado: str | None
    i: int | None  # índice en esperados
    j: int | None  # índice en detectados


def _costo(a: str, b: str) -> float:
    if a == b:
        return 0.0
    if tolerado(a, b):
        return COSTO_TOLERADO
    return COSTO_SUSTITUCION if es_vocal(a) == es_vocal(b) else COSTO_SUSTITUCION_CRUZADA


def alinear(esperados: list[str], detectados: list[str]) -> list[Operacion]:
    n, m = len(esperados), len(detectados)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = i * COSTO_INDEL
    for j in range(1, m + 1):
        d[0][j] = j * COSTO_INDEL
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(
                d[i - 1][j - 1] + _costo(esperados[i - 1], detectados[j - 1]),
                d[i - 1][j] + COSTO_INDEL,
                d[i][j - 1] + COSTO_INDEL,
            )
    ops: list[Operacion] = []
    i, j = n, m
    while i > 0 or j > 0:
        if (
            i > 0
            and j > 0
            and d[i][j] == d[i - 1][j - 1] + _costo(esperados[i - 1], detectados[j - 1])
        ):
            a, b = esperados[i - 1], detectados[j - 1]
            ops.append(Operacion("ok" if tolerado(a, b) else "sustitucion", a, b, i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + COSTO_INDEL:
            ops.append(Operacion("omision", esperados[i - 1], None, i - 1, None))
            i -= 1
        else:
            ops.append(Operacion("insercion", None, detectados[j - 1], None, j - 1))
            j -= 1
    return _enlaces(ops[::-1])


def _enlaces(ops: list[Operacion]) -> list[Operacion]:
    """La "r de enlace" (weather‿is → ɚ ɹ ɪ) y el golpe glótico no cuentan como inserción.

    Aparecen porque cada palabra se fonetiza por separado y se pierde la conexión entre ellas.
    """
    for k, op in enumerate(ops):
        if op.tipo != "insercion":
            continue
        previo = ops[k - 1].detectado if k > 0 else None
        if op.detectado == "ʔ" or (op.detectado == "ɹ" and previo in ("ɚ", "ə")):
            op.tipo = "ok"
    return ops


def distancia(ops: list[Operacion]) -> float:
    return sum(op.tipo != "ok" for op in ops)


def puntaje(n_esperados: int, errores: list[ErrorFonema]) -> float:
    if n_esperados == 0:
        return 100.0
    penalizacion = sum(PESO_INSERCION if e.tipo == "insercion" else 1.0 for e in errores)
    return max(0.0, min(100.0, 100.0 * (1 - penalizacion / n_esperados)))


def por_palabra(
    palabras: list[str],
    esperados: list[list[str]],
    ops: list[Operacion],
    tiempos: list[float] | None = None,
) -> list[ResultadoPalabra]:
    """Reparte las operaciones entre palabras; las inserciones van a la palabra anterior."""
    palabra_de = [k for k, fs in enumerate(esperados) for _ in fs]
    resultados = [
        ResultadoPalabra(palabra=p, puntaje=100.0, esperados=list(e))
        for p, e in zip(palabras, esperados, strict=True)
    ]
    actual = 0
    for op in ops:
        if op.i is not None:
            actual = palabra_de[op.i]
        r = resultados[actual] if resultados else None
        if r is None:
            continue
        if op.detectado is not None:
            r.detectados.append(op.detectado)
            if tiempos is not None and r.inicio is None and op.j is not None:
                r.inicio = tiempos[op.j]
        if op.tipo != "ok":
            r.errores.append(ErrorFonema(op.tipo, op.esperado, op.detectado))
    for r in resultados:
        r.puntaje = puntaje(len(r.esperados), r.errores)
        r.omitida = bool(r.esperados) and not r.detectados
    return resultados


def puntaje_global(resultados: list[ResultadoPalabra]) -> float:
    total = sum(len(r.esperados) for r in resultados)
    errores = [e for r in resultados for e in r.errores]
    return puntaje(total, errores)
