#!/usr/bin/env python3
"""Describe an .xlsx/.xlsm and, with --check, list problems in it.

  python describe.py FILE.xlsx [--check]

Per sheet: size, formulas, cached errors, merged ranges, tables, charts, images, freeze panes, filters, validations,
conditional formats. --check exits with 1 on error values, formulas pointing at missing sheets or #REF!, and numbers
stored as text. Formulas written by openpyxl have no cached result until Excel or LibreOffice opens the file
(recalc.py does that); that is reported as a note, not as a problem.
"""
import argparse
import re
import sys
import zipfile

import openpyxl

ERRORS = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!", "#SPILL!", "#CALC!"}
NUMBER_TEXT = re.compile(r"^\s*-?\d{1,3}([.,]\d{3})*([.,]\d+)?\s*$|^\s*-?\d+([.,]\d+)?\s*$")
SHEET_REF = re.compile(r"(?:'([^']+)'|([A-Za-z_][\w.]*))!")


def cached_report(path):
    """Cached-value facts used by describe and recalc: error cells and how many formulas have a cached result."""
    formulas = openpyxl.load_workbook(path)
    values = openpyxl.load_workbook(path, data_only=True)
    errors, total, cached = [], 0, 0
    for ws in formulas.worksheets:
        vs = values[ws.title]
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    total += 1
                    v = vs[cell.coordinate].value
                    if v is not None:
                        cached += 1
                    if isinstance(v, str) and v in ERRORS:
                        errors.append((ws.title, cell.coordinate, v, str(cell.value)[:60]))
                elif isinstance(cell.value, str) and cell.value in ERRORS:
                    errors.append((ws.title, cell.coordinate, cell.value, ""))
    return {"formulas": total, "cached": cached, "errors": errors}


# Parts openpyxl cannot read back: saving the workbook with openpyxl silently drops them.
LOST_ON_SAVE = {
    "charts": "xl/charts/chart", "pivot tables": "xl/pivotTables/", "slicers": "xl/slicers/",
    "macros (use keep_vba=True)": "xl/vbaProject.bin", "external links": "xl/externalLinks/",
}


def risky_parts(path):
    """Counts of the parts in LOST_ON_SAVE present in the file."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    return {label: sum(1 for n in names if n.startswith(prefix)) for label, prefix in LOST_ON_SAVE.items()
            if any(n.startswith(prefix) for n in names)}


def describe(path):
    wb = openpyxl.load_workbook(path)
    risky = risky_parts(path)
    if risky:
        print("== WARNING: this file contains", ", ".join(f"{n} {k}" for k, n in risky.items()),
              "- openpyxl does not read them back, so loading and saving it here would drop them (edit another way)")
    print(f"== workbook: {len(wb.sheetnames)} sheet(s): {', '.join(wb.sheetnames)}")
    names = list(wb.defined_names.keys()) if hasattr(wb.defined_names, "keys") else []
    if names:
        print("   defined names:", ", ".join(names[:12]))
    for ws in wb.worksheets:
        formulas = sum(1 for row in ws.iter_rows() for c in row if c.data_type == "f")
        flags = [
            f"freeze={ws.freeze_panes}" if ws.freeze_panes else "no freeze panes",
            f"filter={ws.auto_filter.ref}" if ws.auto_filter and ws.auto_filter.ref else "no filter",
        ]
        print(f"== sheet {ws.title!r} ({ws.sheet_state}): {ws.dimensions}, {ws.max_row} rows x {ws.max_column} cols, "
              f"{formulas} formulas")
        print(f"   merged={len(ws.merged_cells.ranges)} tables={list(ws.tables.keys())} charts={len(ws._charts)} "
              f"images={len(ws._images)} validations={len(ws.data_validations.dataValidation)} "
              f"conditional={len(ws.conditional_formatting)} {' '.join(flags)}")
        head = [str(c.value)[:14] for c in next(ws.iter_rows(min_row=1, max_row=1), []) if c.value is not None]
        if head:
            print("   row 1:", " | ".join(head[:10]))
    report = cached_report(path)
    print(f"== formulas: {report['formulas']}, with a cached result: {report['cached']}")
    if report["formulas"] and not report["cached"]:
        print("   note: no cached results yet; Excel computes them on open, or run recalc.py to compute and check them")
    for sheet, cell, value, formula in report["errors"][:20]:
        print(f"   ERROR {sheet}!{cell} = {value} {formula}")


def check(path):
    wb = openpyxl.load_workbook(path)
    problems = []
    report = cached_report(path)
    for sheet, cell, value, formula in report["errors"]:
        problems.append(f"{sheet}!{cell} shows {value} {formula}".strip())
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.data_type == "f" and isinstance(c.value, str):
                    if "#REF!" in c.value:
                        problems.append(f"{ws.title}!{c.coordinate} formula contains #REF!")
                    for quoted, bare in SHEET_REF.findall(re.sub(r'"[^"]*"', "", c.value)):  # ignore string literals
                        name = quoted or bare
                        if name not in wb.sheetnames and not name.startswith("["):
                            problems.append(f"{ws.title}!{c.coordinate} refers to a sheet that does not exist: {name!r}")
                elif c.data_type == "s" and isinstance(c.value, str) and c.row > 1 and NUMBER_TEXT.match(c.value):
                    problems.append(f"{ws.title}!{c.coordinate} is text that looks like a number: {c.value!r}")
    return problems[:100]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    describe(args.file)
    if args.check:
        problems = check(args.file)
        print(f"== check: {len(problems)} problem(s)")
        for line in problems:
            print("  -", line)
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
