---
name: ai-context-verify
description: Verifica que las notas de un vault `ai-context/` (contexto de Obsidian para agentes de IA) siguen siendo ciertas respecto al código actual, corrige las que no lo sean y re-sella su fecha/revisión para que no se queden obsoletas. Úsala cuando el usuario pida «verificar/validar/actualizar/auditar el contexto (ai-context)», «comprobar que las notas siguen al día con el código», «el contexto está obsoleto», tras cambios grandes en el proyecto (merge, nueva versión, refactor), o cuando un agente detecte que una nota contradice el código.
---

# ai-context-verify

Comprueba un vault `ai-context/` contra el código real y lo deja sellado. Cada nota tiene en su frontmatter:

```yaml
summary: ...
verified: "git abc1234 @ 2026-01-01"   # o "svn r1234 @ 2026-01-01"
covers: ["src/main/java/**", "pom.xml"]     # globs relativos a la raíz del proyecto (** = cualquier profundidad)
```

Script mecánico (solo stdlib): `~/.claude/skills/ai-context-verify/scripts/ai_context_check.py`, ejecútalo siempre con `python3 -I`.

| Comando | Qué hace |
|---|---|
| `refs <vault> [--root DIR]` | Extrae los `` `tokens` `` de las notas (rutas, clases, métodos) y comprueba que existen en el proyecto y en los hermanos. Lo que no encuentra son **candidatos** a afirmación obsoleta. |
| `stale <vault> [--root DIR]` | Lista las notas cuyos ficheros `covers:` cambiaron desde su `verified:` (git: diff + working tree; svn: `svn status`/`diff` y mtime, porque el servidor puede estar sin red). |
| `stamp <vault> [--root DIR] [--notes a.md b.md]` | Pone `verified:` a la revisión/fecha actual. Solo después de verificar. |

`--root` es por defecto el padre del vault. Tokens que no existen a propósito (nombres de ejemplo, configuración ausente por diseño) van uno por línea en `<vault>/.checkignore`, con un comentario del porqué.

## Modos

- **delta** (por defecto, si las notas ya tienen `verified:`): `stale` → revisar solo las notas marcadas REVIEW. Es lo barato y lo normal.
- **full** (primera vez, o el usuario pide auditoría total, o `verified:` falta/«pending»): revisar todas las notas.

## Procedimiento

1. `python3 -I <script> stale <vault>` (y `refs` en modo full, o siempre si hay dudas). Anota qué notas hay que mirar.
2. Para cada nota a revisar:
   a. Lee la nota y, si es delta, el diff relevante (`git diff <rev> HEAD -- <ficheros covers>`; en svn `svn diff` o lee los ficheros cambiados).
   b. **Verifica las afirmaciones concretas contra el código**, no solo la existencia de nombres: cifras (nº de ficheros, líneas, endpoints: recuéntalas con `find`/`wc`/`grep -c`), versiones (`pom.xml`), horarios `cron`, constantes y enums, firmas de métodos, rutas, flujos descritos, valores por entorno. Prioriza lo que, si estuviera mal, haría que un agente actuase mal (reglas, trampas, pasos obligatorios).
   c. Para los tokens `refs` no encontrados: ¿se renombró/eliminó (corrige la nota) o es intencional (añade a `.checkignore` con motivo)?
   d. **Corrige la nota** con ediciones mínimas; sigue las reglas del vault (inglés, hechos, ≤ ~150 líneas, sin secretos, marca dudas como *(inferred)*). Si algo ya no se puede confirmar, bórralo o márcalo *(inferred)*; no lo dejes afirmado.
   e. Si aparece conocimiento nuevo importante que ninguna nota cubre, añádelo a la nota adecuada (o crea una y enlázala en `index.md`) y ajusta `covers:`.
3. Si ficheros cambiados no están cubiertos por ninguna nota (`covers` incompleto), amplía `covers:` de la nota que corresponda.
4. `python3 -I <script> stamp <vault> --notes <notas verificadas>` (todas con `stamp <vault>` en modo full). **No selles notas que no hayas verificado.** Comprueba que el working tree no tenía cambios sin commitear en `covers:` que cambien la verdad: si los tenía, sella igualmente pero menciónalo.
5. Re-ejecuta `refs` (debe quedar en 0 no encontrados) y los enlaces `[[...]]`: `for l in $(grep -oh '\[\[[^]]*\]\]' *.md | sort -u | tr -d '[]'); do [ -f "$l.md" ] || echo MISSING $l; done`.
6. Informa al usuario en pocas líneas: notas revisadas, qué se corrigió (con ejemplos concretos), qué se descartó, qué sigue dudoso.

## Reglas

- El código manda sobre la nota; la nota manda sobre comentarios del código desactualizados solo si lo has comprobado en ejecución/histórico.
- No commitees el vault (suele estar excluido de git/svn). No toques el código del proyecto: esta skill solo edita `ai-context/`.
- Sin secretos en las notas, ni siquiera para «aclarar» un valor.
- En proyectos SVN sin red: `svn log` y `svn diff -r` fallarán; apóyate en `svn status`, mtimes y lectura directa, y dilo en el resumen.
- Para vaults grandes, reparte notas independientes entre agentes en paralelo, pero tú haces el `stamp` final.

## Mantenimiento continuo (para que no se vuelva a quedar obsoleto)

El `CLAUDE.md` del proyecto debe contener la regla: *«Si cambias código bajo el `covers:` de una nota, actualiza esa nota en el mismo cambio y su `verified:`»* (la skill `ai-context-vault` la incluye en su plantilla). Esta skill es la red de seguridad periódica: úsala tras merges grandes, subidas de versión o cuando `stale` marque notas.
