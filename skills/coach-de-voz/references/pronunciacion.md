# Pronunciación en inglés: leer `evaluar_pronunciacion` y corregir

## Cómo pedir la evaluación

- Pasa el **texto exacto** que se leerá en `texto_esperado`, y muéstraselo al usuario antes de grabar.
- Funciona mejor con frases completas de 5–15 palabras que con palabras sueltas. Para pares
  mínimos, arma una frase: "I said ship, not sheep".
- **Limitación**: el modelo usa el contexto y a veces "corrige" un error si la palabra correcta es
  muy probable (por ejemplo, oye *think* aunque se dijo *sink*). Por eso alterna frases con
  palabras poco predecibles por el contexto.
- La r vibrante española no se marca como error (se trata como /ɹ/), y la aspiración de /p t k/ no
  se mide. Si la escuchas como problema, menciónala como observación, no como dato.

## Lectura

- `puntaje_global`: ≥ 90 muy bien · 75–90 se entiende con errores puntuales · < 75 foco de trabajo.
- `confusiones_frecuentes`: el patrón más útil. Una confusión que se repite (θ → s ×3) vale más
  que un error aislado.
- `palabras[].errores`:
  - `sustitucion`: se dijo otro fonema.
  - `omision`: falta un fonema. Es típico en grupos consonánticos finales: *asked*, *first*, *-ed*.
  - `insercion`: sobra un fonema. Es típica la *e* antes de *s* + consonante: *(e)school*.
- `omitida: true`: la palabra no se dijo o no se entendió nada.

## Errores típicos de hispanohablantes

| Esperado → detectado | Ejemplo | Cómo se articula | Pares mínimos |
|---|---|---|---|
| θ → s / t | *think* → sink/tink | Punta de la lengua entre los dientes y soplar, sin voz | think/sink, thick/sick, three/tree, path/pass |
| ð → d | *this* → dis | Lengua entre los dientes **con voz** (la garganta vibra) | they/day, then/den, breathe/breed |
| v → b | *very* → berry | Dientes superiores sobre el labio inferior, con voz; los labios no se juntan | very/berry, vote/boat, van/ban |
| iː → ɪ | *sheep* → ship | /iː/ larga y tensa (sonrisa); /ɪ/ corta y relajada | sheep/ship, leave/live, seat/sit, peach/pitch |
| æ → ɛ / a / ʌ | *cat* | Boca muy abierta y mandíbula baja, entre *a* y *e* | cat/cut, bag/bug, hat/hut, man/men |
| ʌ → a / o | *cup* | Vocal corta y relajada, central | cup/cop, luck/lock |
| ʊ → uː | *full* → fool | Corta y relajada, labios poco redondeados | full/fool, pull/pool |
| z → s | *zoo*, *eyes* | La misma posición que /s/, pero con voz (zumbido) | zoo/sue, eyes/ice, prize/price |
| ʃ ↔ tʃ | *ship* → chip | /ʃ/ continua (*shhh*); /tʃ/ con un golpe inicial | ship/chip, wash/watch |
| dʒ → j / ʝ | *jet* → yet | Golpe como /tʃ/ pero con voz | jet/yet, joke/yolk, jam/yam |
| h → x | *hat* con jota | Solo aire, sin fricción en la garganta | hat, house, hello |
| ŋ → n | *thing* → thin | El dorso de la lengua toca el velo del paladar; no se pronuncia la *g* | thing/thin, sing/sin |
| inserción de e antes de s + consonante | *school* → eschool | Empezar directamente en la /s/: *sss-chool* | school, Spain, street, speak |
| omisión de consonantes finales | *asked* → ask, *walked* → walk | Terminar la palabra; *-ed* suena /t/, /d/ o /ɪd/ | walked, played, wanted, first, months |
| vocales sin reducir | *about* → *a-bout* | Sílabas átonas en /ə/ (schwa), cortas | about, banana, problem |

## Progresión

1. Pares mínimos dentro de frases cortas con el fonema objetivo.
2. Frases con el fonema en distintas posiciones (inicio, medio y final de palabra).
3. Lectura de un párrafo corto; luego, habla libre revisada con `transcribir`.
Sube de nivel cuando la confusión objetivo baje a 0–1 en dos tomas seguidas.
