---
name: ai-review
description: Revisión de código orientada al proyecto. Revisa el diff actual (o una rama/ticket/revisión) contra las reglas propias del proyecto (`ai-context/review-checklist.md`, `pitfalls.md` y las reglas del CLAUDE.md), complementa con /code-review para bugs genéricos y genera una carpeta `ai-test/` con un `ai-test.md` (qué se prueba y cómo) más los ficheros de prueba necesarios (scripts estáticos, SQL de solo lectura, borradores JUnit, flujos de UI) y ejecuta los seguros. Úsala cuando el usuario pida «revisa el código/mis cambios/esta rama», «code review», «revisión antes de commit/merge», «qué hay que probar de este cambio», «genera las pruebas (ai-test)», en cualquier proyecto, tenga `ai-context/` o no.
---

# ai-review

Revisión + plan de pruebas de un cambio, usando el conocimiento del proyecto en vez de redescubrirlo. **No modifica el código del proyecto** (salvo que el usuario pida `--fix`); solo escribe en `ai-test/`.

Entradas posibles (`args`): vacío = cambios sin commitear + commits de la rama no integrados; `<rama>`/`<commit>..<commit>`/`rNNNN:rMMMM`; `#ticket`; rutas concretas. Pregunta solo si el alcance es ambiguo.

## 1. Alcance y diff

Git: `git status --short`, `git diff --stat`, `git diff <base>...HEAD` (base = `development`/`master`/rama por defecto si existe; si no, últimos N commits que indique el usuario) más working tree y staged. SVN: `svn status`, `svn diff` (sin red no hay `-r`). Para ruido de finales de línea: compara `git diff --stat` con `git diff --ignore-cr-at-eol --stat` y **revisa solo los cambios reales**, avisando del ruido. Lista los ficheros cambiados agrupados por tipo (Java, JS, SQL, XML, config).

## 2. Cargar contexto (barato primero)

1. `CLAUDE.md` del proyecto (reglas duras) y `ai-context/index.md`.
2. `ai-context/review-checklist.md` (**las reglas de revisión del proyecto**) y `pitfalls.md`.
3. Notas cuyo `covers:` toca el diff: `python3 -I ~/.claude/skills/ai-context-verify/scripts/ai_context_check.py stale ai-context` (las marcadas REVIEW; léelas).
4. Si no existe `ai-context/` o `review-checklist.md`: usa solo CLAUDE.md/README y las comprobaciones universales de abajo, y ofrece crear el checklist al terminar (con `ai-context-vault`).
No leas notas que el diff no necesita.

## 3. Comprobaciones

a. **Checklist del proyecto**: aplica cada regla R# de `review-checklist.md` a los ficheros que le correspondan, ejecutando el comando de comprobación que indica (grep/git). Anota hallazgo, fichero:línea y regla.
b. **Universales** (si el checklist no las cubre): secretos/credenciales/rutas locales/tokens en el diff; ficheros que no deberían subirse (IDE, `target/`, binarios, dumps); código muerto o comentado añadido; `System.out`/`console.log`/`printStackTrace` nuevos; TODO/FIXME nuevos; cambios de firma pública sin buscar usos (`grep -r` en el proyecto y hermanos); manejo de errores que se traga excepciones; tests ausentes para lógica nueva.
c. **Bugs generales**: lanza la skill `code-review` sobre el mismo objetivo (nivel `medium` salvo que el usuario diga otro) y fusiona sus hallazgos con los tuyos sin duplicar. Si no está disponible, revisa tú la lógica: condiciones límite, null, transacciones, concurrencia, consultas N+1, SQL/JSON construidos por concatenación.
d. **Verifica cada hallazgo** antes de reportarlo: abre el código real, confirma que el escenario ocurre y descarta lo que sea especulación. Clasifica: **blocker / major / minor / nit**. Es preferible pocos hallazgos ciertos que muchos dudosos.

## 4. Generar `ai-test/`

En la raíz del proyecto. Si ya existe con contenido, muévelo a `ai-test/_history/<fecha-hora>/` antes. Excluye `ai-test/` del control de versiones en local (git: `.git/info/exclude`; svn: no lo añadas) salvo que el usuario quiera compartirlo.

Contenido:

- **`ai-test/ai-test.md`**, obligatorio (plantilla abajo): qué cambio se prueba, riesgos, matriz de pruebas, cómo ejecutar, resultados.
- Solo los ficheros que hagan falta, por tipo:
  | Tipo | Fichero | Seguridad |
  |---|---|---|
  | Estáticas (grep/git sobre el diff) | `static_checks.sh` | **safe** |
  | SQL de verificación | `sql/NN_*.sql` + `run_sql.sh` | **safe** solo si todo es `SELECT`; escrituras = needs-confirmation |
  | JUnit (borradores) | `junit/*.java` (no tocar `src/test` salvo petición) + comando `mvn` en el md | **safe** si no usan BD/red |
  | HTTP/API | `http/*.sh` (curl) | needs-confirmation (requiere app arrancada) |
  | Flujos de UI | `ui/*.json` (para una skill de captura de UI, si existe) | needs-confirmation |
  | Datos de prueba | `data/*` anonimizados | nunca datos reales ni secretos |
- Diseña las pruebas **a partir del cambio y de los riesgos detectados**: caminos felices, límites, estados/roles/variantes que el checklist marca (p. ej. «y para los otros tipos de proyecto»), regresiones cercanas y cualquier hallazgo que se pueda demostrar con una prueba.

### Reglas de seguridad al ejecutar

Respeta las reglas duras del CLAUDE.md. **Ejecuta tú solo las pruebas `safe`** (estáticas, SELECT, unit sin BD, compilación si es barata y sin efectos). Para `needs-confirmation` (arrancar servidor, escrituras en BD, correo, SFTP, UI contra la app, cualquier cosa contra entornos compartidos): no las ejecutes; deja el comando y pide confirmación explícita al usuario. Nunca imprimas contraseñas (para SQL en docker: lee la contraseña del entorno del contenedor y pásala por variable de entorno, como indica el vault del proyecto). Toda prueba de escritura necesita copia/backup previo y rollback descritos en el md.

### Plantilla `ai-test/ai-test.md`

```markdown
# ai-test: <título corto del cambio>

- Proyecto / rama / base: <...>  · Revisión: <git hash | svn rev> · Fecha: <YYYY-MM-DD>
- Alcance: <ficheros/áreas y ticket>
- Resumen del cambio: <2-4 líneas>

## Qué se está probando
<Comportamiento y riesgos que cubren las pruebas; qué queda fuera y por qué>

## Matriz de pruebas
| ID | Qué verifica | Tipo | Seguridad | Fichero / comando | Esperado | Resultado |
|---|---|---|---|---|---|---|
| T1 | ... | static | safe | `bash ai-test/static_checks.sh` | 0 hallazgos | PASS / FAIL / NOT RUN |

## Cómo ejecutarlas
<Comandos exactos, precondiciones (app arrancada, BD local, backup), orden y limpieza>

## Hallazgos de la revisión
| # | Gravedad | Regla | Ubicación | Descripción y escenario | Prueba |
|---|---|---|---|---|---|

## Resultados y pendientes
<Qué se ejecutó, salidas relevantes resumidas, qué requiere confirmación del usuario>
```

## 5. Informe al usuario

Corto: veredicto (listo / listo con reservas / no listo), hallazgos por gravedad con `fichero:línea` y la regla, qué pruebas se ejecutaron y su resultado, cuáles esperan confirmación, notas del `ai-context` que hay que actualizar (y ofrece hacerlo con `ai-context-verify`), y la ruta de `ai-test/ai-test.md`. Si el diff solo tenía ruido o cambios triviales, dilo y no inventes pruebas.

## Principios

- Reglas específicas del proyecto viven en su `review-checklist.md`, no aquí: esta skill no debe contener datos de un proyecto concreto.
- Revisa el **diff**, no el repo entero; lee código circundante solo para entender el cambio.
- Cada regla del checklist tiene un comando de comprobación: ejecútalo en vez de «opinar».
- Nunca publiques ni envíes el informe fuera (PR, chat, issues) sin que el usuario lo pida.
