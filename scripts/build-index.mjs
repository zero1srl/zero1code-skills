// Builds index.json (schema 2) from two sources:
//  - hosted skills: skills/<name>/SKILL.md in this repository (our own work);
//  - external skills: catalog.json, a reference to a folder of someone else's repository, pinned to a commit.
//    Nothing of theirs is copied here: the app downloads each file from the author's repository at that commit,
//    verifies size and sha256, and places the repository's license files next to the skill.
// Usage: node scripts/build-index.mjs            rebuild everything (network; GITHUB_TOKEN raises the API limit)
//        node scripts/build-index.mjs --check    offline: index.json still matches skills/ and catalog.json
import { createHash } from 'node:crypto'
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, relative, resolve, sep } from 'node:path'

const NAME = /^[a-z0-9][a-z0-9._-]*$/ // same rule the app applies before it writes to disk
const SHA = /^[0-9a-f]{40}$/
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

const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex')
const hasScripts = (paths) => paths.some((p) => p.startsWith('scripts/') || SCRIPT_EXT.has(p.slice(p.lastIndexOf('.'))))
// code-unit order, not localeCompare: the index must be byte-identical on every machine and in CI
const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0)
const byName = (a, b) => cmp(a.name, b.name)

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? (e.name === "__pycache__" ? [] : walk(join(dir, e.name))) : e.isFile() && !e.name.endsWith(".pyc") ? [join(dir, e.name)] : [])
}

/** Skills that live in this repository. */
export function hosted(root) {
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
    const files = walk(dir).sort().map((p) => {
      const bytes = readFileSync(p)
      return { path: relative(dir, p).split(sep).join('/'), size: bytes.length, sha256: sha256(bytes) }
    })
    if (files.length > MAX_FILES) fail(`more than ${MAX_FILES} files`)
    if (files.reduce((n, f) => n + f.size, 0) > MAX_BYTES) fail(`larger than ${MAX_BYTES} bytes`)
    skills.push({
      name, description: meta.description ?? '', license: meta.license ?? '', category: meta.metadata?.category ?? '',
      author: meta.metadata?.author ?? '', hasScripts: hasScripts(files.map((f) => f.path)), files,
    })
  }
  return { errors, skills }
}

const rawUrl = (repo, ref, path) => `https://raw.githubusercontent.com/${repo}/${ref}/${path.split('/').map(encodeURIComponent).join('/')}`

async function pool(items, size, fn) {
  const out = new Array(items.length)
  let next = 0
  await Promise.all(Array.from({ length: size }, async () => {
    while (next < items.length) { const k = next++; out[k] = await fn(items[k]) }
  }))
  return out
}

/** Skills referenced in catalog.json: file lists and hashes are read from the author's repository at the pinned commit. */
export async function external(catalog, { fetchImpl = fetch, token } = {}) {
  const errors = []
  const skills = []
  const headers = { 'user-agent': 'zero1code-skills', ...(token ? { authorization: `Bearer ${token}` } : {}) }
  const bytesOf = async (url) => {
    const response = await fetchImpl(url, { headers })
    if (!response.ok) throw new Error(`${url}: ${response.status}`)
    return Buffer.from(await response.arrayBuffer())
  }
  for (const source of catalog.sources ?? []) {
    const { repo, ref } = source
    const fail = (msg) => errors.push(`${repo}: ${msg}`)
    if (!/^[\w.-]+\/[\w.-]+$/.test(repo ?? '') || !SHA.test(ref ?? '')) { fail('repo must be owner/name and ref a 40-character commit'); continue }
    if (!source.license) { fail('license is required'); continue }
    const response = await fetchImpl(`https://api.github.com/repos/${repo}/git/trees/${ref}?recursive=1`, { headers })
    const tree = response.ok ? await response.json() : undefined
    if (tree === undefined || tree.truncated || !Array.isArray(tree.tree)) { fail(`tree unavailable or truncated (${response.status})`); continue }
    const blobs = new Map(tree.tree.filter((e) => e.type === 'blob').map((e) => [e.path, e]))
    for (const entry of source.skills ?? []) {
      const name = entry.name
      const bad = (msg) => errors.push(`${repo} ${name}: ${msg}`)
      if (!NAME.test(name ?? '')) { bad('invalid name'); continue }
      const prefix = `${entry.path}/`
      const picked = []
      for (const [path, blob] of blobs) {
        if (!path.startsWith(prefix)) continue
        const src = path.slice(prefix.length)
        if (entry.files && !entry.files.includes(src)) continue
        const dest = entry.rename?.[src] ?? src // e.g. graphify ships skill.md, which its installer copies to SKILL.md
        if (blob.mode === '120000') { bad(`${src} is a symlink`); continue }
        picked.push({ dest, from: path, size: blob.size })
      }
      for (const lf of source.licenseFiles ?? []) {
        const blob = blobs.get(lf)
        if (blob === undefined) { bad(`license file ${lf} not found at the commit`); continue }
        if (picked.some((p) => p.dest === lf)) continue
        picked.push({ dest: lf, from: lf, size: blob.size })
      }
      if (!picked.some((p) => p.dest === 'SKILL.md')) { bad('SKILL.md missing'); continue }
      if (picked.length > MAX_FILES) { bad(`more than ${MAX_FILES} files`); continue }
      if (picked.reduce((n, p) => n + p.size, 0) > MAX_BYTES) { bad(`larger than ${MAX_BYTES} bytes`); continue }
      picked.sort((a, b) => cmp(a.dest, b.dest))
      const files = await pool(picked, 8, async (p) => {
        const bytes = await bytesOf(rawUrl(repo, ref, p.from))
        if (bytes.length !== p.size) throw new Error(`${p.from}: size differs from the tree`)
        return { path: p.dest, size: bytes.length, sha256: sha256(bytes), url: rawUrl(repo, ref, p.from), bytes }
      })
      const meta = frontmatter(files.find((f) => f.path === 'SKILL.md').bytes.toString('utf8'))
      if (meta === undefined) { bad('SKILL.md has no frontmatter'); continue }
      if (meta.name !== name) bad(`frontmatter name "${meta.name}" must equal "${name}"`)
      if (!meta.description) bad('description is required')
      skills.push({
        name, description: meta.description ?? '', license: source.license, category: entry.category ?? '',
        author: repo.split('/')[0], source: `github.com/${repo}`, repo, ref, path: entry.path,
        hasScripts: hasScripts(files.map((f) => f.path)),
        files: files.map(({ bytes: _bytes, ...f }) => f),
      })
    }
  }
  return { errors, skills }
}

export function render(skills) {
  const names = new Set()
  for (const s of skills) { if (names.has(s.name)) throw new Error(`duplicate skill name ${s.name}`); names.add(s.name) }
  return JSON.stringify({ schema: 2, skills: [...skills].sort(byName) }, null, 2) + '\n'
}

/** Offline consistency: hosted entries regenerate identically and external entries still match catalog.json. */
export function check(root, indexText, catalog) {
  const errors = []
  const index = JSON.parse(indexText)
  const h = hosted(root)
  errors.push(...h.errors)
  const want = JSON.stringify(h.skills)
  const have = JSON.stringify(index.skills.filter((s) => s.repo === undefined))
  if (want !== have) errors.push('hosted skills differ from index.json: run node scripts/build-index.mjs')
  const listed = (catalog.sources ?? []).flatMap((s) => (s.skills ?? []).map((e) => `${s.repo}@${s.ref}:${e.path}=${e.name}`)).sort()
  const indexed = index.skills.filter((s) => s.repo !== undefined).map((s) => `${s.repo}@${s.ref}:${s.path}=${s.name}`).sort()
  if (JSON.stringify(listed) !== JSON.stringify(indexed)) errors.push('catalog.json and index.json disagree: run node scripts/build-index.mjs')
  return errors
}

const readCatalog = (root) => existsSync(join(root, 'catalog.json')) ? JSON.parse(readFileSync(join(root, 'catalog.json'), 'utf8')) : { sources: [] }

if (process.argv[1]?.endsWith('build-index.mjs')) { // CLI only; the tests import the functions
  const at = process.argv.indexOf('--root')
  const root = resolve(at > 0 ? process.argv[at + 1] : join(import.meta.dirname, '..'))
  const file = join(root, 'index.json')
  if (process.argv.includes('--check')) {
    const errors = existsSync(file) ? check(root, readFileSync(file, 'utf8'), readCatalog(root)) : ['index.json missing']
    if (errors.length) { console.error(errors.join('\n')); process.exit(1) }
    console.log('index.json: consistent')
  } else {
    const h = hosted(root)
    const e = await external(readCatalog(root), { token: process.env.GITHUB_TOKEN })
    const errors = [...h.errors, ...e.errors]
    if (errors.length) { console.error(errors.join('\n')); process.exit(1) }
    writeFileSync(file, render([...h.skills, ...e.skills]))
    console.log(`index.json: ${h.skills.length} hosted, ${e.skills.length} external`)
  }
}
