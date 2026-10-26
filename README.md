# zero1code-skills

Catalogo delle skill di zero1code. L'app desktop legge `index.json` e installa le skill scelte dall'utente.

Pubblico in lettura. Solo i collaboratori dell'organizzazione scrivono su `main`.

## Due tipi di voce

- **Ospitate** (`skills/<nome>/`): skill scritte da noi, nel repository.
- **Riferimenti** (`catalog.json`): skill di terzi. **Qui non c'è nessuna copia del loro lavoro.** L'indice riporta, per ogni
  skill, il repository dell'autore, un commit fissato e l'hash di ogni file. L'app scarica da `raw.githubusercontent.com` a quel
  commit, verifica dimensione e sha256 e mette accanto alla skill i file di licenza del repository originale (`LICENSE`,
  `NOTICE`…). Le licenze restano quelle degli autori (MIT, Apache-2.0, GPL-3.0 per le skill SAP).

## Skill nostre (MIT, copyright zero1code)

`zero1-skill-creator` guida l'agente (e l'utente) a creare, correggere e controllare una skill (`skill_tool.py`, solo libreria standard). `zero1-docx`, `zero1-xlsx`, `zero1-pptx`: Word, Excel e PowerPoint con `python-docx`, `openpyxl` e `python-pptx`, scritte
da zero dalla documentazione pubblica delle librerie (non derivano da altre skill). Ognuna ha script di controllo
(`describe.py --check`), aiuti per ciò che le librerie non fanno (`helpers.py`) e, dove serve, modifiche tracciate
(`track.py`), ricalcolo delle formule (`recalc.py`), compilazione di modelli (`replace_text.py`) e anteprima
(`render.py`, richiede LibreOffice). I test Python sono in `tests/` (`python -m unittest discover -s tests`).

## Aggiungere una skill nostra

1. Crea `skills/<nome>/SKILL.md` (nome = cartella: minuscole, cifre, `.`, `_`, `-`).
2. Frontmatter obbligatorio:

   ```yaml
   ---
   name: <nome>
   description: cosa fa e quando usarla
   license: MIT
   metadata:
     category: sviluppo
     author: zero1
   ---
   ```

3. `node scripts/build-index.mjs` rigenera `index.json`; committalo con la skill.

## Aggiungere un riferimento a una skill di terzi

1. Leggi la licenza del repository e della cartella: senza una licenza che permetta la redistribuzione, non entra.
2. In `catalog.json` aggiungi la skill sotto la sua sorgente (`repo`, `ref` = commit completo da 40 caratteri, `license`,
   `licenseFiles` = file di licenza alla radice del repo). `path` è la cartella della skill nel repository; `files` limita
   i file; `rename` ne rinomina uno (es. `skill.md` → `SKILL.md`). Il nome nel catalogo deve coincidere con il campo `name`
   del suo `SKILL.md`.
3. `GITHUB_TOKEN=$(gh auth token) node scripts/build-index.mjs` scarica i file ai commit indicati e rigenera `index.json`.
4. Per aggiornare una skill si cambia `ref` e si rigenera: il commit fissato è ciò che l'utente riceve, non il ramo.

## Gruppi

Ogni skill ha da 1 a 4 gruppi (può comparire in più gruppi): l'app li usa per filtrare l'elenco. Per i riferimenti si scrivono in `catalog.json` (campo `groups`, obbligatorio: la costruzione dell'indice fallisce senza); per le skill ospitate si aggiunge il nome in `hostedGroups` (il gruppo `zero1code skill` è automatico). Un nome con ` · ` (es. `SAP · ABAP`) è un sotto-gruppo di `SAP`.

## Controlli

`node --test` e `node scripts/build-index.mjs --check` (offline: l'indice corrisponde a `skills/` e a `catalog.json`) girano
in CI. Limiti per skill: 200 file, 5 MB. `hasScripts: true` segnala `scripts/` o file eseguibili: l'app lo mostra prima
dell'installazione; rivedi ogni script prima di aggiungere la voce.

## Formato di `index.json` (schema 2)

`{ schema: 2, skills: [{ name, description, license, category, author, hasScripts, files: [{ path, size, sha256, url? }], source?, repo?, ref?, path? }] }`.
`url` è presente per i riferimenti ed è sempre un URL `raw.githubusercontent.com` con commit completo; l'app rifiuta
qualsiasi altro host.
