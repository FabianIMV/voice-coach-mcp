# Oratoria: leer `metricas_discurso` y entrenar

## Cómo pedir el análisis

- Tomas de 45–90 s sobre un tema que el usuario conozca (presentarse, explicar su trabajo,
  defender una idea). Indica el `idioma` del discurso ("es" o "en").
- Para comparar tomas, mantén el mismo tema y la misma duración.

## Rangos orientativos

| Métrica | Referencia |
|---|---|
| `palabras_por_minuto` | 120–160: cómodo para presentar · > 170: rápido · < 110: lento. El español suele medir algo menos de ppm que el inglés para el mismo ritmo silábico. |
| `ppm_sin_pausas_largas` | Velocidad de articulación: si es muy alta (> 190) aunque las ppm sean normales, habla rápido y compensa con pausas |
| `pausas.lista` | Las pausas tras una idea (después de un punto) ayudan. Si la palabra en `tras` es *de*, *que*, *el*, *the*, *to*…, la pausa está a mitad de una frase: indica titubeo |
| `muletillas.por_minuto` | < 2: excelente · 2–5: normal · > 5: foco de trabajo. Mira `por_tipo` para ver cuál domina |
| `tono.desv_semitonos` | < 2: monótono · 2–4: natural · > 4: muy expresivo. `tramos_monotonos` indica en qué segundos |
| `volumen.desv_entre_palabras_db` | < 3 dB: volumen plano · 3–6 dB: natural · > 8 dB: caídas fuertes (final de frase inaudible) |

Las muletillas se detectan sobre la transcripción: un "eh" muy breve puede no aparecer, así que el
conteo es un **mínimo**.

## Problema → técnica → ejercicio

| Problema | Técnica | Ejercicio |
|---|---|---|
| Muchas muletillas | Cambiar la muletilla por una pausa silenciosa | Repetir la toma; cada vez que aparezca el impulso de decir *eh*, cerrar la boca 1 s. Meta: −50 % de muletillas/min |
| Pausas a mitad de frase | Planificar la frase antes de empezarla | Escribir 3 ideas clave; hablar idea por idea, con una pausa solo entre ideas |
| Demasiado rápido | Pausas intencionales y finales de frase marcados | Leer un párrafo marcando una pausa en cada punto; meta de 140 ppm |
| Monótono | Subir el tono en la palabra clave y bajarlo al cerrar la idea | Leer la misma frase enfatizando una palabra distinta cada vez; meta: desv ≥ 2,5 semitonos |
| Volumen plano o que se apaga | Proyectar hacia el fondo de la sala; sostener el aire hasta la última palabra | Decir frases cortas a 3 m de distancia imaginaria; terminar cada frase con la misma energía |

## Progresión

1. Lectura en voz alta (texto conocido): ritmo y pausas.
2. Discurso preparado de 60 s: muletillas y pausas.
3. Respuestas improvisadas de 45 s a preguntas que hace Claude: fluidez bajo presión.
