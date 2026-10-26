#!/usr/bin/env python3
"""Render an Office file to PDF (LibreOffice) and PNG pages (pypdfium2) so the layout can be checked by eye.

  python render.py FILE [--out DIR] [--dpi 80] [--pages 1,3] [--montage]

Needs LibreOffice (soffice) for the PDF and `pip install pypdfium2 pillow` for the PNGs.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SOFFICE_PATHS = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
)


def find_soffice():
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    return next((p for p in SOFFICE_PATHS if Path(p).exists()), None)


def to_pdf(src: Path, outdir: Path) -> Path:
    soffice = find_soffice()
    if soffice is None:
        sys.exit("LibreOffice (soffice) not found: install it to render, or open the file in Office to check it.")
    profile = Path(tempfile.mkdtemp(prefix="lo-profile-"))  # private profile: no clash with a running LibreOffice
    cmd = [soffice, f"-env:UserInstallation={profile.as_uri()}", "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(src)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    pdf = outdir / (src.stem + ".pdf")
    shutil.rmtree(profile, ignore_errors=True)
    if not pdf.exists():
        sys.exit(f"conversion failed: {result.stderr or result.stdout}")
    return pdf


def to_pngs(pdf: Path, outdir: Path, dpi: int, pages: set) -> list:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        sys.exit(f"PDF written to {pdf}; run `pip install pypdfium2 pillow` to get PNG pages as well.")
    document = pdfium.PdfDocument(str(pdf))
    out = []
    for index in range(len(document)):
        if pages and index + 1 not in pages:
            continue
        path = outdir / f"{pdf.stem}-{index + 1:02d}.png"
        document[index].render(scale=dpi / 72).to_pil().save(path)
        out.append(path)
    return out


def montage(images: list, outdir: Path, name: str) -> Path:
    from PIL import Image
    tiles = [Image.open(p) for p in images]
    cols = 3 if len(tiles) > 4 else 2 if len(tiles) > 1 else 1
    w, h = max(t.width for t in tiles), max(t.height for t in tiles)
    rows = -(-len(tiles) // cols)
    sheet = Image.new("RGB", (cols * w, rows * h), "white")
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * w, (i // cols) * h))
    path = outdir / f"{name}-montage.png"
    sheet.save(path)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path)
    ap.add_argument("--out", type=Path, default=None, help="output folder (default: next to the file, in <name>-render)")
    ap.add_argument("--dpi", type=int, default=80)
    ap.add_argument("--pages", default="", help="comma-separated 1-based pages (default: all)")
    ap.add_argument("--montage", action="store_true", help="also write one contact sheet with all pages")
    args = ap.parse_args()
    out = args.out or args.file.with_name(args.file.stem + "-render")
    out.mkdir(parents=True, exist_ok=True)
    pdf = to_pdf(args.file.resolve(), out)
    pages = {int(p) for p in args.pages.split(",") if p.strip()}
    images = to_pngs(pdf, out, args.dpi, pages)
    print(f"pdf: {pdf}")
    for image in images:
        print(f"png: {image}")
    if args.montage and images:
        print(f"montage: {montage(images, out, args.file.stem)}")


if __name__ == "__main__":
    main()
