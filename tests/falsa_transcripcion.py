"""Transcripciones armadas a mano para probar métricas sin cargar Whisper."""

from voice_coach_mcp.habla.transcripcion import Palabra, Segmento, Transcripcion


def armar(frases: list[list[tuple[str, float, float]]], idioma: str = "es") -> Transcripcion:
    """frases = [[(texto, inicio, fin), ...], ...]; cada frase es un segmento."""
    segmentos = []
    for frase in frases:
        palabras = [Palabra(t, i, f, 0.95) for t, i, f in frase]
        segmentos.append(
            Segmento(frase[0][1], frase[-1][2], " ".join(t for t, _, _ in frase), palabras)
        )
    return Transcripcion(idioma=idioma, prob_idioma=0.99, segmentos=segmentos)


def regular(
    texto: str, inicio: float = 0.0, dur: float = 0.3, hueco: float = 0.1
) -> list[tuple[str, float, float]]:
    """Una frase con palabras de duración fija separadas por huecos fijos."""
    frase, t = [], inicio
    for palabra in texto.split():
        frase.append((palabra, round(t, 3), round(t + dur, 3)))
        t += dur + hueco
    return frase
