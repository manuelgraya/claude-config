# claude-config

Mis skills de Claude Code.

| Skill | Qué hace |
|---|---|
| `md-to-latex` | Convierte documentación Markdown en un proyecto LaTeX/PDF profesional |
| `ai-context-vault` | Crea un vault de Obsidian `ai-context/` para agentes + un `CLAUDE.md` que lo enlaza |
| `ai-context-verify` | Verifica que las notas de `ai-context/` siguen al día con el código |
| `ai-review` | Revisión de código según las reglas del proyecto y generación de `ai-test/` |

## Instalación

```bash
git clone <repo> ~/Work/claude-config
~/Work/claude-config/install.sh
```

`install.sh` crea un enlace en `~/.claude/skills/<skill>` por cada skill del repo. No toca las skills que no están aquí (las locales siguen siendo locales). Si ya existe una carpeta real con el mismo nombre, la mueve a `<skill>.bak.<timestamp>`. Vuelve a ejecutarlo tras un `git pull` que añada skills.

## Ejemplo

[`claude-example.md`](claude-example.md) muestra el `CLAUDE.md` que deja `ai-context-vault` en un proyecto (ficticio): leer `ai-context/index.md` antes de explorar código, mantener las notas al día con `covers:`/`verified:` y las reglas duras del proyecto.
