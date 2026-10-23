# Canto: leer `analizar_afinacion` y elegir ejercicios

## Cómo pedir el análisis

- **Sin referencia**: cada nota se compara con la nota temperada más cercana. Sirve para notas
  tenidas, sirenas y escalas.
- **Con `tonalidad`** ("Do mayor", "A minor"): cada nota se compara con la nota más cercana de la
  escala. Sirve para detectar notas fuera de la tonalidad (por ejemplo, F natural en Sol mayor
  aparece como F#4 a −95 cents).
- **Con `referencia_midi`**: compara contra la melodía real. El usuario aporta el MIDI (exportado
  desde MuseScore, un DAW, etc.). Si el MIDI tiene acompañamiento, indica la pista con `pista_midi`.

## Lectura rápida

| Campo | Lectura orientativa |
|---|---|
| `porcentaje_dentro_25_cents` | ≥ 85 %: muy bien · 60–85 %: en progreso · < 60 %: foco prioritario |
| `desviacion_media_cents` / `tendencia` | Un sesgo de ±10 cents o más es sistemático: plano o sostenido |
| `deriva_cents` | Muy negativa (< −15): la afinación cae hacia el final (aire o fatiga) |
| `estabilidad` | `inestable` en notas largas: falta de apoyo; `vibrato` es normal en notas largas |
| `vibrato_hz`, `vibrato_pp_cents` | Típico: 5–7 Hz y 50–150 cents pico a pico. > 200 cents o < 4,5 Hz: vibrato ancho y lento ("wobble"); > 7,5 Hz: trémolo rápido |
| `notas[].deriva_cents` | La nota se "cae" o "sube" mientras se sostiene |
| `nota_incorrecta` | Se cantó otra nota: problema de intervalo u oído, no de afinación fina |
| `entrada` tarde/temprano | Más de ±80 ms respecto del pulso de la referencia |
| `omitidas`, `notas_extra` | Memoria de la melodía, falta de aire, o adornos y deslizamientos |
| `transposicion_octavas` | Informativo: cantar una octava abajo está bien si es el registro de la persona |

La distancia de 1 cent equivale a 1/100 de semitono. Un oído entrenado percibe 5–10 cents en
notas tenidas; en melodías rápidas, ±25 cents suele sonar afinado.

## Problema → indicación → ejercicio

| Problema medido | Indicación | Ejercicio |
|---|---|---|
| Tendencia **plano**, sobre todo en agudos | Más apoyo respiratorio, pensar la nota "desde arriba", vocal más brillante | Notas tenidas de 5 s con *ng* → vocal; escala de 5 notas subiendo de medio tono en medio tono |
| Tendencia **sostenido** | Suele venir de tensión o exceso de presión de aire: soltar mandíbula y cuello, menos volumen | Sirenas suaves en *u*; la misma frase a mitad de volumen |
| **Deriva negativa** a lo largo de la toma | Gestión del aire: respirar antes de quedarse sin aire | Marcar respiraciones en la frase; frases más cortas |
| Nota que **cae mientras se sostiene** (`deriva_cents` < −15) | Mantener el apoyo hasta el final de la nota | *Messa di voce* corta (crescendo-decrescendo) en esa nota |
| **Inestable** sin vibrato | Flujo de aire irregular | Notas tenidas con *lip trill* y luego con vocal, 3 × 6 s |
| **Nota incorrecta** en un intervalo | Oído interválico | Cantar el intervalo aislado 5 veces (nota de partida → destino) y volver a la frase |
| **Entradas tarde** | Respirar antes del tiempo, no en el tiempo | Frase con metrónomo; contar "1-2-3-y" y entrar en el "y" |
| **Omitidas** | Memoria o aire | Cantar la frase con *la-la* y luego con la letra |

## Calentamientos (2–3 min, elige uno según el nivel)

- *Lip trill* o *ng* en sirena, del grave al agudo y de vuelta (3 veces).
- Escala de 5 notas (Do-Re-Mi-Fa-Sol-Fa-Mi-Re-Do) en *a* o *u*, subiendo de medio tono en medio tono.
- Nota tenida cómoda de 5–8 s: sirve de línea base de afinación y estabilidad. Analízala sin referencia.

## Progresión sugerida

1. Notas tenidas y escalas sin referencia: afinación básica y estabilidad.
2. Escalas con `tonalidad`: notas de la escala.
3. Frases de la canción con `referencia_midi`: afinación, intervalos y tiempo.
4. Canción completa por secciones de 20–40 s.
