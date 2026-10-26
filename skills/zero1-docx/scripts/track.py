#!/usr/bin/env python3
"""Edit a .docx with tracked changes, so the author can accept or reject each edit in Word.

  python track.py IN.docx OUT.docx --author "Name" replace "old text" "new text"
  python track.py IN.docx OUT.docx --author "Name" delete "text to remove"
  python track.py IN.docx OUT.docx --author "Name" insert-after "anchor text" "text to add"

Every occurrence in the body (tables included) is changed; --first limits it to the first one. Text may span several
runs; the formatting of the first affected run is kept for inserted text. Text inside hyperlinks, headers, footers
and text boxes is not touched. Prints how many places were changed and exits 1 when nothing matched.
"""
import argparse
import copy
import datetime
import sys

from docx import Document
from docx.oxml.ns import qn
from lxml import etree

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def run_text(run):
    """Text of a run made only of w:t elements; None for runs with tabs, breaks, drawings, fields (opaque)."""
    kids = [k for k in run if k.tag != qn("w:rPr")]
    if kids and all(k.tag == qn("w:t") for k in kids):
        return "".join(k.text or "" for k in kids)
    return None


def set_text(run, text):
    for t in run.findall(qn("w:t"))[1:]:
        run.remove(t)
    t = run.find(qn("w:t"))
    t.text = text
    t.set(XML_SPACE, "preserve")


def split_run(run, offset):
    """Split a text run at `offset`; returns the run that starts at the split (the second half)."""
    text = run_text(run)
    if offset <= 0 or offset >= len(text):
        return run
    second = copy.deepcopy(run)
    set_text(run, text[:offset])
    set_text(second, text[offset:])
    run.addnext(second)
    return second


class Tracker:
    def __init__(self, doc, author):
        self.body = doc.element.body
        self.author = author
        self.date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ids = [int(e.get(qn("w:id"))) for e in doc.element.xpath("//w:ins | //w:del") if (e.get(qn("w:id")) or "").isdigit()]
        self.next_id = max(ids, default=0) + 1
        self.done = set()  # runs already used as an insert-after anchor: not matched again

    def _mark(self, tag):
        el = etree.SubElement(etree.Element("dummy"), qn(tag))
        el.set(qn("w:id"), str(self.next_id))
        el.set(qn("w:author"), self.author)
        el.set(qn("w:date"), self.date)
        self.next_id += 1
        return el

    def _new_run(self, template, text):
        run = etree.Element(qn("w:r"))
        rpr = template.find(qn("w:rPr")) if template is not None else None
        if rpr is not None:
            run.append(copy.deepcopy(rpr))
        t = etree.SubElement(run, qn("w:t"))
        t.text = text
        t.set(XML_SPACE, "preserve")
        return run

    def apply(self, mode, old, new, first_only):
        count = 0
        for p in list(self.body.iter(qn("w:p"))):
            while True:
                if not self._one(p, mode, old, new):
                    break
                count += 1
                if first_only:
                    return count
        return count

    def _map(self, p):
        """Paragraph text and, per character, the run that holds it. Direct runs only (not inside w:ins, w:del or
        w:hyperlink); runs that are not plain text, or are already done, count as one opaque character."""
        text, owners = "", []
        for r in (r for r in p if r.tag == qn("w:r")):
            t = None if r in self.done else run_text(r)
            piece = t if t is not None else "￼"
            text += piece
            owners.extend([r] * len(piece))
        return text, owners

    def _one(self, p, mode, old, new):
        text, owners = self._map(p)
        start = text.find(old)
        if start < 0 or "￼" in old:
            return False
        end = start + len(old)
        # cut runs at both ends of the match
        first = owners[start]
        offset = start - owners.index(first)
        split_run(first, offset)
        text, owners = self._map(p)
        last = owners[end - 1]
        split_run(last, end - owners.index(last))
        text, owners = self._map(p)
        matched = list(dict.fromkeys(owners[start:end]))
        if not matched:
            return False
        template = matched[0]
        anchor = matched[-1]
        if mode in ("replace", "delete"):
            deletion = self._mark("w:del")
            matched[0].addprevious(deletion)
            for r in matched:
                for t in r.findall(qn("w:t")):
                    t.tag = qn("w:delText")
                    t.set(XML_SPACE, "preserve")
                deletion.append(r)
            anchor = deletion
        if mode in ("replace", "insert-after"):
            insertion = self._mark("w:ins")
            insertion.append(self._new_run(template, new))
            anchor.addnext(insertion)
        if mode == "insert-after":
            self.done.update(matched)
        return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--author", required=True)
    ap.add_argument("--first", action="store_true", help="change only the first occurrence")
    ap.add_argument("mode", choices=["replace", "delete", "insert-after"])
    ap.add_argument("text")
    ap.add_argument("new", nargs="?", default="")
    args = ap.parse_args()
    if args.mode != "delete" and not args.new:
        ap.error(f"{args.mode} needs the new text")
    doc = Document(args.src)
    n = Tracker(doc, args.author).apply(args.mode, args.text, args.new, args.first)
    doc.save(args.dst)
    print(f"{n} tracked change(s) written to {args.dst}")
    sys.exit(0 if n else 1)


if __name__ == "__main__":
    main()
