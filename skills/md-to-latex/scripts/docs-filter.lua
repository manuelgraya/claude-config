-- Pandoc filter for md2latex.py: makes links, images, code, diagrams and
-- callouts work in a multi-file LaTeX project. Configured through PD_* variables.

local ROOT = os.getenv('PD_ROOT') or '.'
local SOURCE = os.getenv('PD_SOURCE') or ''
local SLUG = os.getenv('PD_SLUG') or 'doc'
local TITLE = os.getenv('PD_TITLE') or SLUG
local OUT = os.getenv('PD_OUT') or '.'
local MANIFEST = os.getenv('PD_MANIFEST')
local MAP_FILE = os.getenv('PD_MAP')

local SOURCE_DIR = SOURCE:match('^(.*)/[^/]*$') or ''
local image_count, diagram_count = 0, 0

local KINDS = {
  note = { 'pdnote', 'PdStrNote' }, info = { 'pdnote', 'PdStrNote' },
  abstract = { 'pdnote', 'PdStrNote' }, example = { 'pdnote', 'PdStrNote' },
  tip = { 'pdtip', 'PdStrTip' }, hint = { 'pdtip', 'PdStrTip' },
  success = { 'pdtip', 'PdStrTip' },
  important = { 'pdimportant', 'PdStrImportant' },
  warning = { 'pdwarning', 'PdStrWarning' }, attention = { 'pdwarning', 'PdStrWarning' },
  caution = { 'pdcaution', 'PdStrCaution' }, danger = { 'pdcaution', 'PdStrCaution' },
  error = { 'pdcaution', 'PdStrCaution' },
}

local LANGUAGES = {
  sh = 'bash', shell = 'bash', zsh = 'bash', console = 'bash', terminal = 'bash',
  js = 'javascript', ts = 'typescript', py = 'python', rb = 'ruby',
  yml = 'yaml', ps1 = 'powershell', pwsh = 'powershell',
  docker = 'dockerfile', tf = 'hcl', cs = 'cs', ['c#'] = 'cs',
}

local CONVERTED = { svg = 'pdf', gif = 'png', webp = 'png', bmp = 'png', tif = 'png', tiff = 'png' }

local MAP = {}
if MAP_FILE then
  for line in io.lines(MAP_FILE) do
    local path, slug = line:match('^(.-)\t(.*)$')
    if path then MAP[path] = slug end
  end
end

local function warn(message)
  io.stderr:write('PD-WARN: ' .. message .. '\n')
end

local function url_decode(text)
  return (text:gsub('%%(%x%x)', function(hex)
    return string.char(tonumber(hex, 16))
  end))
end

local function is_external(target)
  return target:match('^%a[%w+.%-]*:') ~= nil or target:sub(1, 2) == '//'
end

local function normalize(path)
  local parts = {}
  for part in path:gmatch('[^/]+') do
    if part == '..' then
      if #parts == 0 then return nil end
      table.remove(parts)
    elseif part ~= '.' then
      parts[#parts + 1] = part
    end
  end
  return table.concat(parts, '/')
end

-- Paths starting with "/" are relative to the documentation root.
local function resolve(path)
  if path:sub(1, 1) == '/' or SOURCE_DIR == '' then return normalize(path) end
  return normalize(SOURCE_DIR .. '/' .. path)
end

local function file_exists(path)
  local handle = io.open(path, 'r')
  if handle then handle:close() end
  return handle ~= nil
end

local function find_chapter(path)
  if path == nil then return nil end
  local clean = path:gsub('/$', '')
  local prefix = clean == '' and '' or clean .. '/'
  return MAP[clean] or MAP[clean .. '.md'] or MAP[prefix .. 'README.md'] or MAP[prefix .. 'index.md']
end

local F = {}

function F.Header(el)
  if el.identifier ~= '' then el.identifier = SLUG .. ':' .. el.identifier end
  return el
end

function F.Link(el)
  local target = el.target
  if target:sub(1, 1) == '#' then
    el.target = '#' .. SLUG .. ':' .. url_decode(target:sub(2))
    return el
  end
  if is_external(target) then return nil end
  local path, fragment = target:match('^([^#]*)#?(.*)$')
  local chapter = find_chapter(resolve(url_decode(path)))
  if chapter then
    el.target = fragment ~= '' and ('#' .. chapter .. ':' .. url_decode(fragment)) or ('#chap:' .. chapter)
    return el
  end
  warn('broken link, kept as text: ' .. target)
  return el.content
end

function F.Image(el)
  local src = el.src
  if is_external(src) then
    if src:match('shields%.io') or src:match('badge') then return {} end
    warn('remote image kept as a link: ' .. src)
    local label = pandoc.utils.stringify(el.caption)
    return pandoc.Link(label ~= '' and label or src, src)
  end
  local rel = resolve(url_decode(src:match('^[^?#]*')))
  if rel == nil or not file_exists(ROOT .. '/' .. rel) then
    warn('missing image: ' .. src)
    return pandoc.Emph('[' .. src .. ']')
  end
  image_count = image_count + 1
  local stem, ext = rel:match('([^/]*)%.([^./]+)$')
  if not stem then
    warn('image without an extension: ' .. src)
    return pandoc.Emph('[' .. src .. ']')
  end
  ext = ext:lower()
  local clean = stem:lower():gsub('[^a-z0-9]+', '-')
  local dest = string.format('figures/%s-%02d-%s.%s', SLUG, image_count, clean, CONVERTED[ext] or ext)
  local manifest = assert(io.open(MANIFEST, 'a'))
  manifest:write(rel .. '\t' .. dest .. '\n')
  manifest:close()
  el.src = dest
  return el
end

function F.RawInline(el)
  if el.format ~= 'html' then return nil end
  if el.text:match('^<%s*[bB][rR]') then return pandoc.RawInline('latex', '\\newline{}') end
  if el.text:match('^<%s*[iI][mM][gG]') then
    local blocks = pandoc.read(el.text, 'html').blocks
    return pandoc.utils.blocks_to_inlines(blocks):walk(F)
  end
  return nil
end

-- HTML blocks would otherwise be dropped from LaTeX output along with their text.
function F.RawBlock(el)
  if el.format ~= 'html' or el.text:match('^%s*<!%-%-') then return nil end
  return pandoc.read(el.text, 'html').blocks:walk(F)
end

function F.Para(el)
  local text = pandoc.utils.stringify(el):lower()
  if #el.content == 1 and (text == '[toc]' or text == '[[toc]]') then return {} end
  return nil
end

-- Text drawn with box characters depends on its alignment: wrapping would break
-- it, so a wide block shrinks to fit the line instead.
local function art_options(text)
  if not text:find('\226\148') and not text:find('\226\149') then return '' end
  local longest = 0
  for line in (text .. '\n'):gmatch('(.-)\n') do
    longest = math.max(longest, utf8.len(line) or #line)
  end
  if longest <= 86 then return '' end
  local size = math.max(5.5, 735 / longest)
  return string.format('[fontsize=\\fontsize{%.1f}{%.1f}\\selectfont,breaklines=false]', size, size * 1.25)
end

function F.CodeBlock(el)
  local language = (el.classes[1] or ''):lower()
  if language == 'mermaid' then
    diagram_count = diagram_count + 1
    local name = string.format('diagrams/%s-%02d', SLUG, diagram_count)
    local file = assert(io.open(OUT .. '/' .. name .. '.mmd', 'w'))
    file:write(el.text .. '\n')
    file:close()
    return pandoc.RawBlock('latex', '\\pddiagram{' .. name .. '}')
  end
  if LANGUAGES[language] then el.classes = pandoc.List({ LANGUAGES[language] }) end
  local body = el
  if language == '' or language == 'text' or language == 'txt' or language == 'plain' then
    body = pandoc.RawBlock('latex', '\\begin{pdverb}' .. art_options(el.text) .. '\n' .. el.text .. '\n\\end{pdverb}')
  end
  return {
    pandoc.RawBlock('latex', '\\begin{pdcode}'),
    body,
    pandoc.RawBlock('latex', '\\end{pdcode}'),
  }
end

local function latex_text(markdown)
  local doc = pandoc.Pandoc(pandoc.read(markdown, 'commonmark_x').blocks)
  return (pandoc.write(doc, 'latex'):gsub('%s+$', ''))
end

local function admonition(kind, title, blocks)
  local style = KINDS[kind]
  local heading = title and title ~= '' and latex_text(title) or ('\\' .. style[2])
  local result = pandoc.List({
    pandoc.RawBlock('latex', '\\begin{pdadmonition}{' .. style[1] .. '}{' .. heading .. '}'),
  })
  result:extend(blocks)
  result:insert(pandoc.RawBlock('latex', '\\end{pdadmonition}'))
  return result
end

function F.Div(el)
  for _, class in ipairs(el.classes) do
    local kind = class:lower()
    if KINDS[kind] then
      local blocks = el.content
      local first = blocks[1]
      -- Pandoc's alerts extension adds a default English title; use the translated one.
      if first and first.t == 'Div' and first.classes:includes('title') then blocks:remove(1) end
      return admonition(kind, el.attributes.title, blocks)
    end
  end
  return nil
end

-- GitHub alert syntax: > [!NOTE]
function F.BlockQuote(el)
  local blocks = el.content
  local first = blocks[1]
  if not first or first.t ~= 'Para' or first.content[1].t ~= 'Str' then return nil end
  local marker = first.content[1].text:match('^%[!(%a+)%]$')
  local kind = marker and marker:lower()
  if not kind or not KINDS[kind] then return nil end
  local inlines = first.content
  inlines:remove(1)
  while inlines[1] and (inlines[1].t == 'SoftBreak' or inlines[1].t == 'LineBreak' or inlines[1].t == 'Space') do
    inlines:remove(1)
  end
  if #inlines == 0 then
    blocks:remove(1)
  else
    blocks[1] = pandoc.Para(inlines)
  end
  return admonition(kind, nil, blocks)
end

-- Each source file opens with exactly one chapter heading and a label that other
-- files can link to. A leading logo or badge must not fall into the previous chapter.
local function ensure_chapter(doc)
  local blocks = doc.blocks
  local position
  for i, block in ipairs(blocks) do
    if block.t == 'Header' then
      position = i
      break
    end
  end
  if position and blocks[position].level == 1 then
    local heading = blocks[position]
    blocks:remove(position)
    blocks:insert(1, heading)
  else
    local title = doc.meta.title
    blocks:insert(1, pandoc.Header(1, title and pandoc.utils.stringify(title) or TITLE))
  end
  blocks:insert(2, pandoc.RawBlock('latex', '\\label{chap:' .. SLUG .. '}'))
  doc.blocks = blocks
  return doc
end

return { F, { Pandoc = ensure_chapter } }
