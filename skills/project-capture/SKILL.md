---
name: project-capture
description: Hace capturas de pantalla de webs y de proyectos web (locales o publicados) con Playwright, descubre sus menús, campos y selectores, y ejecuta flujos paso a paso (clics, rellenar formularios) que generan capturas numeradas y un report.md. Úsala cuando el usuario pida «haz una captura de esta web/pantalla», «cómo se ve esta página», «documenta las pantallas», «escribe un tutorial paso a paso con capturas», «qué campos/botones/selectores tiene esta pantalla», «comprueba en la app si…», «captura en móvil/modo oscuro», o quiera verificar con la aplicación real algo que dice la documentación, aunque no diga «captura».
---

# project-capture

Script: `scripts/capture.mjs`, en la carpeta de esta skill (la que contiene este `SKILL.md`; llámala `$PC`). Usa `playwright-core` con el Chromium/Chrome del sistema, sin descargar navegadores.

## 0. Preparación (una vez por equipo)

1. `node -v` (≥ 18). Si no existe `$PC/scripts/node_modules`, **pide permiso** y ejecuta `npm install --prefix $PC/scripts`.
2. Navegador: lo detecta solo (`/usr/bin/chromium`, Chrome, Brave, macOS…) o usa `$CHROME_PATH` / `--browser`. Si no hay ninguno, propón `npx playwright@1.49.1 install chromium` (pide permiso).

## 1. Delimitar el objetivo

- **Web publicada**: la URL. Solo páginas que el usuario indique; no rastrees el sitio entero.
- **Proyecto local**: busca cómo se sirve (README, `package.json` scripts, `pom.xml`, `docker-compose`, `CLAUDE.md`/`ai-context/` del proyecto). Si ya está arrancado, usa su URL (`curl -sI` para comprobarlo). **No arranques servidores sin preguntar**: pueden lanzar tareas programadas, enviar correos o tocar bases de datos. HTML estático: pasa la ruta del fichero o carpeta (se abre como `file://`).
- **Con login**: `node $PC/scripts/capture.mjs login <url> --storage captures/.auth/session.json` abre el navegador, el usuario inicia sesión a mano y se guarda la sesión; después pasa `--storage` a los demás comandos. **Nunca pidas ni escribas contraseñas en ficheros**; si un flujo necesita un valor secreto, usa `"$ENV:NOMBRE"` (se lee del entorno, no se imprime y el campo sale tapado en las capturas).

## 2. Comandos

```bash
node $PC/scripts/capture.mjs shot <url|ruta> [--full] [--selector CSS] [--name N] [--out DIR]
node $PC/scripts/capture.mjs discover <url|ruta> [--out DIR]       # PNG completo + .md/.json de elementos
node $PC/scripts/capture.mjs flow <flow.json> [--out DIR]           # pasos + capturas numeradas + report.md
```

Opciones comunes: `--viewport 390x844` (móvil), `--dark`, `--wait 2000|CSS`, `--storage FILE`, `--headed`, `--ignore-https`, `--timeout MS` (por acción, 10000 por defecto). Salida por defecto: `./captures/` del directorio actual.

- **`discover`** lista enlaces, botones, campos y menús visibles (separando navegación y contenido) con un **selector sugerido** por elemento, en este orden de preferencia: `data-testid`/`data-test`/`data-cy` → `#id` estable → `role=<rol>[name="<texto>"]` → `[name=…]`. Úsalo antes de escribir un flujo en vez de adivinar selectores, y para responder «qué tiene esta pantalla».
- **`flow`**: ver `examples/flow.example.json`. Acciones: `goto` (`url`, relativa a `baseUrl`), `click`, `hover`, `fill` (`value`), `select`, `check`, `press` (`key`), `wait` (`ms` o `selector`), `screenshot` (`name`, `caption`, `highlight` para remarcar un elemento en rojo, `selector` para recortar, `full`), `discover`. Cualquier paso admite `"screenshot": "nombre"` y `"caption"` para capturar justo después, y `"wait"`. Si un paso falla, guarda `ERROR.png` y lo anota en el `report.md`, que también recoge los errores de la consola del navegador.

## 3. Procedimiento típico

1. `discover` de la pantalla inicial → lee el `.md` generado (no el PNG entero si no hace falta).
2. Escribe el flujo en `captures/<tarea>/flow.json` con los selectores descubiertos; haz `discover` de cada pantalla nueva que aparezca.
3. Ejecuta `flow`; si falla, mira `ERROR.png` y el selector, corrige y repite.
4. **Mira las capturas** (léelas con la herramienta de lectura de imágenes) antes de afirmar cómo se ve algo.
5. Para tutoriales: usa `report.md` como borrador (capturas en orden con su `caption`) y redacta los pasos a partir de lo que realmente se ve.

## Reglas de seguridad

- **No ejecutes acciones con efectos** (guardar, enviar, borrar, aprobar, pagar, publicar) en entornos compartidos o de producción sin confirmación explícita. En tutoriales, captura el formulario relleno y para **antes** del botón final, salvo que el usuario diga que el entorno es local o de pruebas.
- Los diálogos `alert/confirm` se descartan automáticamente (se cancela la acción) y se registran.
- `captures/.auth/` contiene cookies de sesión: no lo subas a git ni lo compartas (sugiere añadir `captures/` a `.gitignore` o `.git/info/exclude`).
- Antes de compartir capturas, revisa que no muestren datos personales, credenciales o información interna; si los muestran, avisa al usuario.
- Respeta las reglas del `CLAUDE.md` del proyecto (entornos, datos, servidores).
