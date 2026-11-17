<!--
Ejemplo de CLAUDE.md de un proyecto que usa las skills de este repo.
Lo genera `ai-context-vault` en la raíz del proyecto, junto a la carpeta `ai-context/`.
El proyecto es ficticio: sustituye nombres, notas y reglas por los del tuyo.
Va en inglés a propósito (más compacto para el agente). Objetivo: ≤ ~300 palabras.
-->

# Acme Orders (`acme-orders`)

Java 8 + Spring XML WAR + jQuery frontend. Web app to manage purchase orders and invoices for retail stores.

## AI context (read this instead of exploring the code)

A curated English Obsidian vault lives in `ai-context/`. **Before exploring source, read `ai-context/index.md`** (one line per note), then open only the 1-3 notes relevant to the task. Do not read whole notes "just in case" and do not re-derive what they already state. If you find a note wrong or stale while working, fix it in the same change. Rules for editing the vault are at the bottom of `ai-context/index.md`.

Quick routing: order lifecycle/status → `order-lifecycle` · Java conventions → `backend-layers` · DB/entities → `persistence-db` · JS/UI → `frontend` · new feature → `add-feature-recipe` · "which file?" → `where-to-look` · acronyms → `glossary` · risks → `pitfalls` · reviewing a diff → `review-checklist` (or use the `ai-review` skill).

## Keep the context current (mandatory)

- Each note has `covers:` (source globs) and `verified:` (git commit + date). **If you change code under a note's `covers:`, update that note in the same change and bump its `verified:`** (`python3 -I ~/.claude/skills/ai-context-verify/scripts/ai_context_check.py stamp ai-context --notes <note>.md`).
- If you notice a note contradicts the code, fix the note immediately.
- After big merges/version bumps, or when asked to audit, use the `ai-context-verify` skill (`stale` lists notes whose covered files changed).
- Sibling projects have their own vault, e.g. `../common-lib/ai-context/index.md` (base classes, JSON/exception model, auth). Read it when the task touches `../common-lib`.

## Hard rules

- `pom.xml` contains real credentials. Never print, copy, or send them anywhere.
- Never `git add .` / `git commit -a`. Never push without checking `git remote -v` and asking. Only commit when asked.
- Schedulers start with the app and can send **real emails**; do not start the server without asking.
- Before DB writes: confirm the target is the local database (anonymized data) and take a backup. Never print the DB password.
- Java 8 only (no `List.of`, no `var`). `OrderFacadeImpl` is huge: never read it whole, find methods by name.
- New entity ⇒ register in `persistence.xml`. New JS file ⇒ register in `app.js`. Schema change ⇒ `UPGRADE_*.sql` + `_ROLLBACK`.
- Sibling projects in `../` use another VCS and are not this repo: ask before editing them.
