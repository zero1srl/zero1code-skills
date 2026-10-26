# zero1code-skills

Catalogo delle skill di zero1code. L'app desktop legge `index.json` e installa le cartelle di `skills/`.

Pubblico in lettura. Solo i collaboratori dell'organizzazione scrivono su `main`.

## Aggiungere una skill

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
4. La CI esegue `node --test` e `node scripts/build-index.mjs --check`: fallisce se manca un campo,
   se il nome non coincide con la cartella o se `index.json` è vecchio.

## Regole

- Ogni skill dichiara la licenza; senza licenza non entra. Materiale di terzi solo se la licenza lo consente,
  con attribuzione in `SKILL.md`.
- `hasScripts: true` nell'indice segnala `scripts/` o file eseguibili: l'app lo mostra prima dell'installazione.
  Rivedi ogni script a mano prima del merge.
- Limiti per skill: 200 file, 5 MB.

## Formato di `index.json` (schema 1)

`{ schema, skills: [{ name, description, license, category, author, hasScripts, files: [{ path, size, sha256 }] }] }`.
L'app lo scarica da un commit fissato e verifica ogni file con `sha256`.
