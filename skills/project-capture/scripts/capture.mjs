#!/usr/bin/env node
// project-capture: screenshots, UI discovery and scripted flows with Playwright.
// Usage: node capture.mjs <shot|discover|flow|login> ... (run without args for help)
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline/promises';

const HELP = `project-capture

  shot <url|file> [--out DIR] [--name NAME] [--full] [--selector CSS]
  discover <url|file> [--out DIR] [--name NAME]
  flow <flow.json> [--out DIR]
  login <url> --storage FILE

Common options:
  --viewport WxH     default 1366x768 (use 390x844 for mobile)
  --storage FILE     Playwright storage state (cookies/localStorage) to reuse a session
  --wait MS|CSS      extra wait after load: milliseconds or a selector to wait for
  --dark             emulate prefers-color-scheme: dark
  --headed           show the browser
  --browser PATH     Chromium/Chrome executable (default: auto-detect, or $CHROME_PATH)
  --ignore-https     accept self-signed certificates (local dev servers)
  --timeout MS       per-action timeout (default 10000)
`;

// ---------- args ----------
function parseArgs(argv) {
  const pos = [], opt = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const k = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) opt[k] = true;
      else { opt[k] = next; i++; }
    } else pos.push(a);
  }
  return { pos, opt };
}

function toUrl(target) {
  if (/^[a-z][a-z0-9+.-]*:/i.test(target)) return target;
  const p = path.resolve(target);
  if (fs.existsSync(p)) {
    const f = fs.statSync(p).isDirectory() ? path.join(p, 'index.html') : p;
    return 'file://' + f;
  }
  return 'http://' + target;
}

function slug(s) {
  return String(s).replace(/^[a-z]+:\/\//i, '').replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').slice(0, 60) || 'page';
}

function findBrowser(explicit) {
  const candidates = [explicit, process.env.CHROME_PATH,
    '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
    '/usr/bin/brave', '/snap/bin/chromium',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium'].filter(Boolean);
  return candidates.find(c => fs.existsSync(c)); // undefined -> Playwright's own browser, if installed
}

// Values like "$ENV:NAME" are read from the environment and never printed.
function resolveValue(v) {
  if (typeof v === 'string' && v.startsWith('$ENV:')) {
    const name = v.slice(5);
    if (process.env[name] === undefined) throw new Error(`environment variable ${name} is not set`);
    return { value: process.env[name], shown: `$ENV:${name}`, secret: true };
  }
  return { value: String(v), shown: JSON.stringify(v) };
}

async function launch(opt) {
  const [w, h] = String(opt.viewport || '1366x768').split('x').map(Number);
  const executablePath = findBrowser(opt.browser);
  const browser = await chromium.launch({ headless: !opt.headed, executablePath });
  const ctxOpts = { viewport: { width: w, height: h }, ignoreHTTPSErrors: !!opt['ignore-https'] };
  if (opt.dark) ctxOpts.colorScheme = 'dark';
  if (opt.storage && opt.storage !== true && fs.existsSync(opt.storage)) ctxOpts.storageState = opt.storage;
  const context = await browser.newContext(ctxOpts);
  const page = await context.newPage();
  page.setDefaultTimeout(Number(opt.timeout) || 10000);
  page.on('dialog', d => { console.log(`  dialog (${d.type()}) dismissed: ${d.message()}`); d.dismiss().catch(() => {}); });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e.message || e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  return { browser, context, page, errors };
}

async function settle(page, wait) {
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  if (wait === undefined || wait === true) return;
  if (/^\d+$/.test(String(wait))) await page.waitForTimeout(Number(wait));
  else await page.waitForSelector(String(wait), { timeout: 15000 });
}

function outDir(opt) {
  const d = path.resolve(opt.out && opt.out !== true ? opt.out : 'captures');
  fs.mkdirSync(d, { recursive: true });
  return d;
}

// ---------- discover ----------
async function discoverElements(page) {
  return page.evaluate(() => {
    const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
    const txt = el => (el.innerText || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 80);
    const labelOf = el => {
      if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
      if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return l.innerText.trim(); }
      const p = el.closest('label');
      if (p) { const c = p.cloneNode(true); c.querySelectorAll('input,select,textarea').forEach(x => x.remove()); return c.innerText.trim(); }
      return el.getAttribute('placeholder') || el.getAttribute('title') || el.getAttribute('name') || '';
    };
    const roleOf = el => {
      const r = el.getAttribute('role'); if (r) return r;
      const t = el.tagName.toLowerCase(), ty = (el.getAttribute('type') || '').toLowerCase();
      if (t === 'a' && el.hasAttribute('href')) return 'link';
      if (t === 'button' || ['button', 'submit', 'reset'].includes(ty)) return 'button';
      if (t === 'select') return 'combobox';
      if (t === 'textarea') return 'textbox';
      if (t === 'input') return { checkbox: 'checkbox', radio: 'radio' }[ty] || 'textbox';
      return t;
    };
    const selectorOf = (el, role, name) => {
      const tidAttr = ['data-testid', 'data-test', 'data-cy'].find(a => el.hasAttribute(a));
      if (tidAttr) return `[${tidAttr}="${el.getAttribute(tidAttr)}"]`;
      if (el.id && !/\d{3,}/.test(el.id)) return `#${CSS.escape(el.id)}`;
      if (name && ['link', 'button', 'tab', 'menuitem', 'checkbox', 'radio', 'textbox', 'combobox'].includes(role))
        return `role=${role}[name="${name.replace(/"/g, '\\"').slice(0, 60)}"]`;
      if (el.getAttribute('name')) return `${el.tagName.toLowerCase()}[name="${el.getAttribute('name')}"]`;
      return null;
    };
    const q = 'a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=link],[role=tab],[role=menuitem],[onclick]';
    const items = [];
    for (const el of document.querySelectorAll(q)) {
      if (!vis(el)) continue;
      const role = roleOf(el);
      const raw = ['textbox', 'combobox', 'checkbox', 'radio'].includes(role) ? labelOf(el) : (txt(el) || labelOf(el));
      const name = (raw || '').replace(/\s+/g, ' ').trim().slice(0, 80);
      const inNav = !!el.closest('nav,header,[role=navigation],[role=menubar],aside');
      items.push({ role, name, selector: selectorOf(el, role, name), href: el.getAttribute('href') || undefined,
        type: el.getAttribute('type') || undefined, required: el.required || undefined, area: inNav ? 'navigation' : 'content' });
    }
    const headings = [...document.querySelectorAll('h1,h2,h3')].filter(vis).map(h => `${h.tagName} ${txt(h)}`);
    return { title: document.title, url: location.href, headings, items };
  });
}

function discoverMarkdown(d) {
  const lines = [`# ${d.title || d.url}`, '', `- URL: ${d.url}`, ''];
  if (d.headings.length) lines.push('## Headings', '', ...d.headings.map(h => `- ${h}`), '');
  for (const area of ['navigation', 'content']) {
    const rows = d.items.filter(i => i.area === area);
    if (!rows.length) continue;
    lines.push(`## ${area === 'navigation' ? 'Navigation / menus' : 'Content: fields and actions'}`, '',
      '| Role | Name | Selector | Extra |', '|---|---|---|---|');
    for (const r of rows) {
      const extra = [r.href && `href ${r.href}`, r.type && `type ${r.type}`, r.required && 'required'].filter(Boolean).join(', ');
      lines.push(`| ${r.role} | ${(r.name || '').replace(/\|/g, '\\|')} | ${r.selector ? '`' + r.selector + '`' : '—'} | ${extra} |`);
    }
    lines.push('');
  }
  return lines.join('\n');
}

// ---------- flow ----------
async function highlight(page, selector) {
  await page.locator(selector).first().evaluate(el => {
    el.scrollIntoView({ block: 'center' });
    el.dataset.pcOutline = el.style.outline;
    el.style.outline = '3px solid #e5484d'; el.style.outlineOffset = '2px';
  }).catch(() => {});
}
async function unhighlight(page, selector) {
  await page.locator(selector).first().evaluate(el => { el.style.outline = el.dataset.pcOutline || ''; el.style.outlineOffset = ''; }).catch(() => {});
}

async function runFlow(file, opt) {
  const flow = JSON.parse(fs.readFileSync(file, 'utf8'));
  const o = { ...flow.options, ...opt };
  const dir = outDir({ out: opt.out || path.join('captures', slug(flow.name || path.basename(file, '.json'))) });
  const { browser, context, page, errors } = await launch(o);
  const report = [`# ${flow.name || 'Flow'}`, '', `Base URL: ${flow.baseUrl || '—'}`, ''];
  let n = 0, failed = false;
  const secretFields = []; // filled from $ENV: -> masked in every screenshot
  const mask = () => secretFields.map(sel => page.locator(sel));
  const shot = async (name, s) => {
    n++;
    const f = `${String(n).padStart(2, '0')}-${slug(name || 'step')}.png`;
    if (s.highlight) await highlight(page, s.highlight);
    const target = s.selector ? page.locator(s.selector).first() : page;
    await target.screenshot({ path: path.join(dir, f), fullPage: !s.selector && !!(s.full ?? o.full), mask: mask() });
    if (s.highlight) await unhighlight(page, s.highlight);
    report.push(`### ${n}. ${s.caption || name || ''}`, '', `![${name || f}](${f})`, '');
    console.log(`  📸 ${f}`);
  };
  try {
    for (const [i, s] of (flow.steps || []).entries()) {
      const label = `${i + 1}. ${s.action}${s.selector ? ' ' + s.selector : ''}${s.url ? ' ' + s.url : ''}`;
      console.log(label);
      switch (s.action) {
        case 'goto': await page.goto(new URL(s.url, flow.baseUrl || undefined).href, { waitUntil: 'domcontentloaded' }); await settle(page, s.wait); break;
        case 'click': await page.locator(s.selector).first().click(); await settle(page, s.wait); break;
        case 'hover': await page.locator(s.selector).first().hover(); break;
        case 'fill': { const v = resolveValue(s.value); await page.locator(s.selector).first().fill(v.value); if (v.secret) secretFields.push(s.selector); console.log(`  = ${v.shown}`); break; }
        case 'select': await page.locator(s.selector).first().selectOption(String(s.value)); break;
        case 'check': await page.locator(s.selector).first().check(); break;
        case 'press': await (s.selector ? page.locator(s.selector).first() : page.keyboard).press(s.key); await settle(page, s.wait); break;
        case 'wait': await settle(page, s.ms ?? s.selector ?? s.wait); break;
        case 'screenshot': await shot(s.name, s); break;
        case 'discover': { const d = await discoverElements(page); const f = `${String(++n).padStart(2, '0')}-${slug(s.name || 'discover')}`;
          fs.writeFileSync(path.join(dir, f + '.json'), JSON.stringify(d, null, 2)); fs.writeFileSync(path.join(dir, f + '.md'), discoverMarkdown(d));
          report.push(`### ${n}. Discover: ${d.title}`, '', `[${f}.md](${f}.md)`, ''); console.log(`  🔎 ${f}.md`); break; }
        default: throw new Error(`unknown action "${s.action}"`);
      }
      if (s.screenshot) await shot(s.screenshot === true ? s.action : s.screenshot, { caption: s.caption });
    }
  } catch (e) {
    failed = true;
    e.message = String(e.message).replace(/\x1b\[[0-9;]*m/g, '');
    console.error(`✗ ${e.message.split('\n')[0]}`);
    await page.screenshot({ path: path.join(dir, 'ERROR.png'), fullPage: true, mask: mask() }).catch(() => {});
    report.push('## ✗ Error', '', '```', e.message.split('\n').slice(0, 6).join('\n'), '```', '', '![error](ERROR.png)', '');
  }
  if (errors.length) report.push('## Browser console errors', '', ...errors.slice(0, 20).map(x => `- ${x}`), '');
  fs.writeFileSync(path.join(dir, 'report.md'), report.join('\n'));
  console.log(`report: ${path.join(dir, 'report.md')}`);
  await context.close(); await browser.close();
  process.exitCode = failed ? 1 : 0;
}

// ---------- main ----------
const { pos, opt } = parseArgs(process.argv.slice(2));
const [cmd, target] = pos;
if (!cmd || opt.help) { console.log(HELP); process.exit(cmd ? 0 : 1); }

if (cmd === 'flow') {
  if (!target) throw new Error('flow needs a flow.json');
  await runFlow(target, opt);
} else if (cmd === 'login') {
  if (!target || !opt.storage || opt.storage === true) { console.log('login needs <url> --storage FILE'); process.exit(1); }
  const { browser, context, page } = await launch({ ...opt, headed: true, storage: undefined });
  await page.goto(toUrl(target));
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  await rl.question('Log in in the browser window, then press Enter here to save the session… ');
  rl.close();
  await context.storageState({ path: opt.storage });
  fs.chmodSync(opt.storage, 0o600);
  console.log(`session saved: ${opt.storage} (contains cookies; do not commit or share it)`);
  await browser.close();
} else if (cmd === 'shot' || cmd === 'discover') {
  if (!target) { console.log(HELP); process.exit(1); }
  const url = toUrl(target);
  const dir = outDir(opt);
  const name = opt.name && opt.name !== true ? opt.name : slug(target);
  const { browser, context, page, errors } = await launch(opt);
  const resp = await page.goto(url, { waitUntil: 'domcontentloaded' });
  await settle(page, opt.wait);
  console.log(`${resp ? resp.status() : '-'} ${page.url()}  "${await page.title()}"`);
  const png = path.join(dir, `${name}.png`);
  if (opt.selector && opt.selector !== true) await page.locator(opt.selector).first().screenshot({ path: png });
  else await page.screenshot({ path: png, fullPage: !!opt.full || cmd === 'discover' });
  console.log(`📸 ${png}`);
  if (cmd === 'discover') {
    const d = await discoverElements(page);
    fs.writeFileSync(path.join(dir, `${name}.json`), JSON.stringify(d, null, 2));
    fs.writeFileSync(path.join(dir, `${name}.md`), discoverMarkdown(d));
    console.log(`🔎 ${path.join(dir, name + '.md')}  (${d.items.length} elements)`);
  }
  if (errors.length) console.log(`console errors (${errors.length}):\n` + errors.slice(0, 10).map(e => '  - ' + e).join('\n'));
  await context.close(); await browser.close();
} else {
  console.log(HELP); process.exit(1);
}
