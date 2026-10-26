#!/usr/bin/env python3
"""Describe a .docx and, with --check, list problems that make a document look unfinished.

  python describe.py FILE.docx [--check]

Prints page setup, outline, tables, images, headers/footers, comments and tracked changes. --check exits with 1
when it finds placeholders, runs of empty paragraphs, skipped heading levels, images without alt text or tables
without a repeating header row.
"""
import argparse
import re
import sys
from collections import Counter

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Emu

IMAGE_NAME = re.compile(r".(png|jpe?g|gif|bmp|tiff?|svg|emf|wmf|webp)$", re.I)  # python-docx fills alt text with the file name
PLACEHOLDER = re.compile(r"\{\{|\}\}|lorem ipsum|\bTODO\b|\bXXX\b|\bTBD\b|\[(?:nome|data|titolo|name|date|title)[^\]]*\]", re.I)


def heading_level(paragraph):
    name = paragraph.style.name if paragraph.style is not None else ""
    match = re.fullmatch(r"Heading (\d)", name) or re.fullmatch(r"Titolo (\d)", name)
    return int(match.group(1)) if match else None


def describe(doc):
    print("== page setup")
    for i, s in enumerate(doc.sections):
        w, h = Emu(s.page_width).mm, Emu(s.page_height).mm
        print(f"section {i}: {w:.0f}x{h:.0f} mm, margins L{Emu(s.left_margin).mm:.0f} R{Emu(s.right_margin).mm:.0f} "
              f"T{Emu(s.top_margin).mm:.0f} B{Emu(s.bottom_margin).mm:.0f}, "
              f"{'landscape' if s.page_width > s.page_height else 'portrait'}")
        for label, part in (("header", s.header), ("footer", s.footer)):
            text = " | ".join(p.text for p in part.paragraphs if p.text.strip())
            fields = len(part._element.xpath(".//w:instrText | .//w:fldSimple"))
            if text or fields:
                print(f"  {label}: {text!r}{f' (+{fields} field)' if fields else ''}")
    print("== outline")
    for p in doc.paragraphs:
        level = heading_level(p)
        if level is not None and p.text.strip():
            print(f"{'  ' * (level - 1)}H{level} {p.text.strip()[:90]}")
    styles = Counter(p.style.name for p in doc.paragraphs if p.text.strip())
    print("== styles in use:", ", ".join(f"{n} x{c}" for n, c in styles.most_common(8)))
    print(f"== paragraphs: {len(doc.paragraphs)}, tables: {len(doc.tables)}, images: {len(doc.inline_shapes)}")
    for i, t in enumerate(doc.tables):
        head = " | ".join(c.text.strip()[:18] for c in t.rows[0].cells) if t.rows else ""
        print(f"table {i}: {len(t.rows)}x{len(t.columns)} style={t.style.name if t.style is not None else None} first row: {head}")
    comments = list(doc.comments)
    print(f"== comments: {len(comments)}")
    for c in comments:
        print(f"  {c.author}: {c.text[:100]}")
    body = doc.element
    ins, dele = body.xpath(".//w:ins"), body.xpath(".//w:del")
    authors = Counter(e.get(qn("w:author")) for e in ins + dele)
    print(f"== tracked changes: {len(ins)} insertions, {len(dele)} deletions {dict(authors) if authors else ''}")
    instr = list(body.xpath(".//w:instrText"))
    for s in doc.sections:
        for part in (s.header, s.footer):
            instr += part._element.xpath(".//w:instrText")
    fields = [t.text.strip().split()[0] for t in instr if t.text and t.text.strip()]
    print("== fields:", dict(Counter(fields)) if fields else "none")


def check(doc):
    problems = []
    empty_run = 0
    last_level = 0
    for i, p in enumerate(doc.paragraphs):
        if not p.text.strip() and not p._p.xpath(".//w:drawing | .//w:br[@w:type='page'] | .//w:sectPr"):
            empty_run += 1
            if empty_run == 3:
                problems.append(f"paragraph {i}: 3+ empty paragraphs in a row (use spacing or a page break, not blank lines)")
        else:
            empty_run = 0
        if PLACEHOLDER.search(p.text):
            problems.append(f"paragraph {i}: placeholder text left in: {p.text.strip()[:70]!r}")
        level = heading_level(p)
        if level is not None and p.text.strip():
            if last_level and level > last_level + 1:
                problems.append(f"paragraph {i}: heading jumps from H{last_level} to H{level}: {p.text.strip()[:50]!r}")
            last_level = level
    for i, t in enumerate(doc.tables):
        if t.rows and not t.rows[0]._tr.xpath("./w:trPr/w:tblHeader"):
            problems.append(f"table {i}: first row is not marked as a repeating header")
        for row in t.rows:
            for cell in row.cells:
                if PLACEHOLDER.search(cell.text):
                    problems.append(f"table {i}: placeholder text in a cell: {cell.text.strip()[:50]!r}")
    for i, doc_pr in enumerate(doc.element.xpath(".//wp:docPr")):
        descr = (doc_pr.get("descr") or "").strip()
        if not descr or IMAGE_NAME.search(descr):
            problems.append(f"image {i}: no alt text (set docPr descr)")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = Document(args.file)
    describe(doc)
    if args.check:
        problems = check(doc)
        print(f"== check: {len(problems)} problem(s)")
        for line in problems:
            print("  -", line)
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
