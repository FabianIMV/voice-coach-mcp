# voice-coach-mcp

Servidor MCP en Python que le da "oídos" a Claude. Claude no procesa audio, así que este servidor
graba y analiza el audio **localmente** y le devuelve mediciones compactas en JSON (afinación,
pronunciación, ritmo del discurso). Con esos datos, Claude actúa como coach de canto,
pronunciación en inglés y oratoria.

- **Las tools miden; Claude interpreta.** El servidor no da consejos: devuelve números,
  categorías descriptivas, un campo `confianza` y `advertencias` (ruido, clipping, audio corto…).
- **Respuestas de ~2 KB como máximo.** Si hay más detalle, se guarda en un JSON junto al audio y la
  respuesta indica la ruta en `detalle_completo`.
- **Sin material con derechos.** Las melodías de referencia las aportas tú como MIDI; los tests y
  los ejemplos usan audio sintético.

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Esqueleto, `grabar_audio`, `analizar_afinacion`, prompts | ✅ |
| 2 | `transcribir`, `metricas_discurso` | ✅ |
| 3 | `evaluar_pronunciacion` (wav2vec2 local / Azure opcional) | pendiente |
| 4 | Skill `coach-de-voz` | pendiente |

## Requisitos

- macOS (o Linux) con micrófono
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`); uv instala Python 3.12 por su cuenta
- Opcional: `brew install ffmpeg` para leer `.m4a`/`.aac` (p. ej., notas de voz del iPhone). WAV, FLAC, OGG y MP3 se leen sin ffmpeg.

```bash
git clone https://github.com/fabianimv/voice-coach-mcp.git
cd voice-coach-mcp
uv sync --extra habla               # canto + transcripción y oratoria
uv run voice-coach-mcp descargar-modelos   # opcional: baja Whisper ahora y no en la 1.ª llamada
```

Extras: `habla` agrega faster-whisper para `transcribir` y `metricas_discurso` (el modelo
`small` pesa ~480 MB y se descarga una sola vez). Con solo `uv sync` funcionan la grabación y la
afinación; si llamas a una tool que necesita un extra que no instalaste, el error indica el
comando para instalarlo. La primera llamada a `analizar_afinacion` tarda unos segundos más porque
compila el detector de pitch (numba).

## Registrar el servidor

### Claude Desktop

Edita `~/Library/Application Support/Claude/claude_desktop_config.json` (Claude → Ajustes →
Desarrollador → Editar configuración) y agrega:

```json
{
  "mcpServers": {
    "voice-coach": {
      "command": "/Users/TU_USUARIO/.local/bin/uv",
      "args": ["--directory", "/Users/TU_USUARIO/ruta/a/voice-coach-mcp", "run", "voice-coach-mcp"],
      "env": {
        "VOICE_COACH_DIR": "/Users/TU_USUARIO/VoiceCoach"
      }
    }
  }
}
```

Usa **rutas absolutas**: Claude Desktop no hereda el `PATH` de tu terminal. `which uv` te da la
ruta de `uv`. Reinicia Claude Desktop después de guardar.

### Claude Code

```bash
claude mcp add voice-coach --scope user -- uv --directory /ruta/a/voice-coach-mcp run voice-coach-mcp
```

Comprueba con `claude mcp list` o `/mcp` dentro de Claude Code.

### Permiso de micrófono (macOS)

macOS le da el permiso de micrófono a la **app que lanza el servidor**: Claude Desktop o la
terminal donde corre Claude Code (Terminal, iTerm, Ghostty, VS Code…). La primera vez que se graba,
macOS debería preguntar. Si el permiso está denegado, macOS no falla: entrega silencio. En ese caso
`grabar_audio` devuelve la advertencia `sin_permiso_microfono`. Para corregirlo, ve a **Ajustes del
Sistema → Privacidad y seguridad → Micrófono**, habilita la app y reiníciala.

## Tools

Todas aceptan como `audio` una ruta (wav/flac/mp3/m4a…) o el nombre que devolvió `grabar_audio`.
Todas las respuestas incluyen `confianza` (`valor` 0–1 y `nivel` alta/media/baja) y `advertencias`
(`codigo` + `detalle`).

### `grabar_audio(segundos, nombre?)`

Graba del micrófono predeterminado y guarda un `.wav` de 16 kHz mono en
`$VOICE_COACH_DIR/grabaciones/` (por defecto `~/VoiceCoach`). No sobrescribe: si el nombre existe,
agrega `-2`, `-3`… Máximo 120 s por defecto (`VOICE_COACH_MAX_SEGUNDOS`). Mientras graba, informa
el progreso al cliente.

Salida real (con un dispositivo de entrada **simulado**, porque el entorno donde se generó no tiene micrófono):

```json
{"audio":"~/VoiceCoach/grabaciones/toma.wav","duracion_s":3.0,"sample_rate":16000,"dispositivo":"Micrófono falso",
 "niveles":{"pico_dbfs":-10.5,"rms_dbfs":-14.3,"snr_db":60.0,"clipping_pct":0.0},
 "confianza":{"valor":1.0,"nivel":"alta"},"advertencias":[]}
```

Sin permiso de micrófono ([ejemplo completo](ejemplos/salidas/grabar_audio_sin_permiso.json)):

```json
{"audio":"~/VoiceCoach/grabaciones/toma-2.wav", "...": "...",
 "confianza":{"valor":0.0,"nivel":"baja"},
 "advertencias":[{"codigo":"sin_permiso_microfono","detalle":"macOS no está entregando audio del micrófono. Revisa Ajustes del Sistema → Privacidad y seguridad → Micrófono…"},
                 {"codigo":"silencio_digital","detalle":"El audio es silencio absoluto (todo ceros)."}]}
```

### `analizar_afinacion(audio, referencia_midi?, tonalidad?, pista_midi?)`

Analiza una línea melódica (voz sola). Tiene tres modos:

- **temperado** (por defecto): cada nota se compara con la nota temperada más cercana (A4 = 440 Hz, configurable).
- **tonalidad**: con `tonalidad` ("A minor", "Am", "La menor", "Sol mayor", "F#", "sib menor"…), cada nota se compara con la nota más cercana de esa escala (mayor o menor natural).
- **referencia_midi**: con `referencia_midi`, se alinea lo cantado con la melodía del MIDI. Tolera cantar una octava arriba o abajo, empezar en otro momento y un tempo algo distinto. Usa la pista no percusiva con más notas (o `pista_midi`); si tiene acordes, toma la línea superior.

Campos principales:

| Campo | Significado |
|---|---|
| `resumen.porcentaje_dentro_25_cents` | % de notas a ±25 cents o menos de la nota objetivo |
| `resumen.desviacion_media_cents` | media ponderada por duración, con signo (+ = sostenido) |
| `resumen.tendencia` | `plano` (< −10 cents), `sostenido` (> +10) o `centrado` |
| `resumen.deriva_cents` | cuánto sube (+) o baja (−) la afinación de la 2.ª mitad respecto de la 1.ª |
| `resumen.estabilidad` | conteo de notas `estable` / `vibrato` / `inestable` |
| `notas[].t`, `dur` | inicio y duración en segundos |
| `notas[].cents` | desviación respecto de la nota objetivo |
| `notas[].estabilidad` | `estable`; `vibrato` (con `vibrato_hz` y `vibrato_pp_cents`, pico a pico); `inestable` (con `desv_cents`) |
| `notas[].deriva_cents` | solo si la nota sube o baja ≥ 15 cents de principio a fin |
| con MIDI: `esperada`, `cantada`, `nota_incorrecta` | `cantada` aparece solo si difiere de la esperada; incorrecta = más de 50 cents de error |
| con MIDI: `entrada_ms`, `entrada` | adelanto o atraso respecto del pulso de la referencia; `a_tiempo` si está dentro de ±80 ms |
| con MIDI: `estado` | `omitida` (nota de la referencia que no se cantó) o `extra` (nota cantada sin pareja) |
| con MIDI: `transposicion_octavas`, `desfase_inicio_ms`, `tempo_relativo` | octava en que se cantó, momento de la grabación donde empieza la referencia, y tempo (> 1 = más lento) |

Si la lista de notas no cabe en ~2 KB, se muestran las más problemáticas (`notas_mostradas: "10 de 220"`)
y el resto queda en `detalle_completo`.

Salida real, modo temperado. El audio es [una escala sintética](ejemplos/audio/escala_do_mayor.wav)
con desafinaciones conocidas (0, −8, −30, +5, +22, −15, −42 y −2 cents, más vibrato de ±40 cents en la última nota) y ruido a 35 dB:

```json
{"audio":"ejemplos/audio/escala_do_mayor.wav","duracion_s":7.36,"modo":"temperado",
 "resumen":{"notas":8,"rango":"C4–C5","porcentaje_dentro_25_cents":75.0,"desviacion_media_cents":-7.8,
   "desviacion_abs_media_cents":13.6,"tendencia":"centrado","deriva_cents":-1.0,
   "estabilidad":{"estable":7,"vibrato":1,"inestable":0}},
 "notas":[{"t":0.4,"dur":0.62,"nota":"C4","cents":0,"estabilidad":"estable"},
   {"t":1.12,"dur":0.62,"nota":"D4","cents":-8,"estabilidad":"estable"},
   {"t":1.84,"dur":0.62,"nota":"E4","cents":-30,"estabilidad":"estable"},
   {"t":2.56,"dur":0.62,"nota":"F4","cents":5,"estabilidad":"estable"},
   {"t":3.28,"dur":0.62,"nota":"G4","cents":22,"estabilidad":"estable"},
   {"t":4.0,"dur":0.62,"nota":"A4","cents":-15,"estabilidad":"estable"},
   {"t":4.72,"dur":0.62,"nota":"B4","cents":-42,"estabilidad":"estable"},
   {"t":5.44,"dur":1.43,"nota":"C5","cents":-2,"estabilidad":"vibrato","vibrato_hz":5.5,"vibrato_pp_cents":84}],
 "confianza":{"valor":1.0,"nivel":"alta"},"advertencias":[]}
```

Otras salidas reales:
- [Modo tonalidad (Sol mayor)](ejemplos/salidas/analizar_afinacion_tonalidad.json): el F4 cantado aparece como F#4 a −95 cents, porque en Sol mayor corresponde F#.
- [Con referencia MIDI](ejemplos/salidas/analizar_afinacion_referencia_midi.json): melodía cantada una octava abajo, que entra 1 s tarde, con una nota 33 cents calante, una entrada 140 ms tarde, una nota inestable y vibrato en la final. El servidor informa `transposicion_octavas: -1`, `desfase_inicio_ms: 1003`, la nota a −33 cents, la entrada a +134 ms y la nota `inestable`.

### `transcribir(audio, idioma?)`

Transcripción local con faster-whisper, con timestamps por segmento y por palabra. `idioma`
acepta "es", "en", "en-US", "español"…; si se omite, se detecta automáticamente. Devuelve `texto`, `segmentos`
[{t, fin, texto}] y `palabras` [{p, t, fin}]. Si no cabe en ~2 KB, primero se omiten las
palabras y luego los segmentos, que quedan completos en `detalle_completo`.
[Salida real](ejemplos/salidas/transcribir_en.json) sobre [voz sintética](ejemplos/audio/discurso_en.wav):

```json
{"audio":"ejemplos/audio/discurso_en.wav","duracion_s":15.79,"idioma":"en","prob_idioma":0.94,
 "texto":"Um, so today I want to talk about, uh, public speaking. You know, most people feel nervous, like, before a big talk. I mean, that is completely normal. The key is to practice with real feedback.",
 "segmentos":[{"t":0.0,"fin":4.26,"texto":"Um, so today I want to talk about, uh, public speaking."},
   {"t":5.32,"fin":9.58,"texto":"You know, most people feel nervous, like, before a big talk."}, "…"],
 "palabras":[{"p":"Um,","t":0.0,"fin":0.28}, "…"],
 "confianza":{"valor":1.0,"nivel":"alta"},"advertencias":[]}
```

### `metricas_discurso(audio, idioma, umbral_pausa_s=0.7)`

| Bloque | Campos |
|---|---|
| `ritmo` | `palabras`, `tiempo_habla_s` (de la 1.ª a la última palabra), `palabras_por_minuto`, `ppm_sin_pausas_largas` |
| `pausas` | silencios ≥ `umbral_s` medidos por energía del audio: `cantidad`, `total_s`, `max_s`, `por_minuto`, `lista` [{t, dur, tras: palabra previa}] |
| `muletillas` | `total`, `por_minuto`, `por_tipo`, `ocurrencias` [{t, texto}] |
| `tono` | `f0_mediana_hz`, `desv_semitonos`, `rango_p10_p90_semitonos`, `monotono` (desv < 2 semitonos), `tramos_monotonos` [{t, fin}] (ventanas de 8 s) |
| `volumen` | nivel por palabra: `media_dbfs`, `desv_entre_palabras_db`, `rango_p10_p90_db`, `variacion_baja` (desv < 3 dB) |
| `segmentos` | transcripción con timestamps |

**Muletillas.** Las listas de español e inglés están en
[`muletillas.toml`](src/voice_coach_mcp/habla/muletillas.toml) y tienen tres tipos de entrada:

- **Vocalizaciones** ("eh", "mmm", "um"): siempre cuentan.
- **Expresiones** ("o sea", "¿no?", "you know"): siempre cuentan.
- **Ambiguas** ("este", "bueno", "like", "so"): solo cuentan aisladas, es decir, al inicio de la frase, junto a una coma o rodeadas de una pausa de 0,3 s o más. "Este libro" o "I like it" no cuentan.

Para usar tus propias listas, copia el archivo y apunta `VOICE_COACH_MULETILLAS` a la copia. Para
que Whisper no "limpie" las muletillas, en esta tool se le pasa un prompt inicial que las
contiene; aun así, un "eh" muy breve puede no transcribirse.

Salida real ([completa](ejemplos/salidas/metricas_discurso_es.json)) sobre un
[discurso sintético en español](ejemplos/audio/discurso_es.wav) con pausas insertadas de 1,2 s y 0,9 s
y 7 muletillas:

```json
{"audio":"ejemplos/audio/discurso_es.wav","duracion_s":22.98,"idioma":"es",
 "ritmo":{"palabras":43,"tiempo_habla_s":22.3,"palabras_por_minuto":116,"ppm_sin_pausas_largas":127},
 "pausas":{"umbral_s":0.7,"cantidad":2,"total_s":2.0,"max_s":1.16,"por_minuto":5.4,
   "lista":[{"t":3.9,"dur":1.16,"tras":"importante"},{"t":15.56,"dur":0.87,"tras":"nerviosos"}]},
 "muletillas":{"total":7,"por_minuto":18.8,
   "por_tipo":{"bueno":1,"eh":1,"o sea":1,"este":1,"mmm":1,"entonces":1,"no?":1},
   "ocurrencias":[{"t":0.0,"texto":"bueno"},{"t":1.06,"texto":"eh"},{"t":4.56,"texto":"o sea"}, "…"]},
 "tono":{"f0_mediana_hz":103,"desv_semitonos":1.44,"rango_p10_p90_semitonos":3.6,"monotono":true,
   "tramos_monotonos":[{"t":0.0,"fin":20.0}]},
 "volumen":{"media_dbfs":-21.4,"desv_entre_palabras_db":2.6,"rango_p10_p90_db":5.2,"variacion_baja":true},
 "segmentos":[{"t":0.0,"fin":3.74,"texto":"Bueno, eh, hoy quiero hablarles de un tema importante."}, "…"],
 "confianza":{"valor":1.0,"nivel":"alta"},"advertencias":[]}
```

La voz de espeak-ng es muy plana, por eso sale `monotono: true` y `variacion_baja: true`.
[Ejemplo en inglés](ejemplos/salidas/metricas_discurso_en.json).

## Prompts MCP

| Prompt | Argumentos | Uso |
|---|---|---|
| `sesion_canto` | `nivel`, `objetivo`, `referencia_midi` | calentamiento → ejercicio → `analizar_afinacion` → feedback → siguiente ejercicio |
| `sesion_pronunciacion` | `nivel`, `foco` | pares mínimos y frases (requiere `evaluar_pronunciacion`, fase 3) |
| `sesion_oratoria` | `contexto`, `duracion_objetivo_s` | ritmo, pausas, muletillas y variación de tono/volumen con `metricas_discurso` |

En Claude Desktop aparecen en el botón **+** → *Agregar desde voice-coach*; en Claude Code, como `/mcp__voice-coach__sesion_canto`.

## Configuración

| Variable | Por defecto | Uso |
|---|---|---|
| `VOICE_COACH_DIR` | `~/VoiceCoach` | grabaciones (`grabaciones/`) y análisis |
| `VOICE_COACH_MAX_SEGUNDOS` | `120` | duración máxima de `grabar_audio` |
| `VOICE_COACH_A4_HZ` | `440` | diapasón de referencia |
| `VOICE_COACH_MAX_BYTES` | `2048` | presupuesto de cada respuesta |
| `VOICE_COACH_WHISPER_MODEL` | `small` | modelo de Whisper (`tiny`, `base`, `small`, `medium`, `large-v3`, `turbo`…) |
| `VOICE_COACH_WHISPER_DEVICE` | `cpu` | `cpu` o `cuda` (CTranslate2 no usa la GPU de los Mac) |
| `VOICE_COACH_WHISPER_COMPUTE_TYPE` | `int8` | tipo de cómputo de CTranslate2 |
| `VOICE_COACH_MULETILLAS` | — | TOML propio con listas de muletillas |

## Cómo mide la afinación

1. **Pitch**: pYIN (librosa) decide qué frames tienen voz y da una altura gruesa. Cada frame se
   refina midiendo los picos de sus armónicos con interpolación parabólica, lo que da ~1 cent de
   precisión entre C2 y C6.
2. **Notas**: se separan por silencios, por caídas de energía de ≥ 9 dB (notas repetidas) y por
   cambios de altura de más de medio tono sostenidos durante 60 ms. Para segmentar, el contorno se
   suaviza ~200 ms, así el vibrato no parte la nota. Se descartan fragmentos de menos de 80 ms y
   los que pYIN no considera voz.
3. **Altura de la nota**: la mediana de su parte central (se ignora el 20 % inicial de ataque o
   portamento). **Vibrato**: más de la mitad de la energía de la oscilación está entre 4 y 8 Hz.
   **Inestable**: la desviación estándar supera 15 cents sin un vibrato regular.
4. **Con MIDI**: se busca la octava y el desfase que mejor superponen ambos contornos. Luego las
   notas se alinean con Needleman-Wunsch (altura + tiempo), permitiendo notas omitidas y extra, y se
   ajusta una recta `t_cantado = a·t_ref + b` (tempo relativo y desfase). La entrada de cada nota
   se mide respecto de esa recta.
5. **Calidad**: clipping (> 0,1 % de muestras saturadas), ruido (SNR estimado < 15 dB entre los
   frames fuertes y los débiles; requiere alguna pausa en la grabación) y duración.

Limitaciones conocidas: está pensado para una sola voz. Con acompañamiento de fondo o polifonía,
la detección se degrada. Dos notas iguales cantadas en legato perfecto, sin consonante ni
respiración entre ellas, cuentan como una sola.

## Desarrollo

```bash
uv run pytest                     # tests rápidos (audio sintético, micrófono simulado)
uv run pytest -m modelos          # Whisper real (tiny) sobre voz de espeak-ng; requiere --extra habla y espeak-ng
uv run ruff check . && uv run ruff format --check .
uv run python ejemplos/generar_ejemplos.py   # regenera ejemplos/ llamando al servidor por stdio
```

El servidor usa el SDK oficial `mcp` 2.x, donde `FastMCP` pasó a llamarse `MCPServer`
(`from mcp.server.mcpserver import MCPServer`); la API de decoradores es la misma.

Estructura:

```
src/voice_coach_mcp/
  server.py        tools y prompts MCP (capa fina)
  audio/           carga, grabación y calidad del audio
  canto/           pitch, teoría musical, referencia MIDI, afinación
  habla/           transcripción (faster-whisper), métricas de discurso, listas de muletillas
  salida.py        presupuesto de 2 KB y JSON de detalle
  prompts.py       textos de los prompts de sesión
tests/             tests con audio y MIDI sintéticos
ejemplos/          audios sintéticos y salidas reales de cada tool
```
