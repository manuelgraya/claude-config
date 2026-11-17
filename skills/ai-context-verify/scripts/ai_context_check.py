#!/usr/bin/env python3
"""Mechanical checks for an ai-context vault.

Usage (run with: python3 -I ai_context_check.py ...):
  refs  <vault_dir> [--root DIR]   check that code references in notes exist
  stale <vault_dir> [--root DIR]   list notes whose `covers:` changed since `verified:`
  stamp <vault_dir> [--root DIR] [--notes a.md b.md]   set `verified:` to the current revision/date

Frontmatter per note:
  summary: ...
  verified: "git abc1234 @ 2026-01-01"   or   "svn r1234 @ 2026-01-01"
  covers: ["src/main/java/**", "pom.xml"]    (globs relative to --root; ** = any depth)
"""
import argparse, datetime, fnmatch, os, re, subprocess, sys

SKIP_DIRS = {'.git', '.svn', 'node_modules', 'target', '.settings', '.idea', '.vscode', 'ai-context', '.dbeaver'}
TEXT_EXT = {'.java', '.js', '.xml', '.sql', '.properties', '.jsp', '.json', '.jrxml', '.css', '.html', '.md', '.yml', '.yaml', '.sh', '.txt', '.csv'}
PATH_EXT = {'java', 'js', 'xml', 'sql', 'properties', 'jsp', 'json', 'jrxml', 'css', 'html', 'yml', 'yaml', 'sh', 'md', 'txt'}


def run(cmd, cwd):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return ''


def frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(':')
            if _:
                fm[k.strip()] = v.strip()
    return fm


def parse_list(v):
    return re.findall(r'"([^"]+)"', v or '')


def vcs_info(root):
    if os.path.isdir(os.path.join(root, '.git')) or run(['git', 'rev-parse', '--git-dir'], root).strip():
        h = run(['git', 'rev-parse', '--short', 'HEAD'], root).strip()
        return 'git', h
    if os.path.isdir(os.path.join(root, '.svn')):
        r = run(['svn', 'info', '--show-item', 'revision'], root).strip()
        return 'svn', r
    return None, ''


def stamp_value(root):
    kind, rev = vcs_info(root)
    d = datetime.date.today().isoformat()
    if kind == 'git':
        return f'"git {rev} @ {d}"'
    if kind == 'svn':
        return f'"svn r{rev} @ {d}"'
    return f'"date {d}"'


def glob_to_re(g):
    g = g.replace('\\', '/')
    out, i = '', 0
    while i < len(g):
        if g.startswith('**/', i):
            out += '(?:.*/)?'; i += 3
        elif g.startswith('**', i):
            out += '.*'; i += 2
        elif g[i] == '*':
            out += '[^/]*'; i += 1
        elif g[i] == '?':
            out += '[^/]'; i += 1
        else:
            out += re.escape(g[i]); i += 1
    return re.compile('^' + out + '$')


def source_files(roots):
    for root in roots:
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for f in files:
                yield os.path.join(d, f)


def notes_of(vault):
    return sorted(f for f in os.listdir(vault) if f.endswith('.md'))


# ---------------------------------------------------------------- refs
def cmd_refs(vault, root):
    parent = os.path.dirname(root)
    scan_roots = [root] + [os.path.join(parent, d) for d in sorted(os.listdir(parent))
                           if os.path.isdir(os.path.join(parent, d)) and os.path.join(parent, d) != root
                           and not d.startswith('.')]
    suffixes, idents, names = set(), set(), set()
    id_re = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
    for r in scan_roots:
        names.add(os.path.basename(r))
        for d, dirs, files in os.walk(r):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for x in dirs:
                names.add(x)
                parts = os.path.relpath(os.path.join(d, x), r).replace('\\', '/').split('/')
                for i in range(len(parts)):
                    suffixes.add('/'.join(parts[i:]))
    ignore = set()
    ig = os.path.join(vault, '.checkignore')
    if os.path.exists(ig):
        ignore = {l.strip() for l in open(ig, encoding='utf-8') if l.strip() and not l.startswith('#')}
    for p in source_files(scan_roots):
        names.add(os.path.splitext(os.path.basename(p))[0]); names.add(os.path.basename(p))
        rel = p.replace('\\', '/')
        parts = rel.split('/')
        for i in range(len(parts)):  # every path suffix, with and without extension
            suf = '/'.join(parts[i:])
            suffixes.add(suf)
            suffixes.add(os.path.splitext(suf)[0])
        if os.path.splitext(p)[1] in TEXT_EXT:
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                    idents.update(id_re.findall(fh.read()))
            except OSError:
                pass
    bad_total = 0
    for n in notes_of(vault):
        text = open(os.path.join(vault, n), encoding='utf-8').read()
        body = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.S)
        body = re.sub(r'```.*?```', '', body, flags=re.S)  # code blocks are examples
        missing, checked = [], 0
        for tok in sorted(set(re.findall(r'`([^`\n]+)`', body))):
            t = tok.strip().rstrip('/').rstrip(',.;:')
            t = re.sub(r'\(.*\)$', '', t)  # method() -> method
            if (not t or tok in ignore or t in ignore or ' ' in t or '...' in t or '://' in t or '{' in t or '*' in t or '<' in t
                    or t.startswith(('-', '@', '$', '#', '"', "'", '_')) or re.fullmatch(r'[0-9a-f]{7,12}', t)
                    or re.match(r'^[A-Za-z]:/', t) or t.startswith('jdbc/') or re.search(r'\bx\.y', t)):
                continue
            if t.startswith('~'):
                checked += 1
                if not os.path.exists(os.path.expanduser(t)):
                    missing.append(tok)
                continue
            ext = t.rsplit('.', 1)[-1] if '.' in t else ''
            if '/' in t or ext in PATH_EXT:
                checked += 1
                t2 = t.replace('\\', '/')
                if os.path.exists(os.path.join(root, t2)) or os.path.exists(os.path.join(vault, t2)):
                    continue
                t3 = t2
                while t3.startswith(('./', '../')):
                    t3 = t3.split('/', 1)[1]
                t3 = t3.lstrip('/')
                if t3 in suffixes:
                    continue
                segs = [x for x in t3.split('/') if x and x not in ('.', '..')]
                segs = [os.path.splitext(x)[0] if x == segs[-1] and '.' in x else x for x in segs]
                if segs and all(x in names or x in idents for x in segs):
                    continue  # every segment exists somewhere: lenient pass
                missing.append(tok)
            elif re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', t):
                if t.isupper() or t.lower() == t and len(t) < 4:
                    continue  # SQL tables/constants/short words: not checked
                checked += 1
                if t not in idents and t not in names:
                    missing.append(tok)
        bad_total += len(missing)
        print(f'{n}: {checked} refs checked, {len(missing)} not found' + (': ' + ', '.join(missing) if missing else ''))
    print(f'\nTOTAL not found: {bad_total} (each one is a candidate stale/wrong claim: confirm by hand)')
    return 1 if bad_total else 0


# ---------------------------------------------------------------- stale
def changed_files(root, verified):
    kind, rev = vcs_info(root)
    files = set()
    m = re.match(r'(git|svn)\s+r?(\w+)\s*@\s*(\d{4}-\d{2}-\d{2})', verified or '')
    if not m:
        return None
    vkind, vrev, vdate = m.groups()
    if kind == 'git' and vkind == 'git':
        files.update(run(['git', 'diff', '--name-only', vrev, 'HEAD'], root).split())
        for line in run(['git', 'status', '--porcelain'], root).splitlines():
            files.add(line[3:].split(' -> ')[-1])
    elif kind == 'svn':
        for line in run(['svn', 'status'], root).splitlines():
            if line[:1] in 'MAD!R':
                files.add(line[8:].strip())
        out = run(['svn', 'diff', '-r', f'{vrev}:HEAD', '--summarize'], root)  # needs server; may be empty
        for line in out.splitlines():
            files.add(line[8:].strip())
    # fallback for any VCS / offline svn: mtime newer than the verification date
    cutoff = datetime.datetime.strptime(vdate, '%Y-%m-%d').timestamp()
    for p in source_files([root]):
        try:
            if os.path.getmtime(p) > cutoff + 86400:
                files.add(os.path.relpath(p, root))
        except OSError:
            pass
    return {f.replace('\\', '/') for f in files}


def cmd_stale(vault, root):
    stale = 0
    for n in notes_of(vault):
        fm = frontmatter(open(os.path.join(vault, n), encoding='utf-8').read())
        covers, verified = parse_list(fm.get('covers')), fm.get('verified', '').strip('"')
        if not verified or not covers:
            print(f'{n}: NO verified/covers frontmatter -> treat as unverified')
            stale += 1
            continue
        changed = changed_files(root, verified)
        if changed is None:
            print(f'{n}: cannot parse verified="{verified}"')
            stale += 1
            continue
        pats = [glob_to_re(c) for c in covers]
        hit = sorted(f for f in changed if any(p.match(f) for p in pats))
        if hit:
            stale += 1
            print(f'{n}: REVIEW ({len(hit)} changed since {verified}): ' + ', '.join(hit[:8]) + (' ...' if len(hit) > 8 else ''))
        else:
            print(f'{n}: ok (no covered file changed since {verified})')
    print(f'\n{stale} note(s) need review')
    return 1 if stale else 0


# ---------------------------------------------------------------- stamp
def cmd_stamp(vault, root, only):
    val = stamp_value(root)
    for n in (only or notes_of(vault)):
        p = os.path.join(vault, n)
        t = open(p, encoding='utf-8').read()
        if re.search(r'^verified:.*$', t, re.M):
            t = re.sub(r'^verified:.*$', f'verified: {val}', t, count=1, flags=re.M)
        else:
            t = t.replace('\n---\n', f'\nverified: {val}\n---\n', 1)
        open(p, 'w', encoding='utf-8').write(t)
        print(f'stamped {n} -> {val}')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['refs', 'stale', 'stamp'])
    ap.add_argument('vault')
    ap.add_argument('--root')
    ap.add_argument('--notes', nargs='*')
    a = ap.parse_args()
    vault = os.path.abspath(a.vault)
    root = os.path.abspath(a.root) if a.root else os.path.dirname(vault)
    sys.exit({'refs': lambda: cmd_refs(vault, root), 'stale': lambda: cmd_stale(vault, root),
              'stamp': lambda: cmd_stamp(vault, root, a.notes)}[a.cmd]())


if __name__ == '__main__':
    main()
