"""Melodía de referencia desde un archivo MIDI aportado por el usuario."""

from dataclasses import dataclass
from pathlib import Path

from ..errores import ErrorUsuario


@dataclass
class NotaRef:
    inicio: float
    fin: float
    midi: int


@dataclass
class Melodia:
    notas: list[NotaRef]
    pista: str
    era_polifonica: bool


def cargar_melodia(ruta: Path, pista: int | None = None) -> Melodia:
    """Toma la pista indicada o, por defecto, la no percusiva con más notas.

    Si la pista tiene notas superpuestas se queda con la línea superior (skyline).
    """
    import pretty_midi

    try:
        midi = pretty_midi.PrettyMIDI(str(ruta))
    except Exception as e:  # pretty_midi/mido lanzan varios tipos de error
        raise ErrorUsuario(f"No pude leer el MIDI {ruta.name}: {e}") from e

    candidatas = [
        (i, inst) for i, inst in enumerate(midi.instruments) if not inst.is_drum and inst.notes
    ]
    if not candidatas:
        raise ErrorUsuario(f"El MIDI {ruta.name} no tiene pistas melódicas con notas.")
    if pista is not None:
        elegidas = [c for c in candidatas if c[0] == pista]
        if not elegidas:
            disponibles = ", ".join(f"{i} ({inst.name or 'sin nombre'})" for i, inst in candidatas)
            raise ErrorUsuario(
                f"La pista {pista} no existe o no tiene notas. Disponibles: {disponibles}"
            )
        indice, instrumento = elegidas[0]
    else:
        indice, instrumento = max(candidatas, key=lambda c: len(c[1].notes))

    notas = sorted(instrumento.notes, key=lambda n: (n.start, -n.pitch))
    melodia: list[NotaRef] = []
    polifonica = False
    for n in notas:
        if melodia and n.start < melodia[-1].fin - 1e-3:
            polifonica = True
            if n.pitch <= melodia[-1].midi:
                continue  # queda debajo de la nota que suena: no es la melodía
            melodia[-1].fin = n.start
            if melodia[-1].fin - melodia[-1].inicio < 1e-3:
                melodia.pop()
        melodia.append(NotaRef(inicio=float(n.start), fin=float(n.end), midi=int(n.pitch)))
    nombre = instrumento.name.strip() or f"pista {indice}"
    return Melodia(notas=melodia, pista=f"{indice}: {nombre}", era_polifonica=polifonica)
