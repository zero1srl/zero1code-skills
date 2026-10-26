---
name: zero1-xlsx
description: >
  Create, read, analyse and edit Excel workbooks (.xlsx, .xlsm, .csv): budgets, price lists, reports, trackers,
  financial models, data cleanup, tables with formulas, charts, validation and conditional formatting.
  Use when the user asks for an Excel/spreadsheet file, "foglio Excel", "file xlsx", "budget", "preventivo",
  "report in Excel", or gives a spreadsheet to read, fix, extend or analyse. Formulas stay live and are checked
  for errors. Not for Word or PowerPoint files, nor for Google Sheets links.
license: MIT
metadata:
  category: Office
  author: zero1code
---

# Excel workbooks with openpyxl (and pandas for analysis)

Reply in the user's language. Excel shows numbers and dates with the reader's regional settings, so Italian users see
`1.234,50`; the file itself always stores US-style formats and English function names.

## 0. Check the tools

```bash
python -c "import openpyxl, sys; print(openpyxl.__version__)"      # else: pip install openpyxl   (pandas for analysis)
```

LibreOffice (`soffice`) is needed to verify formulas (`recalc.py`) and to render a sheet to PDF. Without it, say that
the formulas were not computed here and set `wb.calculation.fullCalcOnLoad = True` so Excel recalculates on open.

| Script | Use |
|---|---|
| `describe.py FILE [--check]` | sheets, formulas, tables, charts, validations; `--check` fails on error values, `#REF!`, missing sheets, numbers stored as text |
| `recalc.py FILE [--inplace]` | computes every formula in LibreOffice, prints each error cell, saves `FILE-recalc.xlsx` |
| `helpers.py` | `write_rows`, `style_header`, `autofit_columns`, `add_table`, `mark_input`, `fit_to_page`, `thin_borders`, formats `EUR EUR0 PCT DATE INT` |
| `render.py FILE` | PDF/PNG of the sheets through LibreOffice, for a visual check |

## 1. The rules that matter most

1. **Formulas, not pasted results.** If a number can be derived from other cells, write the formula
   (`ws["D2"] = "=B2*C2"`), never `ws["D2"] = 2*10.5`. Totals, percentages, margins, growth rates: all formulas.
2. **Inputs in cells, never inside formulas.** Rates, prices, thresholds go in labelled cells (an "Ipotesi" area or
   sheet); formulas point to them (`=B2*$F$1`). Mark typed-in inputs blue (`mark_input(cell)`), keep formulas black.
3. **English function names and commas in the file**, whatever the Excel language: `=SUMIF(A:A,"x",B:B)`, not
   `SOMMA.SE(...;...)`. Functions newer than Excel 2007 need the `_xlfn.` prefix or they show `#NAME?`:
   `=_xlfn.XLOOKUP(...)`, `=_xlfn.IFS(...)`, `=_xlfn.TEXTJOIN(...)`. Prefer classic functions (`INDEX/MATCH`,
   `SUMIFS`, `IFERROR`) when the file may be opened by older Excel or LibreOffice. Avoid dynamic-array formulas
   (`FILTER`, `UNIQUE`, `SORT`, `LET`).
4. **Sheet names in formulas**: `=Dati!B2`, and with spaces `='Foglio 1'!B2`. Names are at most 31 characters and
   cannot contain `[]:*?/\`.
5. **One table per sheet region, starting at A1**, one header row, no blank rows or columns inside, no merged cells
   in data (use "Center across selection" or widen the column instead).
6. **Types**: numbers as numbers, dates as `datetime.date`/`datetime` with `number_format = DATE`, percentages as
   fractions (`0.22` with `PCT`), currency with `EUR`. Text that looks like a number is a bug (`describe.py --check`).
7. **Never leave a default empty "Sheet"**; name sheets for their content; put the summary first.

## 2. Build a new workbook

```python
import sys
sys.path.insert(0, "<folder of this skill>/scripts")
import openpyxl
from helpers import *

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Dati"
write_rows(ws, [
    ["Voce", "Quantità", "Prezzo", "Totale"],
    ["Licenza", 2, 120, "=B2*C2"],
    ["Supporto", 1, 80, "=B3*C3"],
    ["Totale", "=SUM(B2:B3)", "", "=SUM(D2:D3)"],
])
style_header(ws)                       # bold coloured header, freeze panes under it
for r in range(2, 5):
    ws.cell(row=r, column=3).number_format = EUR
    ws.cell(row=r, column=4).number_format = EUR
mark_input(ws["B2"], ws["B3"], ws["C2"], ws["C3"])
autofit_columns(ws)
fit_to_page(ws)                        # A4, one page wide, header repeated
wb.calculation.fullCalcOnLoad = True
wb.save("preventivo.xlsx")
```

Useful pieces (all supported by openpyxl; see `helpers.py` for the first):

- **Excel table** (filters, banding, structured refs): `add_table(ws, "A1", name="Dati")` (name without spaces, unique).
- **Conditional formatting**: `ws.conditional_formatting.add("D2:D50", CellIsRule(operator="greaterThan", formula=["1000"], fill=PatternFill("solid", bgColor="FFC7CE")))`.
- **Validation list**: `dv = DataValidation(type="list", formula1='"Aperto,Chiuso"', allow_blank=True); ws.add_data_validation(dv); dv.add("E2:E200")`.
- **Chart**: `BarChart()` / `LineChart()` / `PieChart()` with `Reference(ws, min_col, min_row, max_row)`, `chart.add_data(ref, titles_from_data=True)`, `chart.set_categories(...)`, a title, axis titles, `chart.width/height` (cm), then `ws.add_chart(chart, "F2")`. One message per chart; no 3D.
- **Named range**: `from openpyxl.workbook.defined_name import DefinedName; wb.defined_names["Aliquota"] = DefinedName("Aliquota", attr_text="Ipotesi!$B$1")`.
- **Column groups, hidden helper columns, protection**: only when asked; say so.
- **Big data (50k+ rows)**: `openpyxl.Workbook(write_only=True)` and `ws.append(row)`; style afterwards is not possible in
  write-only mode, so decide the look first.
- **From pandas**: `df.to_excel(writer, sheet_name="Dati", index=False)` with `pd.ExcelWriter(path, engine="openpyxl")`, then
  re-open with openpyxl for formats, table and widths.

## 3. Read and analyse

```python
import pandas as pd
df = pd.read_excel("in.xlsx", sheet_name="Dati")           # values (cached results of formulas)
wb_values = openpyxl.load_workbook("in.xlsx", data_only=True)   # cached values, cell by cell
wb_formulas = openpyxl.load_workbook("in.xlsx")                  # formulas as text
```

Cached values exist only if Excel/LibreOffice saved the file after calculating. A file written by openpyxl shows
`None` for formulas until it has been recalculated (`recalc.py`).
**Never open with `data_only=True` and then save: every formula is replaced by its last value.**

## 4. Edit an existing workbook

1. Run `python scripts/describe.py in.xlsx`. If it warns about charts, pivot tables, slicers, macros or external
   links, **do not load-and-save it with openpyxl**: those parts are dropped silently. Options: make the change
   in a copy and tell the user what would be lost, add the new content in a new workbook, or edit only with
   LibreOffice/Excel automation if available. For `.xlsm`, use `load_workbook(path, keep_vba=True)`.
2. Otherwise modify in place and save under a new name; never overwrite the user's original.
3. Inserting rows/columns with `ws.insert_rows` does **not** update formulas, tables, merged ranges or charts that
   point at the moved cells: rewrite those references yourself or avoid inserting; append at the end when possible.
4. Keep the existing style: copy `cell._style` from a neighbouring cell for new rows.

## 5. Verify before handing over

1. `python scripts/describe.py out.xlsx --check` must report 0 problems.
2. `python scripts/recalc.py out.xlsx` (needs LibreOffice) must show 0 errors. Fix every `#REF!`, `#DIV/0!` (guard
   with `IFERROR` or an `IF` on the denominator only where a zero is legitimate), `#NAME?` (spelling, `_xlfn.`) and
   `#VALUE!`. Check two or three results by hand against the inputs.
3. Optionally `python scripts/render.py out.xlsx --montage` to look at widths, wrapped headers and chart placement.
4. Deliver the openpyxl file (`out.xlsx`, formulas live) unless cached values are required; then deliver the
   `-recalc` copy after checking its formatting.
5. Tell the user: sheet names and what each contains, which cells are inputs, and anything not verified (for example
   "formule non calcolate qui: LibreOffice non installato; Excel le calcola all'apertura").

## Known limits

openpyxl cannot read charts, pivot tables or slicers from existing files, cannot evaluate formulas, and does not
render. Images need Pillow. Data validation and conditional formatting survive a round trip; threaded comments,
sparklines and Power Query connections do not.
