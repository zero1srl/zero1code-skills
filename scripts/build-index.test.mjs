// node --test
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { check, external, hosted, render } from './build-index.mjs'

const skill = (root, name, front, extra = {}) => {
  const dir = join(root, 'skills', name)
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, 'SKILL.md'), `---\n${front}\n---\nBody\n`)
  for (const [file, body] of Object.entries(extra)) {
    mkdirSync(join(dir, file, '..'), { recursive: true })
    writeFileSync(join(dir, file), body)
  }
}

test('valid hosted skill is indexed with metadata and script flag', () => {
  const root = mkdtempSync(join(tmpdir(), 'skills-'))
  skill(root, 'good', 'name: good\ndescription: >\n  Does a\n  thing.\nlicense: MIT\nmetadata:\n  category: dev\n  author: zero1', { 'scripts/run.sh': 'echo' })
  const { errors, skills } = hosted(root)
  assert.deepEqual(errors, [])
  assert.equal(skills[0].description, 'Does a thing.')
  assert.equal(skills[0].category, 'dev')
  assert.equal(skills[0].hasScripts, true)
  assert.deepEqual(skills[0].groups, ['zero1code skill'])
  assert.deepEqual(hosted(root, { good: ['Office e documenti'] }).skills[0].groups, ['zero1code skill', 'Office e documenti'])
  assert.deepEqual(skills[0].files.map((f) => f.path), ['SKILL.md', 'scripts/run.sh'])
})

test('name mismatch, missing description and license are all reported', () => {
  const root = mkdtempSync(join(tmpdir(), 'skills-'))
  skill(root, 'bad', 'name: other')
  assert.equal(hosted(root).errors.length, 3)
})

const REF = 'a'.repeat(40)
const files = {
  'pkg/demo/SKILL.md': '---\nname: demo\ndescription: Demo\n---\nHi\n',
  'pkg/demo/run.py': 'print(1)\n',
  'pkg/other/SKILL.md': '---\nname: other\ndescription: Other\n---\n',
  LICENSE: 'MIT text\n',
}
const fakeFetch = async (url) => {
  const u = String(url)
  if (u.includes('/git/trees/')) {
    return Response.json({ truncated: false, tree: Object.entries(files).map(([path, body]) => ({ path, type: 'blob', mode: '100644', size: body.length })) })
  }
  const path = decodeURIComponent(u.split(`/${REF}/`)[1])
  return path in files ? new Response(files[path]) : new Response('', { status: 404 })
}
const catalog = { sources: [{ repo: 'acme/skills', ref: REF, license: 'MIT', licenseFiles: ['LICENSE'], skills: [{ name: 'demo', path: 'pkg/demo', groups: ['Sviluppo web', 'Design e UI'] }] }] }

test('external skill: files pinned to the commit, license file added, only its own folder', async () => {
  const { errors, skills } = await external(catalog, { fetchImpl: fakeFetch })
  assert.deepEqual(errors, [])
  assert.deepEqual(skills[0].files.map((f) => f.path), ['LICENSE', 'SKILL.md', 'run.py'])
  assert.equal(skills[0].files[1].url, `https://raw.githubusercontent.com/acme/skills/${REF}/pkg/demo/SKILL.md`)
  assert.equal(skills[0].hasScripts, true)
  assert.deepEqual(skills[0].groups, ['Sviluppo web', 'Design e UI'])
})

test('an external skill without groups is rejected', async () => {
  const bad = { sources: [{ ...catalog.sources[0], skills: [{ name: 'demo', path: 'pkg/demo' }] }] }
  const { errors } = await external(bad, { fetchImpl: fakeFetch })
  assert.match(errors[0], /groups/)
})

test('external skill with a frontmatter name that differs from the catalog name is rejected', async () => {
  const bad = { sources: [{ ...catalog.sources[0], skills: [{ name: 'renamed', path: 'pkg/demo', groups: ['Sviluppo web'] }] }] }
  const { errors } = await external(bad, { fetchImpl: fakeFetch })
  assert.match(errors[0], /must equal "renamed"/)
})

test('check passes on a fresh index and fails when catalog.json drifts', async () => {
  const root = mkdtempSync(join(tmpdir(), 'skills-'))
  const ext = await external(catalog, { fetchImpl: fakeFetch })
  const text = render([...hosted(root).skills, ...ext.skills])
  assert.deepEqual(check(root, text, catalog), [])
  const moved = { sources: [{ ...catalog.sources[0], ref: 'b'.repeat(40) }] }
  assert.equal(check(root, text, moved).length, 1)
})
