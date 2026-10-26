#!/usr/bin/env python3
"""Recalculate an .xlsx with LibreOffice and report formula errors.

  python recalc.py FILE.xlsx [--inplace] [--timeout 180]

openpyxl writes formulas without results, so nothing in the file proves they work. This opens the workbook in
headless LibreOffice, lets it compute every formula, saves a recalculated copy (FILE-recalc.xlsx, or FILE.xlsx with
--inplace) and prints every cell that shows an error (#REF!, #DIV/0!, #NAME? ...). Exit code 1 when there are errors.
LibreOffice may rewrite some styling when it saves: keep the original and hand over the openpyxl file unless the
cached values are needed (previews, pandas data_only reads); then deliver the recalculated copy after checking it.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from describe import cached_report
from render import find_soffice


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path)
    ap.add_argument("--inplace", action="store_true", help="replace FILE with the recalculated copy")
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()
    soffice = find_soffice()
    if soffice is None:
        sys.exit("LibreOffice (soffice) not found, so formulas cannot be computed here. Excel computes them when the "
                 "file is opened (set wb.calculation.fullCalcOnLoad = True); say that they were not verified.")
    work = Path(tempfile.mkdtemp(prefix="recalc-"))
    profile = Path(tempfile.mkdtemp(prefix="lo-profile-"))
    cmd = [soffice, f"-env:UserInstallation={profile.as_uri()}", "--headless", "--convert-to",
           "xlsx:Calc MS Excel 2007 XML", "--outdir", str(work), str(args.file.resolve())]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
    produced = work / (args.file.stem + ".xlsx")
    shutil.rmtree(profile, ignore_errors=True)
    if not produced.exists():
        sys.exit(f"recalculation failed: {result.stderr or result.stdout}")
    report = cached_report(produced)
    target = args.file if args.inplace else args.file.with_name(args.file.stem + "-recalc.xlsx")
    shutil.copyfile(produced, target)
    print(f"recalculated copy: {target}")
    print(f"formulas: {report['formulas']}, computed: {report['cached']}, errors: {len(report['errors'])}")
    for sheet, cell, value, formula in report["errors"][:50]:
        print(f"  {sheet}!{cell} = {value}  {formula}")
    sys.exit(1 if report["errors"] else 0)


if __name__ == "__main__":
    main()
