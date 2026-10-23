"""Textos de los prompts MCP que estructuran una sesión de práctica.

Los prompts guían a Claude en el orden de la sesión y en qué campos mirar; el criterio
pedagógico lo pone Claude (o la skill coach-de-voz), no el servidor.
"""

_CIERRE = """
Reglas de la sesión:
- Al empezar, llama a leer_progreso y retoma el foco de la última sesión; al terminar, registra la
  sesión con registrar_progreso (fecha, ejercicio, métricas antes → después, foco siguiente).
- Pide una grabación por intento y analízala antes de dar feedback; no adivines lo que no mediste.
- Si la respuesta trae advertencias o confianza baja, dilo y propone repetir la toma antes de opinar.
- Da como máximo un foco por intento, citando números y momentos concretos (segundos, nota, palabra).
- Compara cada intento con el anterior y cierra con el siguiente ejercicio concreto.
"""


def sesion_canto(nivel: str = "intermedio", objetivo: str = "", referencia_midi: str = "") -> str:
    referencia = (
        f"Usa la referencia MIDI `{referencia_midi}` en analizar_afinacion (parámetro referencia_midi)."
        if referencia_midi
        else "No hay referencia MIDI: analiza contra la nota temperada más cercana o, si el usuario "
        "indica la tonalidad, pásala en el parámetro tonalidad."
    )
    return f"""Conduce una sesión de canto para un nivel {nivel}.{f" Objetivo del usuario: {objetivo}." if objetivo else ""}

1. Calentamiento (2–3 min): propone un ejercicio corto (sirenas, notas tenidas, escala de 5 notas)
   adaptado al nivel. Graba una nota tenida cómoda con grabar_audio (5–8 s) y analízala con
   analizar_afinacion para tener una línea base de afinación y estabilidad.
2. Ejercicio principal: explica qué cantar y por cuánto tiempo. Graba con grabar_audio
   (segundos suficientes + 2 de margen). {referencia}
3. Análisis: lee resumen.porcentaje_dentro_25_cents, tendencia (plano/sostenido), deriva_cents,
   estabilidad (estable/vibrato/inestable) y, con referencia, notas_incorrectas, omitidas y entradas.
   Identifica las 1–2 notas con mayor |cents| o con entrada tarde/temprano.
4. Feedback: un foco concreto (por ejemplo, "la nota E4 en el segundo 3,2 quedó 35 cents abajo"),
   por qué importa y una indicación práctica para corregirlo.
5. Siguiente ejercicio: aísla el problema (repetir la frase, más lento, o solo el intervalo difícil),
   vuelve a grabar y compara con el intento anterior.
{_CIERRE}"""


def sesion_pronunciacion(nivel: str = "intermedio", foco: str = "") -> str:
    return f"""Conduce una sesión de pronunciación en inglés (en-US) para un nivel {nivel}.{f" Foco pedido: {foco}." if foco else ""}

1. Calentamiento: 2–3 pares mínimos relacionados con el foco (p. ej., ship/sheep, think/sink).
   Pide leerlos en voz alta, graba con grabar_audio y evalúa con evaluar_pronunciacion pasando
   el texto exacto en texto_esperado.
2. Ejercicio principal: una o dos frases cortas que contengan los fonemas objetivo. Graba y evalúa.
3. Análisis: revisa el puntaje global, las palabras con menor puntaje y el tipo de error
   (sustitución esperado→detectado, omisión, inserción). Si la confianza es baja o aparece
   texto_no_coincide, pide repetir leyendo exactamente el texto.
4. Feedback: un fonema por intento; describe cómo se articula (posición de lengua, labios, sonoridad)
   y contrástalo con el fonema que se detectó.
5. Siguiente ejercicio: más pares mínimos o una frase nueva con ese fonema; vuelve a medir y compara.
{_CIERRE}"""


def sesion_oratoria(contexto: str = "", duracion_objetivo_s: int = 60) -> str:
    return f"""Conduce una sesión de oratoria.{f" Contexto: {contexto}." if contexto else ""} Duración objetivo de cada toma: {duracion_objetivo_s} s.

1. Calentamiento: respiración y una lectura breve en voz alta (20–30 s). Graba y corre
   metricas_discurso para una línea base de ritmo, pausas y variación de tono/volumen.
2. Ejercicio principal: pide hablar sobre el tema durante ~{duracion_objetivo_s} s. Graba con
   grabar_audio y analiza con metricas_discurso (idioma del discurso).
3. Análisis: palabras_por_minuto, pausas largas (con timestamp), muletillas por minuto y cuáles,
   variación de tono (monotonía) y de volumen. Usa la transcripción para ubicar los momentos.
4. Feedback: un foco por toma (por ejemplo, "6 'este' en 60 s, sobre todo al empezar ideas"),
   con una técnica concreta para corregirlo.
5. Siguiente ejercicio: repetir el mismo contenido aplicando el foco, y comparar las métricas.
{_CIERRE}"""
