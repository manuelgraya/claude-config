---
name: md-to-latex
description: Convert Markdown documentation (a single .md, a docs/ folder, a README, an Obsidian vault, MkDocs, GitBook/mdBook or Docsify content) into a professional, compilable LaTeX project and PDF for technical or project documentation, with cover page, document control, table of contents, code highlighting, callouts, working cross-references and figures. Use this whenever the user wants to turn .md files into LaTeX, .tex or a formal PDF manual, even if they only say "pásame esta documentación a LaTeX", "maquétame los docs", "quiero un PDF profesional de la documentación" or "convert these docs into a manual". Not for writing new LaTeX from scratch or for editing an existing LaTeX project that has no Markdown source.
---

# Markdown to LaTeX

Turn Markdown documentation into a LaTeX project a person can keep editing. The script does the mechanical conversion the same way every time; your job is the judgment around it: the right metadata, a sensible chapter order, and a PDF that actually looks finished.

Keep project details out of this skill. Anything specific to a project (name, client, logo, colors, version, classification) belongs in the command's options or the generated `metadata.tex`.

## 1. Check the tools

Requires `pandoc` and either `latexmk` + `xelatex` or `tectonic`. Optional: `rsvg-convert` (SVG), `magick` (GIF/WebP/BMP/TIFF), `mmdc` (Mermaid), `pdftoppm` (visual review).

```bash
command -v pandoc latexmk xelatex tectonic rsvg-convert magick mmdc pdftoppm
```

If a required tool is missing, stop and ask the user to install it, since it changes their system and may need their password. On Arch: `sudo pacman -S pandoc-cli tectonic`. On Debian/Ubuntu: `sudo apt install pandoc latexmk texlive-xetex texlive-latex-extra texlive-fonts-recommended`.

## 2. Read the sources and gather metadata

Look through the Markdown to understand its scope, language and structure. Take title, organization, version and authors from the docs or the user. Don't invent these: a made-up version, owner or classification on a formal document looks authoritative and is easy to miss. Leave unknown fields out; the template hides them on the cover and shows "—" in document control. Ask only if a missing value matters to this document.

## 3. Preview the chapter order

```bash
python3 <skill-dir>/scripts/md2latex.py SOURCE OUTPUT_DIR --dry-run
```

Order comes from `mkdocs.yml`, `SUMMARY.md` or `_sidebar.md` when present. Otherwise README/index goes first, followed by natural filename order. Files missing from a nav are added at the end, so nothing disappears silently; exclude them with `--exclude` if they aren't meant to be published.

If the order doesn't read like a manual (say, reference before getting started), write one relative path per line in a file and pass `--order-file`. A line `@part Name` opens a part before the next file. Use parts when a long document has clear top-level sections. If the sources contain a reading path, such as an index note, follow it.

Obsidian vaults need no preparation: wikilinks, embeds and callouts, with their titles, are converted. Foldable callouts print expanded.

## 4. Convert and compile

```bash
python3 <skill-dir>/scripts/md2latex.py SOURCE OUTPUT_DIR \
  --title "..." --subtitle "..." --organization "..." --author "..." \
  --doc-version "..." --classification "..." --lang es \
  --accent 1F4E79 --logo path/to/logo.png --build
```

All metadata options are optional. `--lang` accepts `en es fr de pt it`. Run `--help` for the rest.

| Generated | Purpose | Rerunning with `--force` |
|---|---|---|
| `main.tex`, `projectdoc.sty` | Document and visual style | Kept |
| `metadata.tex` | Title, version, revision history, translated labels | Kept |
| `chapters.tex`, `chapters/` | Order and converted content | **Replaced** |
| `figures/`, `diagrams/` | Images and Mermaid sources | **Replaced** |

Warn the user before using `--force` on a project with manual edits in `chapters/`, because those edits are lost. Prefer metadata and style changes, which survive, or edit the Markdown source and regenerate.

## 5. Fix what the script reports

Resolve these rather than passing them along, because each one is a visible defect in the PDF:

| Report | Meaning | Fix |
|---|---|---|
| Broken link or undefined reference | Target file or heading doesn't exist | Fix the Markdown if the intent is clear; otherwise report it |
| Missing or remote image | Local file absent, or a URL (kept as a link, not downloaded) | Find the file; download a remote image only if the user agrees |
| Missing characters | The font has no glyph (emoji, CJK, Cyrillic), so the text vanishes from the PDF | Replace decorative emoji; for real text set a suitable font in `projectdoc.sty` |
| Overfull boxes | Content runs past the margin | Inspect the page; small overflows of a few points don't matter |
| Mermaid not rendered | `mmdc` missing; the PDF shows the source and a notice | Install `mmdc` or tell the user. If Chromium is installed, `PUPPETEER_SKIP_DOWNLOAD=1 npm i @mermaid-js/mermaid-cli` skips the browser download; the script finds the system browser |

## 6. Look at the PDF

A clean compile doesn't prove the result looks right. Render and open the cover, document control, table of contents and a few content-heavy pages:

```bash
pdftoppm -r 60 -png -f 1 -l 4 OUTPUT_DIR/main.pdf /tmp/preview
```

Check for tables squeezed or running off the page, chapter titles that are really filenames, and leftovers that make no sense in a PDF: "Table of contents" sections, "edit on GitHub" links, badges, site navigation, "next page" links, and instructions for an interface the PDF doesn't have ("click the arrow to expand"). Remove those from the conversion: edit the Markdown if it's the user's to change, or the generated chapter otherwise, and mention the manual edit since `--force` would discard it.

## 7. Report back

Give the path to `main.pdf` and the project, the metadata you used, anything left blank, and any unresolved warnings. Say plainly if you couldn't compile or visually check the result.
