"""Needs: pip install python-docx lxml. Run: python -m unittest discover -s tests"""
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "zero1-docx" / "scripts"
# each skill has its own helpers.py: load by path under a unique name so the three test modules do not clash
_spec = importlib.util.spec_from_file_location("zero1_docx_helpers", SCRIPTS / "helpers.py")
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)


def run(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True)


def texts(paragraph, accepted):
    out = []
    for el in paragraph._p.iter(qn("w:t"), qn("w:delText")):
        in_ins = any(a.tag == qn("w:ins") for a in el.iterancestors())
        in_del = any(a.tag == qn("w:del") for a in el.iterancestors())
        if (accepted and not in_del) or (not accepted and not in_ins):
            out.append(el.text or "")
    return "".join(out)


def add_field(paragraph, instruction, placeholder="1"):
    def mark(kind):
        r = paragraph.add_run()
        c = OxmlElement("w:fldChar")
        c.set(qn("w:fldCharType"), kind)
        r._r.append(c)
    mark("begin")
    r = paragraph.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instruction} "
    r._r.append(it)
    mark("separate")
    paragraph.add_run(placeholder)
    mark("end")


class DocxScripts(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_helpers_build_a_document_that_passes_the_check(self):
        doc = Document()
        h.a4(doc)
        h.set_base_font(doc, "Calibri", 11)
        h.set_language(doc, "it-IT")
        doc.add_heading("Relazione", 1)
        h.add_toc(doc)
        h.update_fields_on_open(doc)
        doc.add_heading("Dati", 2)
        h.add_table(doc, ["Voce", "Importo"], [["A", "10,00"], ["B", "20,00"]], widths_mm=[100, 40], align_right=[1])
        p = doc.add_paragraph("Vedi ")
        h.add_hyperlink(p, "https://example.com", "il sito")
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), "green").save(buf, "PNG")
        buf.seek(0)
        img = self.tmp / "g.png"
        img.write_bytes(buf.getvalue())
        h.add_image(doc, img, 30, "quadrato verde")
        h.add_page_number_footer(doc.sections[0])
        h.page_break(doc)
        doc.add_section()
        h.landscape(doc.sections[-1])
        path = self.tmp / "h.docx"
        doc.save(path)
        again = Document(path)
        self.assertEqual(round(again.sections[0].page_width.mm), 210)
        self.assertGreater(again.sections[-1].page_width, again.sections[-1].page_height)
        self.assertTrue(again.element.xpath("//w:hyperlink"))
        self.assertTrue(again.settings.element.xpath("//w:updateFields"))
        self.assertTrue(again.styles.element.xpath("//w:lang[@w:val='it-IT']"))
        r = run("describe.py", path, "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("TOC", r.stdout)
        self.assertIn("NUMPAGES", r.stdout)

    def test_describe_check_passes_on_a_clean_document_and_flags_a_bad_one(self):
        doc = Document()
        s = doc.sections[0]
        s.page_width, s.page_height = Mm(210), Mm(297)
        doc.add_heading("Titolo", 1)
        doc.add_heading("Sezione", 2)
        add_field(doc.sections[0].footer.paragraphs[0], "PAGE")
        t = doc.add_table(rows=2, cols=2)
        t.style = "Table Grid"
        trpr = t.rows[0]._tr.get_or_add_trPr()
        h = OxmlElement("w:tblHeader")
        h.set(qn("w:val"), "true")
        trpr.append(h)
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), "blue").save(buf, "PNG")
        buf.seek(0)
        pic = doc.add_paragraph().add_run().add_picture(buf, width=Mm(20))
        pic._inline.docPr.set("descr", "quadrato blu")
        doc.add_comment(runs=[doc.paragraphs[0].runs[0]], text="rivedere", author="Ann", initials="A")
        good = self.tmp / "good.docx"
        doc.save(good)
        r = run("describe.py", good, "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Ann: rivedere", r.stdout)
        self.assertIn("PAGE", r.stdout)

        bad = Document()
        bad.add_heading("T", 1)
        bad.add_heading("Salto", 3)
        bad.add_paragraph("Testo {{nome}} da compilare")
        bad.add_table(rows=1, cols=1)
        path = self.tmp / "bad.docx"
        bad.save(path)
        r = run("describe.py", path, "--check")
        self.assertEqual(r.returncode, 1)
        for needle in ("jumps from H1 to H3", "placeholder", "repeating header"):
            self.assertIn(needle, r.stdout)

    def test_track_replace_across_runs_keeps_both_versions(self):
        doc = Document()
        p = doc.add_paragraph()
        p.add_run("Hello ").bold = True
        p.add_run("wonderful world, hello again")
        src, dst = self.tmp / "in.docx", self.tmp / "out.docx"
        doc.save(src)
        r = run("track.py", src, dst, "--author", "Rev", "replace", "lo wonder", "XX")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = Document(dst)
        para = out.paragraphs[0]
        self.assertEqual(texts(para, accepted=True), "HelXXful world, hello again")
        self.assertEqual(texts(para, accepted=False), "Hello wonderful world, hello again")
        self.assertEqual(len(out.element.xpath("//w:ins[@w:author='Rev']")), 1)
        self.assertEqual(len(out.element.xpath("//w:del[@w:author='Rev']")), 1)
        # the inserted run keeps the bold of the first replaced run
        self.assertTrue(out.element.xpath("//w:ins/w:r/w:rPr/w:b"))

    def test_track_delete_insert_all_occurrences_and_no_match(self):
        doc = Document()
        doc.add_paragraph("cat and cat")
        src = self.tmp / "in.docx"
        doc.save(src)
        dst = self.tmp / "o1.docx"
        self.assertEqual(run("track.py", src, dst, "--author", "A", "delete", "cat").returncode, 0)
        self.assertEqual(texts(Document(dst).paragraphs[0], True), " and ")
        dst2 = self.tmp / "o2.docx"
        self.assertEqual(run("track.py", src, dst2, "--author", "A", "insert-after", "and", "!").returncode, 0)
        self.assertEqual(texts(Document(dst2).paragraphs[0], True), "cat and! cat")
        self.assertEqual(run("track.py", src, self.tmp / "o3.docx", "--author", "A", "replace", "dog", "x").returncode, 1)

    def test_render_without_libreoffice_fails_with_a_clear_message(self):
        r = run("render.py", self.tmp / "missing.docx")
        if r.returncode == 0:
            self.skipTest("LibreOffice present")
        self.assertIn("LibreOffice", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
