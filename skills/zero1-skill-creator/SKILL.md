---
name: zero1-skill-creator
description: >
  Guide the user through creating, improving or checking an agent skill (a SKILL.md with instructions the agent loads
  on demand) and save it where zero1code reads it. Use when the user says "crea una skill", "voglio una skill che...",
  "trasforma questa procedura in una skill", "migliora/correggi la mia skill", or asks how to teach the agent a
  repeatable task, a house style or a company procedure.
license: MIT
metadata:
  category: Skill
  author: zero1code
---

# Creating a skill

A skill is a folder with a `SKILL.md`: a short header (`name`, `description`) and the instructions. The agent always
sees the header of every skill, and loads the body only when a request matches the description. So: the description
decides **when** the skill is used, the body decides **how well** it is done.

Talk to the user in their language. Be brief: ask only what you need, then write.

## 1. Understand the task (ask, don't guess)

Ask at most four short questions, skipping what the user already said:

1. What should the agent do with this skill? Ask for one real example request, with input and the result they expect.
2. When should it apply, and when not (which requests, files, situations)?
3. Are there fixed rules: format, tone, company wording, mandatory steps, things to never do?
4. Should it be only for zero1code, or shared with the user's other coding tools (global)?

If the user pasted a procedure, a document or an example output, work from it: extract the steps and the rules.

## 2. Write the description first

The description is the most important line. In 1-3 sentences say **what the skill does and when to use it**, naming the
situations, request phrases or file types that should trigger it (in the user's language and the words they would
really type). Make it specific enough not to fire on unrelated requests and wide enough to fire on the real ones.

Good: "Scrive e riassume verbali di riunione nel formato aziendale (decisioni, azioni con responsabile e scadenza).
Usala quando l'utente chiede un verbale, un riassunto di riunione o le azioni emerse da una chiamata."
Weak: "Aiuta con le riunioni."

Maximum 1024 characters.

## 3. Write the body

- Start with the goal in one sentence, then **when to use it** and **when not to**.
- Give the steps as a numbered list of imperative instructions the agent can follow without guessing.
- Show the expected output once (a short template or example), not five.
- State the rules and the failure cases ("se manca la data, chiedila; non inventarla").
- Explain **why** for rules that are not obvious: the agent applies them better and handles edge cases.
- Keep it short and concrete: under 500 lines. Move long reference material (templates, glossaries, tables) into
  extra files next to `SKILL.md` (`references/...`) and say in the body when to read them. Put deterministic
  operations in small scripts (`scripts/...`) and say how to run them.
- No secrets, tokens or passwords: skills are plain files and may be shared.

## 4. Save it

Use the helper, which validates and never overwrites an existing skill. Write the body to a temporary file first:

```bash
python scripts/skill_tool.py new verbali-riunione --scope local \
  --description "Scrive verbali di riunione nel formato aziendale. Usala quando..." \
  --body-file corpo.md
```

- `--scope local`: only zero1code (`~/.dsh/skills/<name>`).
- `--scope global`: shared library `~/.agents/skills/<name>` plus a link so zero1code uses it too.
- Names: lowercase letters, digits, `-`, `.`, `_`, at most 64 characters, equal to the `name` in the header.
- Extra files (references, scripts) go inside the same folder: create them next to `SKILL.md` after `new`.

Then run `python scripts/skill_tool.py check <name>`; fix every error and read the advice.

## 5. Test it with the user

1. Tell the user the skill is saved; it appears in the Skill panel and in the `/` menu (a new chat may be needed).
2. Ask them to try the example request from step 1 and to say what was missing or wrong.
3. Adjust the description (if it did not trigger or triggered too often) or the body (if the result was off), keep
   changes small, run `check` again.

## Improving an existing skill

Read its `SKILL.md` first, change only what the user asked, keep the header valid (`name` unchanged), and run `check`.
If it is shared (global), say that the change applies to the user's other tools too. Never delete a skill without an
explicit request.
