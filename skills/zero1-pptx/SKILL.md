---
name: zero1-pptx
description: >
  Create, read and edit PowerPoint presentations (.pptx, .potx): sales decks, project updates, training, pitch,
  reports turned into slides, templates to fill in. Use when the user asks for a presentation, "slide",
  "presentazione", "deck", "PowerPoint", or hands over a .pptx to modify, translate, restyle, update numbers or fill
  from a template. Builds 16:9 slides with real titles, native editable charts and tables, fitted pictures with
  alt text, and speaker notes. Not for Word, Excel, PDF or Google Slides links.
license: MIT
metadata:
  category: Office
  author: zero1code
---

# PowerPoint decks with python-pptx

Reply in the user's language and write the slides in the language they asked for.

## 0. Check the tools

```bash
python -c "import pptx; print(pptx.__version__)"        # else: pip install python-pptx pillow
```

LibreOffice (`soffice`) and `pip install pypdfium2` let you look at the slides (`render.py`); without them say that the
layout was checked only by script.

| Script | Use |
|---|---|
| `describe.py FILE [--check]` | per-slide shapes, titles, notes; `--check` fails on missing titles, empty placeholders, shapes off the slide, probable text overflow, text < 12 pt, pictures without alt text, > 120 words, repeated titles |
| `replace_text.py IN OUT --set "{{x}}=Y"` | fill markers everywhere (slides, tables, groups, notes) keeping formatting, also when a marker is split across runs |
| `helpers.py` | `new_deck`, `set_title`, `add_bullets`, `add_textbox`, `estimate_font_size`, `add_picture_fit`, `add_table`, `add_bar_chart`, `set_notes`, `duplicate_slide`, `delete_slide`, `move_slide` |
| `render.py FILE --montage` | PDF + PNG of every slide + a contact sheet |

## 1. Plan before you build

1. Who is the audience and what must they remember or decide? Write the one-sentence message of the deck.
2. Outline one **idea per slide** and give each slide an **assertion title** ("I ricavi crescono del 12% nel Q3", not
   "Ricavi"). Typical shape: title, context/problem, 3-5 content slides, recommendation or next steps. A 10-minute
   talk is about 8-10 slides.
3. Move detail to the speaker notes; the slide holds what is read at a glance: at most ~6 short bullets or ~40-70
   words, and never more than 120 words.
4. If the user supplies a template or an existing deck, **use it**: its layouts, fonts and colours are the brand.

## 2. Build with a template or the default

```python
import sys
sys.path.insert(0, "<folder of this skill>/scripts")
from helpers import *

prs = new_deck()                      # default template made 16:9 properly; new_deck("brand.potx") to use a template
# print([l.name for l in prs.slide_layouts])   # always look at the layouts a template really offers

s = prs.slides.add_slide(prs.slide_layouts[0])          # Title Slide
s.shapes.title.text = "Andamento Q3"
s.placeholders[1].text = "Riunione di direzione, 26 ottobre 2026"

s = prs.slides.add_slide(prs.slide_layouts[1])          # Title and Content
set_title(s, "I ricavi crescono del 12% sul trimestre")
add_bullets(s, ["Nuovi clienti: +18", ("di cui 6 enterprise", 1), "Churn stabile al 2%"], size_pt=24)
set_notes(s, "Ricordare che il Q2 aveva stagionalità sfavorevole.")

s = prs.slides.add_slide(prs.slide_layouts[5])          # Title Only
set_title(s, "Ricavi per trimestre")
add_bar_chart(s, ["Q1", "Q2", "Q3"], {"2026": [10.2, 11.1, 12.4]}, 0.8, 1.7, 7.2, 4.8, title="Ricavi (M€)")
add_picture_fit(s, "logo.png", 8.6, 1.7, 4, 4.8, alt="Logo del cliente")

prs.save("andamento-q3.pptx")
```

Rules:

- **Always use layouts and placeholders** for titles and body so outline view, accessibility and later restyling work;
  add free text boxes only for extra elements. Never draw a title as a plain text box.
- **Sizes**: body 18-28 pt (never below 14 on a slide that will be projected), titles 28-40 pt, footers/sources 10-12 pt.
  A 16:9 slide is 13.33 x 7.5 in; keep 0.6-0.7 in margins; align edges to the same few x/y positions on every slide.
- **Colour and type**: one or two font families, two or three colours plus neutrals, text/background contrast of at
  least 4.5:1, no coloured text on busy pictures. Take colours from the template theme where there is one.
- **Charts**: native (`add_bar_chart`, or `XL_CHART_TYPE.LINE`/`PIE` through the `kind` argument) so the user can edit
  the data; always a title or a slide title that states the message, labelled units, no 3D, one series highlighted if
  there are many. Do not paste a chart as a picture unless the chart type is not supported.
- **Tables**: at most about 6 rows x 5 columns at >= 14 pt, numbers right-aligned, header row coloured. More data goes
  to an appendix or an attached workbook.
- **Pictures**: `add_picture_fit` keeps the aspect ratio and sets alt text; no stretched or pixelated images.
- **Text that does not fit**: shorten it or split the slide. Do not shrink below 18 pt for body text.
  `estimate_font_size(text, width_in, height_in)` gives a starting size for text boxes; the check and the render
  decide.
- **No walls of text, no clip-art, no more than one animation idea**: python-pptx cannot create animations or
  transitions, so do not promise them.

## 3. Fill a template

Put markers such as `{{cliente}}`, `{{periodo}}` in the template (or find the existing placeholders with
`describe.py`), then:

```bash
python scripts/replace_text.py template.pptx out.pptx --set "{{cliente}}=ACME S.p.A." --set "{{periodo}}=Q3 2026"
```

It exits 1 if a marker was not found: investigate (it may be inside a picture, a chart or SmartArt, which text
replacement cannot reach).

## 4. Edit an existing deck

- Read first: `python scripts/describe.py in.pptx`, then change only what was asked. Save under a new name.
- Change text **in runs** (`run.text = ...`) to keep the formatting; `text_frame.text = ...` resets it.
- New slide like an existing one: `duplicate_slide(prs, index)` (pictures and links come along; a copied chart shares its
  data with the original, so rebuild the chart instead of editing both). Remove: `delete_slide(prs, index)`.
  Reorder: `move_slide(prs, old, new)`.
- Update chart data: `chart.replace_data(CategoryChartData(...))` on the existing chart object keeps its formatting.
- Updating numbers across slides: change every occurrence (titles, bullets, tables, charts, notes) and list them.
- Translation: replace paragraph by paragraph keeping runs; long translations can overflow, so run the check.

## 5. Verify before handing over

1. `python scripts/describe.py out.pptx --check` must report 0 problems.
2. If LibreOffice is present, `python scripts/render.py out.pptx --montage` and look at the PNGs: overflow, clipped
   tables, overlapping shapes, unreadable contrast, empty areas. Fix and render again (at least once).
3. Re-open the file with `Presentation(path)`.
4. Tell the user: number of slides, what each carries, where the notes are, anything not verified (fonts that the
   viewer's PC may lack; no render when LibreOffice is missing).

## Known limits

python-pptx cannot create animations, transitions, SmartArt, embedded video controls or morph effects; it keeps
animation XML on slides you do not duplicate but a duplicated slide loses links to timing. It does not render text,
so overflow is estimated by script and confirmed by `render.py`. Fonts are referenced by name: use fonts common to
Windows and Mac (Calibri, Arial) unless the template brings its own.
