// Builds index.json from skills/*/SKILL.md and validates every skill. `--check` fails when index.json is stale.
// Usage: node scripts/build-index.mjs [--check] [--root <dir>]
import { createHash } from 'node:crypto'
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { join, relative, resolve, sep } from 'node:path'

const NAME = /^[a-z0-9][a-z0-9._-]*$/ // same rule the app applies before it writes to disk
const MAX_FILES = 200
const MAX_BYTES = 5 * 1024 * 1024
const SCRIPT_EXT = new Set(['.sh', '.ps1', '.bat', '.cmd', '.py', '.js', '.mjs', '.cjs', '.ts'])

/** Frontmatter keys: scalars, `>`/`|` blocks and one level of nested `key: value` (e.g. metadata). */
// shortcut: not full YAML (no lists, no deeper nesting); a skill that needs more fails validation, extend then.
export function frontmatter(text) {
  const block = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text)?.[1]
  if (block === undefined) return undefined
  const lines = block.split(/\r?\n/)
  const out = {}
  const unquote = (v) => v.trim().replace(/^(['"])(.*)\1$/, '$2')
  for (let i = 0; i < lines.length; i++) {
    const top = /^([A-Za-z][\w-]*):\s*(.*)$/.exec(lines[i])
    if (!top) continue
    const [, key, raw] = top
    const children = []
    while (i + 1 < lines.length && /^\s+\S/.test(lines[i + 1])) children.push(lines[++i].trim())
    if (/^[>|][+-]?$/.test(raw)) out[key] = children.join(raw[0] === '>' ? ' ' : '\n')
    else if (raw === '' && children.length) {
      out[key] = Object.fromEntries(children.map((c) => /^([\w-]+):\s*(.*)$/.exec(c)).filter(Boolean).map((m) => [m[1], unquote(m[2])]))
    } else out[key] = unquote(raw)
  }
  return out
}

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(join(dir, e.name)) : e.isFile() ? [join(dir, e.name)] : [])
}

export function build(root) {
  const skillsDir = join(root, 'skills')
  const errors = []
  const skills = []
  const names = existsSync(skillsDir)
    ? readdirSync(skillsDir, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name).sort()
    : []
  for (const name of names) {
    const dir = join(skillsDir, name)
    const fail = (msg) => errors.push(`skills/${name}: ${msg}`)
    if (!NAME.test(name)) { fail('folder name must match ' + NAME); continue }
    if (!existsSync(join(dir, 'SKILL.md'))) { fail('SKILL.md missing'); continue }
    const meta = frontmatter(readFileSync(join(dir, 'SKILL.md'), 'utf8'))
    if (meta === undefined) { fail('SKILL.md has no frontmatter'); continue }
    if (meta.name !== name) fail(`frontmatter name "${meta.name}" must equal the folder name`)
    if (!meta.description) fail('description is required')
    if (!meta.license) fail('license is required')
    const paths = walk(dir).sort()
    const files = paths.map((p) => {
      const bytes = readFileSync(p)
      return { path: relative(dir, p).split(sep).join('/'), size: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') }
    })
    const total = files.reduce((n, f) => n + f.size, 0)
    if (files.length > MAX_FILES) fail(`more than ${MAX_FILES} files`)
    if (total > MAX_BYTES) fail(`larger than ${MAX_BYTES} bytes`)
    const hasScripts = files.some((f) => f.path.startsWith('scripts/') || SCRIPT_EXT.has(f.path.slice(f.path.lastIndexOf('.'))))
    skills.push({
      name,
      description: meta.description ?? '',
      license: meta.license ?? '',
      category: meta.metadata?.category ?? '',
      author: meta.metadata?.author ?? '',
      hasScripts,
      files,
    })
  }
  return { errors, text: JSON.stringify({ schema: 1, skills }, null, 2) + '\n' }
}

if (process.argv[1]?.endsWith('build-index.mjs')) { // CLI only; the test imports build()
  const at = process.argv.indexOf('--root')
  const root = resolve(at > 0 ? process.argv[at + 1] : join(import.meta.dirname, '..'))
  const { errors, text } = build(root)
  if (errors.length) { console.error(errors.join('\n')); process.exit(1) }
  const file = join(root, 'index.json')
  if (process.argv.includes('--check')) {
    if (!existsSync(file) || readFileSync(file, 'utf8') !== text) { console.error('index.json is stale: run node scripts/build-index.mjs'); process.exit(1) }
  } else writeFileSync(file, text)
  console.log(`index.json: ${JSON.parse(text).skills.length} skill(s)`)
}
