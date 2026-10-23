# Registro de progreso

El registro vive en `~/VoiceCoach/progreso.md` (o en `$VOICE_COACH_DIR/progreso.md`). Se usa con
dos tools del servidor:

- `leer_progreso(entradas=5)` al empezar: devuelve las últimas sesiones en markdown.
- `registrar_progreso(entrada)` al terminar: agrega una sección al final del archivo.

Si tienes acceso directo a archivos (Claude Code), puedes leer el archivo completo para ver
tendencias largas, pero para escribir usa siempre `registrar_progreso`, así el formato queda
consistente.

## Formato de una entrada

```markdown
## 2026-10-23 · Canto · Escala de Do mayor (nivel intermedio)

- **Objetivo**: afinar la parte aguda de la escala.
- **Tomas**: 3 (`escala-do-toma1` … `toma3`)
- **Métricas**: dentro de ±25 cents 62 % → 88 %; desviación media −14 → −4 cents (plano → centrado); B4 −42 → −12 cents.
- **Lo que mejoró**: la B4 y la C5 dejaron de caer; vibrato estable en la nota final (5,5 Hz).
- **Pendiente**: entradas tarde en el compás 3 (~+130 ms).
- **Foco siguiente**: entradas a tiempo con metrónomo; mantener ±20 cents en la parte aguda.
```

Para pronunciación, anota el puntaje global y las confusiones (por ejemplo, "θ → s: 3 → 1"). Para
oratoria, anota ppm, muletillas/min, pausas largas y desviación de tono.

## Reglas

- Una entrada por sesión, al final (no por toma).
- Siempre con números de antes → después y el **foco siguiente**: es lo que se retoma en la
  próxima sesión.
- Sé breve: entre 5 y 8 viñetas.
- Cada 5 sesiones, si el usuario quiere, agrega una entrada `## Resumen …` con la tendencia: qué
  métricas mejoraron de forma sostenida y qué sigue igual.
