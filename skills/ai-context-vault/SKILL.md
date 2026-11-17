---
name: ai-context-vault
description: Crea (o actualiza) un contexto en Obsidian para agentes de IA dentro de un directorio de proyecto, más un CLAUDE.md corto que enlaza a él, para que los agentes lean notas compactas en inglés en vez de explorar el código y se ahorren tokens. Úsala cuando el usuario pida «crear un contexto/vault de Obsidian para los agentes», «un CLAUDE.md que lea el contexto enlazado», «ahorrar tokens en este directorio», «documentar este proyecto para IA», o repita ese encargo para otro directorio o proyecto hermano, aunque no diga «skill».
---

# ai-context-vault

Genera `ai-context/` (vault Obsidian, **todo en inglés**) + `CLAUDE.md` (≤ ~300 palabras) en el directorio objetivo. Un agente futuro lee `CLAUDE.md` → `ai-context/index.md` → 1-3 notas, y no vuelve a explorar el código.

Si ya existe otro vault `ai-context/` en un proyecto hermano, úsalo como referencia de estructura y tono; si no, sigue las plantillas de abajo.

## Pasos

1. **Delimitar**: directorio objetivo (por defecto el cwd). Si ya existe `ai-context/` o `CLAUDE.md`, léelos y **actualiza**, no sobrescribas. Pregunta solo si el alcance es ambiguo (p. ej. varios proyectos hermanos).
2. **Reunir fuentes baratas primero**, en este orden: `CLAUDE.md`/README existentes, memoria del usuario (`~/.claude/projects/*/memory/`), vaults Obsidian existentes (`~/Documents/Obsidian Vault/...`, destila, no copies), `pom.xml`/`package.json`/build files, `git log --oneline | head`, árbol de directorios (`find -maxdepth 3`, excluyendo `target`, `node_modules`, `.git`). Solo después lee código, y solo lo necesario para lo que falte (puntos de entrada, convenciones, clases clave). Para proyectos grandes, usa agentes Explore en paralelo para zonas independientes.
3. **Escribir las notas** (plantilla abajo; cada una con `summary:`, `verified:` y `covers:`, ver «Frontmatter»). Una nota = un tema, ≤ ~150 líneas, hechos y no narrativa, tablas y listas cortas, fragmentos de código solo si fijan una convención. Marca lo no confirmado como *(inferred)*.
4. **Escribir `ai-context/index.md`**: tabla `[[nota]] | Read when` de una línea por nota + sección «Maintaining this vault».
5. **Escribir `CLAUDE.md`**: ver plantilla.
6. **Git**: si el repo es del equipo, **no commitees ni modifiques ficheros rastreados**. Añade `ai-context/` y `CLAUDE.md` a `.git/info/exclude` (exclusión local), salvo que el usuario pida compartirlos. Dilo en el resumen final.
7. **Sellar y validar**: `python3 -I ~/.claude/skills/ai-context-verify/scripts/ai_context_check.py stamp ai-context` (rellena `verified:` con commit git o revisión svn + fecha) y `... refs ai-context` (debe dar 0 referencias no encontradas; las intencionadas van a `ai-context/.checkignore` con motivo); todos los `[[enlaces]]` resuelven a un fichero (`for l in $(grep -oh '\[\[[^]]*\]\]' *.md | sort -u | tr -d '[]'); do [ -f "$l.md" ] || echo MISSING $l; done`); sin secretos (`grep -riE 'password|passwd|secret|token|api[_-]?key' ai-context CLAUDE.md` y revisa cada coincidencia); `.obsidian/app.json` con `{}` para que abra como vault.
8. **Resumir al usuario** en pocas líneas: dónde quedó, qué notas, qué es *(inferred)*, qué se excluyó de git.

## Reglas de contenido

- **Inglés siempre**, aunque el usuario hable español y el código tenga comentarios en español.
- **Nada de secretos**: contraseñas, tokens, claves, URLs con credenciales, datos personales. Si el proyecto los tiene en un fichero, escribe «contains credentials, never copy» y la ruta, nunca el valor.
- Prioriza lo que **no se deduce rápido del código**: convenciones, trampas, pasos que se olvidan (registros manuales, orden de carga), flujos de negocio, siglas, por qué algo es raro, riesgos de entorno. No documentes lo que `ls` o un `grep` responde en una llamada.
- Rutas relativas a la raíz del proyecto; **nombres de método/clase en vez de números de línea** (derivan).
- Enlaza con `[[nota]]` en vez de repetir. Cada nota empieza con frontmatter `summary:` de una línea (sirve para decidir si abrirla).
- Mide el ahorro: `index.md` + `CLAUDE.md` deben quedar en ~700 palabras; el resto se lee bajo demanda.

## Notas típicas (adapta al proyecto; omite las que no apliquen)

`index` · `overview` (qué es, stack, layout del repo, cifras) · `workspace-map` (proyectos hermanos/dependencias) · `architecture`/`backend-layers` (flujo de petición y convenciones) · `persistence-db` · `security-permissions` · `frontend` · notas de **dominio** (una por concepto central) · `integrations-and-batch` · `glossary` · `where-to-look` (tema → ficheros) · `add-feature-recipe` (checklist de punta a punta) · `build-env-git` (perfiles, CI, depuración por síntoma, convenciones de commit) · `review-checklist` (reglas R1..Rn de revisión con el comando que comprueba cada una; las usa la skill `ai-review`) · `pitfalls` (qué puede salir mal / peligroso).

## Frontmatter obligatorio (permite que las notas no se queden obsoletas)

```yaml
summary: <one line>
verified: "git <hash> @ YYYY-MM-DD"      # o "svn rNNNN @ YYYY-MM-DD"; lo pone `stamp`
covers: ["src/main/java/**", "pom.xml"]    # globs relativos a la raíz del proyecto que la nota describe
```

`covers:` es lo que usa `ai-context-verify stale` para saber qué notas revisar cuando cambia el código. Sé preciso: ni tan amplio que todo marque REVIEW, ni tan estrecho que un cambio relevante pase inadvertido. Proyectos **SVN**: sin servidor solo hay `svn status` y mtimes; funciona igual.

## Plantilla de nota

```markdown
---
summary: <one line: what this note answers>
verified: "git abc1234 @ 2026-01-01"
covers: ["path/glob/**"]
tags: [area]
---

# Title

<facts, tables, short lists; links to [[other-note]]>
```

## Plantilla de CLAUDE.md

```markdown
# <Project> (<artifact>)

<one-line what it is + stack>

## AI context (read this instead of exploring the code)

A curated English Obsidian vault lives in `ai-context/`. **Before exploring source, read `ai-context/index.md`**, then open only the 1-3 notes relevant to the task. Do not read notes "just in case" and do not re-derive what they state. 

Quick routing: <topic> → `<note>` · ...

## Keep the context current (mandatory)
- Each note has `covers:` (source globs) and `verified:` (VCS revision + date). **If you change code under a note's `covers:`, update that note in the same change and bump `verified:`** (`python3 -I ~/.claude/skills/ai-context-verify/scripts/ai_context_check.py stamp ai-context --notes <note>.md`).
- If a note contradicts the code, fix the note immediately. After big merges/version bumps or on request, use the `ai-context-verify` skill.
- Sibling projects' vaults: `../<project>/ai-context/index.md`: read when the task touches them.

## Hard rules
- <secrets, git, destructive-op, environment, language-version, "register X when adding Y" rules; ≤ 8 bullets>
```

## Mantenimiento

Para auditar o refrescar un vault existente usa la skill **`ai-context-verify`** (delta por `covers:`/`verified:`, no regeneres todo).

Cuando el usuario pida «actualiza el contexto», compara con `git log` desde la fecha/versión de la nota `overview` y edita solo las notas afectadas. Actualiza la línea «Analyzed: version, branch, date».
