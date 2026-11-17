#!/usr/bin/env python3
"""Convert Markdown documentation into a compilable LaTeX project."""
import argparse
import datetime
import fnmatch
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
FILTER = SKILL_DIR / "scripts" / "docs-filter.lua"
TEMPLATE = SKILL_DIR / "assets" / "template"
MARKER = ".md2latex"
GENERATED = ("chapters", "figures", "diagrams")
SKIP_DIRS = {"node_modules", "vendor", "venv", "site", "dist", "build", "target", "__pycache__"}
NAV_FILES = {"summary.md", "_sidebar.md"}
FIRST_FILES = {"readme.md", "index.md"}
PANDOC_FROM = "commonmark_x+gfm_auto_identifiers"

STRINGS = {
    "en": ("english", dict(Version="Version", Date="Date", Author="Author", Owner="Organization", Classification="Classification", DocControl="Document control", Revisions="Revision history", Description="Description", Initial="Initial version", Note="Note", Tip="Tip", Important="Important", Warning="Warning", Caution="Caution", Diagram="Diagram not rendered; source shown", Intro="Introduction")),
    "es": ("spanish", dict(Version="Versión", Date="Fecha", Author="Autor", Owner="Organización", Classification="Clasificación", DocControl="Control del documento", Revisions="Historial de revisiones", Description="Descripción", Initial="Versión inicial", Note="Nota", Tip="Consejo", Important="Importante", Warning="Advertencia", Caution="Precaución", Diagram="Diagrama sin renderizar; se muestra el código fuente", Intro="Introducción")),
    "fr": ("french", dict(Version="Version", Date="Date", Author="Auteur", Owner="Organisation", Classification="Classification", DocControl="Contrôle du document", Revisions="Historique des révisions", Description="Description", Initial="Version initiale", Note="Remarque", Tip="Conseil", Important="Important", Warning="Avertissement", Caution="Attention", Diagram="Diagramme non généré ; source affichée", Intro="Introduction")),
    "de": ("ngerman", dict(Version="Version", Date="Datum", Author="Autor", Owner="Organisation", Classification="Klassifizierung", DocControl="Dokumentenkontrolle", Revisions="Änderungshistorie", Description="Beschreibung", Initial="Erste Version", Note="Hinweis", Tip="Tipp", Important="Wichtig", Warning="Warnung", Caution="Vorsicht", Diagram="Diagramm nicht gerendert; Quelle angezeigt", Intro="Einführung")),
    "pt": ("portuguese", dict(Version="Versão", Date="Data", Author="Autor", Owner="Organização", Classification="Classificação", DocControl="Controlo do documento", Revisions="Histórico de revisões", Description="Descrição", Initial="Versão inicial", Note="Nota", Tip="Dica", Important="Importante", Warning="Aviso", Caution="Cuidado", Diagram="Diagrama não renderizado; fonte apresentada", Intro="Introdução")),
    "it": ("italian", dict(Version="Versione", Date="Data", Author="Autore", Owner="Organizzazione", Classification="Classificazione", DocControl="Controllo del documento", Revisions="Cronologia delle revisioni", Description="Descrizione", Initial="Versione iniziale", Note="Nota", Tip="Suggerimento", Important="Importante", Warning="Avviso", Caution="Attenzione", Diagram="Diagramma non generato; sorgente mostrata", Intro="Introduzione")),
}


BABEL_EXTRA = {"es": r"\addto\captionsspanish{\renewcommand\tablename{Tabla}\renewcommand\listtablename{Índice de tablas}}"}


def natural_key(path):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", str(path))]


def walk_markdown(root, output):
    """Depth-first natural order, with README/index first in each directory."""
    found = []

    def visit(folder):
        entries = sorted(folder.iterdir(), key=lambda p: natural_key(p.name))
        files = [p for p in entries if p.is_file() and p.suffix.lower() in (".md", ".markdown")]
        files.sort(key=lambda p: p.name.lower() not in FIRST_FILES)
        found.extend(p for p in files if p.name.lower() not in NAV_FILES)
        for sub in entries:
            hidden = sub.name.startswith(".") or sub.name in SKIP_DIRS
            if sub.is_dir() and not hidden and sub.resolve() != output:
                visit(sub)

    visit(root)
    return found


def nav_entries(root):
    """Return (base_dir, ordered files) from a documentation nav, if there is one."""
    mkdocs = next((root / n for n in ("mkdocs.yml", "mkdocs.yaml") if (root / n).is_file()), None)
    if mkdocs:
        text = mkdocs.read_text(encoding="utf-8")
        docs_dir = re.search(r"^docs_dir:\s*['\"]?([^'\"\n#]+)", text, re.M)
        base = root / (docs_dir.group(1).strip() if docs_dir else "docs")
        nav = re.search(r"^nav:\s*\n((?:[ \t-].*\n|\s*\n)*)", text + "\n", re.M)
        if nav and base.is_dir():
            return base, re.findall(r"([^\s:'\"]+\.md)\b", nav.group(1))
        if base.is_dir():
            return base, []
    for name in ("SUMMARY.md", "_sidebar.md"):
        if (root / name).is_file():
            text = (root / name).read_text(encoding="utf-8")
            return root, re.findall(r"\]\(\s*(?:\./)?([^)#\s]+\.md)", text)
    return root, []


def discover(source, output, order_file, excludes):
    """Return (root, files, notes)."""
    notes = []
    if source.is_file():
        return source.parent, [source], notes
    root, ordered = nav_entries(source)
    if order_file:
        root, ordered = source, [
            line.strip()
            for line in order_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith(("#", "@part "))
        ]
    files = []
    for rel in ordered:
        path = (root / rel).resolve()
        if path.is_file():
            if path not in files:
                files.append(path)
        else:
            notes.append(f"listed in the order but not found: {rel}")
    if ordered:
        listed = set(files)
        for path in walk_markdown(root, output):
            if path.resolve() not in listed:
                files.append(path.resolve())
                notes.append(f"not in the nav, added at the end: {path.relative_to(root)}")
    else:
        files = [p.resolve() for p in walk_markdown(root, output)]
    root = root.resolve()
    kept = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        if not any(fnmatch.fnmatch(rel, pat) for pat in excludes):
            kept.append(path)
    return root, kept, notes


def read_parts(order_file, root):
    """Map each file to the part opened just before it by an "@part Name" line."""
    parts, pending = {}, None
    if not order_file:
        return parts
    for line in order_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("@part "):
            pending = line[6:].strip()
        elif line and not line.startswith("#") and pending:
            parts[(root / line).resolve()] = pending
            pending = None
    return parts


def make_slugs(files, root):
    used, result = set(), {}
    for path in files:
        base = re.sub(r"\.(md|markdown)$", "", path.relative_to(root).as_posix(), flags=re.I)
        slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "doc"
        unique, n = slug, 2
        while unique in used:
            unique, n = f"{slug}-{n}", n + 1
        used.add(unique)
        result[path] = unique
    return result


def fallback_title(path, root, intro):
    stem = path.stem
    if stem.lower() in ("readme", "index"):
        if path.parent == root:
            return intro
        stem = path.parent.name
    name = re.sub(r"^\d+[-_. ]*", "", stem) or stem
    name = re.sub(r"[-_]+", " ", name).strip()
    return name[:1].upper() + name[1:]


def first_heading(path):
    fence = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if re.match(r"\s*(```|~~~)", line):
            fence = not fence
        elif not fence and (m := re.match(r"#\s+(.+?)\s*#*\s*$", line)):
            return m.group(1)
    return None


ADMON_MKDOCS = re.compile(r"^(\s*)(?:!!!|\?\?\?\+?)\s+([A-Za-z]+)(?:\s+\"(.*)\")?\s*$")
ADMON_DOCUSAURUS = re.compile(
    r"^(\s*):::\s*(note|tip|info|warning|danger|caution|important)(?:\[(.*)\]|[ \t]+([^{\s].*?))?\s*$",
    re.I,
)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


OBSIDIAN_CALLOUT = re.compile(r"^(\s*)>\s*\[!(\w+)\][-+]?[ \t]*(.*)$")
WIKILINK = re.compile(r"(!?)\[\[([^\]|#]*)(#[^\]|]*)?(?:\\?\|([^\]]*))?\]\]")
INLINE_CODE = re.compile(r"(`+[^`\n]*`+)")
# Callout types without a style of their own in the template.
CALLOUT_KINDS = {
    "tldr": "note", "summary": "note", "question": "note", "faq": "note", "help": "note", "todo": "note",
    "quote": "note", "cite": "note", "check": "tip", "done": "tip", "fail": "danger", "failure": "danger",
    "missing": "danger", "bug": "danger",
}
KNOWN_KINDS = {"note", "info", "abstract", "example", "tip", "hint", "success", "important", "warning", "attention", "caution", "danger", "error"}


def vault_index(root):
    """Index notes by name and other files by filename, for Obsidian's shortest-path links."""
    names, assets = {}, {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or any(p.startswith(".") or p in SKIP_DIRS for p in rel.parts):
            continue
        if path.suffix.lower() in (".md", ".markdown"):
            names.setdefault(path.stem, rel.as_posix())
            names.setdefault(rel.with_suffix("").as_posix(), rel.as_posix())
        else:
            assets.setdefault(path.name, rel.as_posix())
    return names, assets


def heading_id(text):
    """Pandoc's GFM auto identifier for a heading."""
    text = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"\s", "-", text)


def resolve_wikilinks(line, names, assets, unresolved):
    def replace(m):
        embed, name, fragment, alias = m.group(1), m.group(2).strip(), m.group(3), m.group(4)
        target = f"#{heading_id(fragment[1:])}" if fragment else ""
        label = (alias or "").strip()
        if embed:
            rel = assets.get(name)
            if rel:
                # An embed alias is a size or a caption; keep only captions.
                caption = "" if re.fullmatch(r"\d+(x\d+)?", label) else label
                return f"![{caption}](</{rel.replace('%', '%25')}>)"
            if name not in names:
                unresolved.append(m.group(0))
                return label or name
        if not name:
            return f"[{label or fragment[1:]}]({target})"
        if name not in names:
            unresolved.append(m.group(0))
            return label or name
        return f"[{label or name}](</{names[name].replace('%', '%25')}{target}>)"

    pieces = INLINE_CODE.split(line)
    pieces[::2] = [WIKILINK.sub(replace, piece) for piece in pieces[::2]]
    return "".join(pieces)


def fenced_div(indent, kind, title):
    if title:
        escaped = title.replace("\\", "\\\\").replace('"', '\\"')
        return f'{indent}::: {{.{kind.lower()} title="{escaped}"}}'
    return f"{indent}::: {{.{kind.lower()}}}"


def preprocess(text, names=None, assets=None, unresolved=None):
    """Rewrite Obsidian, MkDocs and Docusaurus syntax as Pandoc Markdown, skipping code."""
    names, assets = names or {}, assets or {}
    unresolved = unresolved if unresolved is not None else []
    lines, out, i, fence = text.splitlines(), [], 0, None
    while i < len(lines):
        line = lines[i]
        match = FENCE.match(line)
        if fence:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
            out.append(line)
            i += 1
        elif match:
            fence = match.group(1)
            out.append(line)
            i += 1
        elif m := OBSIDIAN_CALLOUT.match(line):
            indent, kind = m.group(1), m.group(2).lower()
            kind = kind if kind in KNOWN_KINDS else CALLOUT_KINDS.get(kind, "note")
            body, i = [], i + 1
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                body.append(re.sub(r"^\s*> ?", "", lines[i]))
                i += 1
            title = m.group(3).strip()
            out += [fenced_div(indent, kind, title), ""]
            out += [indent + b if b else b for b in preprocess("\n".join(body), names, assets, unresolved).splitlines()]
            out += ["", f"{indent}:::", ""]
        elif m := ADMON_MKDOCS.match(line):
            indent = m.group(1)
            body, i = [], i + 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith(indent + "    ")):
                body.append(lines[i][len(indent) + 4:])
                i += 1
            while body and not body[-1].strip():
                body.pop()
            out += [fenced_div(indent, m.group(2), m.group(3)), ""]
            out += [indent + b if b else b for b in preprocess("\n".join(body), names, assets, unresolved).splitlines()]
            out += ["", f"{indent}:::", ""]
        elif m := ADMON_DOCUSAURUS.match(line):
            out.append(fenced_div(m.group(1), m.group(2), m.group(3) or m.group(4)))
            i += 1
        else:
            out.append(resolve_wikilinks(line, names, assets, unresolved))
            i += 1
    return "\n".join(out) + "\n"


LINE_CHARS = 95  # characters of body text in one full-width line
TABLE = re.compile(r"\\begin\{longtable\}\[\]\{@\{\}([lrc]+)@\{\}\}(.*?)\\end\{longtable\}", re.S)
CELL_SPLIT = re.compile(r"(?<!\\) & ")
CELL_ALIGN = {"l": r"\raggedright", "r": r"\raggedleft", "c": r"\centering"}
CODE_PIECES = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[./:,\-=(_])")
HEADINGS = ("\\part", "\\chapter", "\\section", "\\subsection", "\\subsubsection", "\\paragraph", "\\begin{pdadmonition}")


def table_rows(body, columns):
    rows = []
    for line in body.splitlines():
        if line.endswith(" \\\\") and not line.startswith(("\\toprule", "\\midrule", "\\bottomrule")):
            cells = CELL_SPLIT.split(line[:-3])
            if len(cells) == columns:
                rows.append(cells)
    return rows


def plain_text(cell):
    text = re.sub(r"\\hyperref\[[^\]]*\]", "", cell)
    return re.sub(r"[{}\\]", "", re.sub(r"\\[a-zA-Z]+", " ", text))


def cell_length(cell):
    code = sum(len(c) for c in re.findall(r"\\texttt\{([^}]*)\}", cell))
    return len(plain_text(cell)) + code // 4  # monospace runs wider than body text


def column_minimum(rows, column):
    """Fraction of the line taken by the longest piece that cannot break."""
    best = 0.0
    for row in rows:
        cell = row[column]
        for code in re.findall(r"\\texttt\{([^}]*)\}", cell):
            for piece in CODE_PIECES.split(code.replace("\\", "")):
                best = max(best, (len(piece) * 1.2 + 3) / LINE_CHARS)
        bold = column == 0 or r"\textbf" in cell
        for word in plain_text(re.sub(r"\\texttt\{[^}]*\}", " ", cell)).split():
            best = max(best, (len(word) * (1.25 if bold else 1.15) + 3) / LINE_CHARS)
    return max(0.09, min(0.4, best))


def fit_table(match):
    """Pandoc leaves pipe tables in natural width, so wide ones run off the page."""
    spec, body = match.group(1), match.group(2)
    rows = table_rows(body, len(spec))
    if not rows:
        return match.group(0)
    columns = range(len(spec))
    longest = [max(cell_length(r[c]) for r in rows) for c in columns]
    if sum(longest) + 3 * len(spec) <= LINE_CHARS:
        return match.group(0)
    average = [sum(cell_length(r[c]) for r in rows) / len(rows) for c in columns]
    raw = [(max(a, 1) * max(x, 1)) ** 0.5 for a, x in zip(average, longest)]
    minimum = [column_minimum(rows, c) for c in columns]
    width = [max(r / sum(raw), m) for r, m in zip(raw, minimum)]
    excess, spare = sum(width) - 1, sum(w - m for w, m in zip(width, minimum))
    if 0 < excess <= spare:  # shrink only the columns above their minimum
        width = [w - (w - m) * excess / spare for w, m in zip(width, minimum)]
    else:
        width = [w / sum(width) for w in width]
    cols = "".join(
        f">{{{CELL_ALIGN[a]}\\arraybackslash}}p{{\\dimexpr {w:.3f}\\linewidth-2\\tabcolsep\\relax}}"
        for a, w in zip(spec, width)
    )
    body = re.sub(r" \\\\$", lambda _: " \\\\\\addlinespace[2pt]", body, flags=re.M)
    return f"\\begin{{longtable}}[]{{@{{}}{cols}@{{}}}}{body}\\end{{longtable}}"


def soften_code(code):
    """Let long identifiers break at natural points."""
    code = code.replace(r"\_", "\0")
    code = re.sub(r"([a-z0-9])([A-Z])", r"\1\\allowbreak{}\2", code)
    code = re.sub(r"(?<=[\w)])([./:,\-=(])(?=[\w(<$\\\"])", r"\1\\allowbreak{}", code)
    return code.replace("\0", r"\_\allowbreak{}")


def soften_inline_code(line):
    result, i = [], 0
    while (start := line.find(r"\texttt{", i)) != -1:
        end, depth = start + 8, 1
        while end < len(line) and depth:
            if line[end] == "\\":
                end += 2
                continue
            depth += {"{": 1, "}": -1}.get(line[end], 0)
            end += 1
        result += [line[i:start], r"\texttt{", soften_code(line[start + 8:end - 1]), "}"]
        i = end
    return "".join(result) + line[i:]


def finish_chapter(path):
    """Fit tables to the page and make inline code breakable in a generated chapter."""
    text = TABLE.sub(fit_table, path.read_text(encoding="utf-8"))
    # Code in a language Pandoc can't highlight arrives as plain verbatim, which doesn't wrap.
    text = text.replace(r"\begin{verbatim}", r"\begin{pdverb}").replace(r"\end{verbatim}", r"\end{pdverb}")
    lines, verbatim = [], False
    for line in text.split("\n"):
        if re.match(r"\\begin\{(Highlighting|verbatim|pdverb)\}", line):
            verbatim = True
        elif re.match(r"\\end\{(Highlighting|verbatim|pdverb)\}", line):
            verbatim = False
        elif not verbatim:
            if not line.startswith(HEADINGS):
                line = soften_inline_code(line)
            line = line.replace("↔", r"$\leftrightarrow$")
        lines.append(line)
    path.write_text("\n".join(lines), encoding="utf-8")


TEX_SPECIALS = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#", "_": r"\_", "%": r"\%", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def tex(value):
    return re.sub(r"[\\{}$&#_%~^]", lambda m: TEX_SPECIALS[m.group(0)], value or "")


def write_metadata(path, args, title, logo, strings):
    version = tex(args.doc_version)
    values = {
        "DocTitle": tex(title), "DocSubtitle": tex(args.subtitle), "DocOrganization": tex(args.organization),
        "DocAuthor": tex(args.author), "DocVersion": version, "DocDate": tex(args.date),
        "DocClassification": tex(args.classification), "DocLogo": logo, "DocAccent": args.accent.lstrip("#").upper(),
    }
    out = ["% Project metadata. Safe to edit: regenerating with --force keeps this file.", ""]
    out += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in values.items()]
    out += ["", "% One row per revision: version & date & author & description \\\\"]
    row = f"{version or '---'} & {tex(args.date)} & {tex(args.author) or '---'} & {tex(strings['Initial'])} \\\\"
    out += ["\\newcommand{\\DocRevisionRows}{%", f"  {row}", "}", "", "% Interface labels"]
    out += [f"\\newcommand{{\\PdStr{k}}}{{{tex(v)}}}" for k, v in strings.items()]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def write_highlighting(out, env):
    with tempfile.TemporaryDirectory() as tmp:
        template = Path(tmp) / "macros.tpl"
        template.write_text("$highlighting-macros$\n", encoding="utf-8")
        done = subprocess.run(
            ["pandoc", "-f", "markdown", "-t", "latex", "-s", f"--template={template}"],
            input="```python\nx = 1\n```\n", capture_output=True, text=True, env=env,
        )
    if done.returncode != 0:
        raise SystemExit(f"pandoc failed:\n{done.stderr}")
    (out / "highlighting.tex").write_text(done.stdout, encoding="utf-8")


def convert_images(manifest, root, out):
    errors = []
    lines = manifest.read_text(encoding="utf-8").splitlines() if manifest.exists() else []
    for line in lines:
        rel, dest_rel = line.split("\t")
        src, dest = root / rel, out / dest_rel
        same_type = src.suffix.lower().lstrip(".") == dest.suffix.lstrip(".") or {src.suffix.lower(), dest.suffix} == {".jpeg", ".jpg"}
        if same_type:
            shutil.copyfile(src, dest)
            continue
        if src.suffix.lower() == ".svg":
            cmd = ["rsvg-convert", "-f", "pdf", "-o", str(dest), str(src)]
        else:
            cmd = ["magick", f"{src}[0]", str(dest)]
        if not shutil.which(cmd[0]):
            errors.append(f"{rel}: {cmd[0]} is required to convert this image")
            continue
        done = subprocess.run(cmd, capture_output=True, text=True)
        if done.returncode != 0:
            errors.append(f"{rel}: conversion failed: {done.stderr.strip()[:200]}")
    return errors


def render_diagrams(out):
    sources = sorted((out / "diagrams").glob("*.mmd"))
    if not sources:
        return []
    if not shutil.which("mmdc"):
        return [f"{len(sources)} Mermaid diagram(s) not rendered: mmdc is not installed"]
    errors = []
    # Recent mermaid-cli fits PDFs by default and rejects --pdfFit.
    usage = subprocess.run(["mmdc", "--help"], capture_output=True, text=True).stdout
    fit = ["--pdfFit"] if "--pdfFit" in usage else []
    env = dict(os.environ)
    browser = next(filter(None, map(shutil.which, ("chromium", "chromium-browser", "google-chrome", "chrome"))), None)
    if browser:  # mmdc may have been installed without its bundled browser
        env.setdefault("PUPPETEER_EXECUTABLE_PATH", browser)
    for src in sources:
        cmd = ["mmdc", "-i", str(src), "-o", str(src.with_suffix(".pdf")), *fit]
        done = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if done.returncode != 0:
            errors.append(f"{src.name}: mmdc failed: {done.stderr.strip()[:200]}")
    return errors


def build_pdf(out):
    if shutil.which("latexmk") and shutil.which("xelatex"):
        cmd = ["latexmk", "-xelatex", "-interaction=nonstopmode", "-file-line-error", "main.tex"]
    elif shutil.which("tectonic"):
        cmd = ["tectonic", "--keep-logs", "main.tex"]
    else:
        return False, ["no LaTeX engine found: install latexmk + xelatex, or tectonic"]
    done = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
    pdf_ok = done.returncode == 0 and (out / "main.pdf").is_file()
    report = []
    log_path = out / "main.log"
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    errors = re.findall(r"^(?:! |.*:\d+: )(.*)$", log, re.M)
    report += [f"LaTeX error: {e}" for e in dict.fromkeys(errors)]
    if not pdf_ok and not errors:
        report.append("compile failed:\n" + (done.stderr or done.stdout)[-1500:])
    report += [f"undefined reference: {r}" for r in dict.fromkeys(re.findall(r"(?:Hyper reference|Reference) [`'](.+?)' .*undefined", log))]
    missing = sorted(set(re.findall(r"Missing character: There is no (.+?) (?:\(U\+[0-9A-F]+\) )?in font", log)))
    if missing:
        report.append(f"missing characters: {' '.join(missing)}")
    overfull = [float(w) for w in re.findall(r"^Overfull \\hbox \(([\d.]+)pt too wide", log, re.M)]
    if overfull:
        report.append(f"{len(overfull)} overfull box(es), {sum(w > 10 for w in overfull)} over 10pt, widest {max(overfull):.0f}pt; see main.log")
    return pdf_ok, report


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path, help="Markdown file or documentation directory")
    p.add_argument("output", type=Path, help="directory for the LaTeX project")
    p.add_argument("--title")
    p.add_argument("--subtitle", default="")
    p.add_argument("--organization", default="")
    p.add_argument("--author", default="")
    p.add_argument("--doc-version", default="")
    p.add_argument("--date", default=datetime.date.today().isoformat())
    p.add_argument("--classification", default="", help="for example: Confidential")
    p.add_argument("--lang", default="en", choices=sorted(STRINGS))
    p.add_argument("--accent", default="1F4E79", help="accent color as 6-digit hex")
    p.add_argument("--logo", type=Path)
    p.add_argument("--order-file", type=Path, help="one relative Markdown path per line")
    p.add_argument("--exclude", action="append", default=[], help="glob on the relative path; repeatable")
    p.add_argument("--dry-run", action="store_true", help="show the chapter plan and stop")
    p.add_argument("--force", action="store_true", help="regenerate chapters, figures and diagrams")
    p.add_argument("--build", action="store_true", help="compile main.pdf after converting")
    args = p.parse_args()
    if not re.fullmatch(r"#?[0-9A-Fa-f]{6}", args.accent):
        p.error("--accent must be a 6-digit hex color")
    if not args.source.exists():
        p.error(f"source not found: {args.source}")
    if args.logo and not args.logo.is_file():
        p.error(f"logo not found: {args.logo}")
    if args.order_file and not args.order_file.is_file():
        p.error(f"order file not found: {args.order_file}")
    return args


def main():
    args = parse_args()
    out = args.output.resolve()
    root, files, notes = discover(args.source.resolve(), out, args.order_file, args.exclude)
    if not files:
        raise SystemExit("no Markdown files found")
    slugs = make_slugs(files, root)
    parts = read_parts(args.order_file, root)
    names, assets = vault_index(root)
    babel, strings = STRINGS[args.lang]

    if args.dry_run:
        print(f"Root: {root}")
        for n, path in enumerate(files, 1):
            if path in parts:
                print(f"     == {parts[path]} ==")
            print(f"{n:3d}. {path.relative_to(root)}  ->  chapters/{n:02d}-{slugs[path]}.tex")
        for note in notes:
            print(f"note: {note}")
        return

    if not shutil.which("pandoc"):
        raise SystemExit("pandoc is not installed")
    has_project = (out / MARKER).exists()
    if out.exists() and any(out.iterdir()):
        if not has_project:
            raise SystemExit(f"{out} is not empty and is not an md2latex project; choose another directory")
        if not args.force:
            raise SystemExit(f"{out} already exists; --force replaces chapters/, figures/ and diagrams/")
    for name in GENERATED:
        if has_project and (out / name).exists():
            shutil.rmtree(out / name)
        (out / name).mkdir(parents=True, exist_ok=True)
    (out / MARKER).touch()

    warnings = list(notes)
    env = dict(os.environ)
    write_highlighting(out, env)

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        map_file, manifest = tmp / "map.tsv", tmp / "images.tsv"
        map_file.write_text(
            "".join(f"{p.relative_to(root).as_posix()}\t{s}\n" for p, s in slugs.items()), encoding="utf-8"
        )
        chapter_lines, unresolved = [], []
        for n, path in enumerate(files, 1):
            rel, slug = path.relative_to(root).as_posix(), slugs[path]
            source = tmp / f"{n}.md"
            source.write_text(preprocess(path.read_text(encoding="utf-8", errors="replace"), names, assets, unresolved), encoding="utf-8")
            chapter = f"chapters/{n:02d}-{slug}"
            file_env = env | {
                "PD_ROOT": str(root), "PD_SOURCE": rel, "PD_SLUG": slug, "PD_OUT": str(out),
                "PD_TITLE": fallback_title(path, root, strings["Intro"]),
                "PD_MAP": str(map_file), "PD_MANIFEST": str(manifest),
            }
            done = subprocess.run(
                ["pandoc", str(source), "-f", PANDOC_FROM, "-t", "latex", "--top-level-division=chapter",
                 "--columns=72", "--wrap=preserve", f"--lua-filter={FILTER}", "-o", str(out / f"{chapter}.tex")],
                capture_output=True, text=True, env=file_env,
            )
            if done.returncode != 0:
                raise SystemExit(f"pandoc failed on {rel}:\n{done.stderr}")
            for line in done.stderr.splitlines():
                if line.strip():
                    warnings.append(f"{rel}: {line.replace('PD-WARN: ', '')}")
            finish_chapter(out / f"{chapter}.tex")
            for link in dict.fromkeys(unresolved):
                warnings.append(f"{rel}: broken wikilink, kept as text: {link}")
            unresolved.clear()
            if path in parts:
                chapter_lines.append(f"\\part{{{tex(parts[path])}}}")
            chapter_lines.append(f"\\input{{{chapter}}}")
        warnings += convert_images(manifest, root, out)

    warnings += render_diagrams(out)
    (out / "chapters.tex").write_text("% Chapter order. Regenerated by --force.\n" + "\n".join(chapter_lines) + "\n", encoding="utf-8")

    logo = ""
    if args.logo:
        assets = out / "assets"
        assets.mkdir(exist_ok=True)
        logo = f"assets/logo{args.logo.suffix.lower()}"
        shutil.copyfile(args.logo, out / logo)
    title = args.title or first_heading(files[0]) or fallback_title(args.source.resolve(), root, strings["Intro"])
    if not (out / "metadata.tex").exists():
        write_metadata(out / "metadata.tex", args, title, logo, strings)
    for name in ("projectdoc.sty", ".latexmkrc", ".gitignore"):
        if not (out / name).exists():
            shutil.copyfile(TEMPLATE / name, out / name)
    if not (out / "main.tex").exists():
        main_tex = (TEMPLATE / "main.tex").read_text(encoding="utf-8").replace("@@BABEL@@", babel).replace("@@BABELEXTRA@@", BABEL_EXTRA.get(args.lang, ""))
        (out / "main.tex").write_text(main_tex, encoding="utf-8")

    print(f"Project: {out} ({len(files)} chapter file(s))")
    failed = False
    if args.build:
        pdf_ok, report = build_pdf(out)
        warnings += report
        failed = not pdf_ok
        print(f"PDF: {out / 'main.pdf'}" if pdf_ok else "PDF: compile FAILED")
    for warning in warnings:
        print(f"warning: {warning}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
