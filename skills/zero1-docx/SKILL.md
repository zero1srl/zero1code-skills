---
name: zero1-docx
description: >
  Create, read and edit Word documents (.docx): reports, letters, contracts, memos, offers, minutes, templates.
  Use when the user asks for a Word file, "documento Word", "relazione", "lettera", "contratto", "verbale", or hands
  over a .docx to review, fill in, correct or annotate (comments, tracked changes). Covers headings and styles,
  tables, images, headers/footers with page numbers, table of contents, hyperlinks, A4 and landscape pages.
  Not for PDFs, Google Docs, spreadsheets or slides.
license: MIT
metadata:
  category: Office
  author: zero1code
---

# Word documents (.docx) with python-docx

Work in Python with `python-docx` (>= 1.2). Reply in the user's language; write the document in the language they
asked for (Italian by default for Italian users: A4, `it-IT`, decimal comma in numbers shown to people).

## 0. Check the tools first

```bash
python -c "import docx; print(docx.__version__ if hasattr(docx,'__version__') else 'ok')"   # else: pip install python-docx lxml
```

Optional: LibreOffice (`soffice`) to render pages for a visual check, and `pip install pypdfium2 pillow` for PNGs.
Without them, rely on `scripts/describe.py --check` and say that the layout was not rendered.

Scripts live next to this file (`scripts/`):

| Script | Use |
|---|---|
| `describe.py FILE [--check]` | what is in the file; `--check` lists unfinished-looking problems (exit 1 if any) |
| `helpers.py` | functions for what python-docx lacks: `a4`, `landscape`, `set_base_font`, `set_language`, `add_table`, `add_image`, `add_hyperlink`, `add_toc`, `add_page_number_footer`, `add_field`, `shade_cell`, `repeat_header`, `update_fields_on_open`, `page_break` |
| `track.py IN OUT --author N replace\|delete\|insert-after ...` | edits as tracked changes |
| `render.py FILE [--pages 1,2] [--montage]` | PDF + PNG pages through LibreOffice |

## 1. Decide: new document or existing one

- **Existing file to modify**: open it, change it in place, save under a new name. Never rebuild it from scratch: that
  loses styles, headers, numbering and anything python-docx does not model. Keep the original untouched.
- **New file**: start from `Document()` (or from the user's template `.docx`/`.dotx` if they give one: open it and
  fill it, so the corporate styles come along).
- **Review/correction by someone else's hand**: use comments and tracked changes (section 5), not silent edits.

## 2. Build a new document

```python
import sys
sys.path.insert(0, "<folder of this skill>/scripts")
from docx import Document
from docx.shared import Pt, Mm
from helpers import *

doc = Document()
a4(doc, margin_mm=25)                  # python-docx starts as US Letter
set_base_font(doc, "Calibri", 11)
set_language(doc, "it-IT")

doc.add_heading("Titolo del documento", level=0)     # Title style
doc.add_heading("1. Introduzione", level=1)
doc.add_paragraph("Testo normale. ")                  # style 'Normal'
doc.add_paragraph("Primo punto", style="List Bullet")
doc.add_paragraph("Passo uno", style="List Number")

add_table(doc, ["Voce", "Quantità", "Importo"],
          [["Licenza", "2", "120,00"], ["Supporto", "1", "80,00"]],
          widths_mm=[90, 30, 40], align_right=[1, 2])
add_image(doc, "grafico.png", width_mm=120, alt="Andamento mensile dei ricavi")
add_page_number_footer(doc.sections[0])               # "Pagina X di Y"
doc.save("relazione.docx")
```

Rules that make the result look professional:

1. **Use styles, not manual formatting.** Headings with `add_heading` (so the outline, navigation pane and TOC work),
   lists with `List Bullet` / `List Number`, body text with `Normal`. To change the look, change the style
   (`doc.styles["Heading 1"].font...`), not every run.
2. **No blank paragraphs for spacing.** Set `paragraph_format.space_after`/`space_before`, or `page_break_before` on
   a heading. Use `page_break(doc)` only for a real break.
3. **One font family**, body 10.5-12 pt, headings in the same family. Sizes in `Pt`, lengths in `Mm`.
4. **Tables**: header row bold, shaded and repeating (`add_table` does it), numbers right-aligned, widths set, no
   merged cells unless needed. A table that does not fit portrait width: reduce columns or use a landscape section.
5. **Images** always with alt text, width at most the text width (A4 with 25 mm margins = 160 mm).
6. **Table of contents** only if the document has 3+ headings levels or many pages:
   `add_toc(doc)` then `update_fields_on_open(doc)` (Word asks once to update fields) and tell the user that the TOC
   fills in when the fields are updated. Do not type a fake TOC by hand.
7. **Landscape for one wide table**: `doc.add_section()` then `landscape(doc.sections[-1])`, and back with another
   section.
8. **Hyperlinks** with `add_hyperlink(paragraph, url, text)`; show readable text, not the raw URL, unless the
   URL itself matters.
9. **Numbers and dates** formatted for the reader (`1.234,50 €`, `26 ottobre 2026`), consistently.
10. **Footnotes are not supported by python-docx.** Prefer parenthetical notes or a "Note" section; do not fake
    superscripts.

Fill-in templates: put markers such as `{{cliente}}` in the template, then replace them run-safe (a marker can be
split across runs; join the paragraph's run texts, replace, and put the result in the first run, clearing the
others) so the formatting of the marker is kept. `describe.py --check` fails while any `{{...}}` remains.

## 3. Read or analyse a document

```python
doc = Document("in.docx")
for p in doc.paragraphs: print(p.style.name, "|", p.text)
for t in doc.tables:
    for row in t.rows: print([c.text for c in row.cells])
```

`python scripts/describe.py in.docx` gives the outline, tables, images, headers/footers, comments and tracked
changes in one go. Text in tracked deletions is not in `p.text`; tracked insertions inside `w:ins` are also not
returned by `p.text` (python-docx skips them): read the XML or accept all changes first when the exact text matters.
For `.doc` (old binary) convert first: `soffice --headless --convert-to docx file.doc`.

## 4. Edit an existing document

- Change text **inside runs** (`run.text = ...`) to keep formatting; setting `paragraph.text` resets the run
  formatting of that paragraph.
- Insert a paragraph after another: build it with `doc.add_paragraph(...)`, then move its XML:
  `target._p.addnext(new._p)`.
- Delete a paragraph: `p._p.getparent().remove(p._p)`.
- Copy a table's look: `copy.deepcopy(table._tbl)` and `addnext`.
- Images in an existing file stay put unless you remove their paragraph.
- Always diff the outline before and after (`describe.py` on both) and report what changed.

## 5. Comments and tracked changes

```python
run = doc.paragraphs[3].runs[0]
doc.add_comment(runs=[run], text="Verificare l'importo.", author="Nome Cognome", initials="NC")
```

Tracked edits, one command each, so the owner can accept or reject every change in Word:

```bash
python scripts/track.py in.docx out.docx --author "Nome Cognome" replace "30 giorni" "60 giorni"
python scripts/track.py in.docx out.docx --author "Nome Cognome" delete "Il presente articolo"
python scripts/track.py in.docx out.docx --author "Nome Cognome" insert-after "Art. 4" " (rinnovo)"
```

Chain calls by feeding the output back as the next input. The script handles text split across runs and keeps the
formatting of the first affected run; it skips text inside hyperlinks, headers, footers and text boxes (it says
`0 changes` and exits 1 when nothing matched, so check the result). For legal or contractual text, make the edits
the user asked for, nothing more, and list them.

## 6. Verify before handing over

1. `python scripts/describe.py out.docx --check` must report 0 problems.
2. If LibreOffice is present: `python scripts/render.py out.docx --montage`, then look at the PNGs: clipped tables,
   orphan headings at page bottom, images off the margin, wrong page orientation. Fix and render again.
3. Re-open the saved file with `Document(path)` to make sure it loads.
4. Tell the user what you could not check (e.g. "non ho potuto generare l'anteprima: LibreOffice non installato";
   TOC and page numbers update when the file is opened in Word).

## Known limits

python-docx cannot create footnotes/endnotes, content controls, equations, SmartArt or charts. A chart goes in as an
image (build it with matplotlib, `dpi=200`, then `add_image`). Fields (TOC, page counts) show placeholders until
Word or LibreOffice updates them. `.docm` macros are dropped on save: do not round-trip macro-enabled files.
