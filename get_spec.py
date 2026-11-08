"""Fetch the newest version of 3GPP specs as good PDFs.

First choice is ETSI's official PDF (ETSI republishes every 3GPP spec as a
PDF made from the Word original: TS 38.211 -> ETSI TS 138 211). If ETSI has
no copy, or 3GPP already has a newer version, the 3GPP .docx goes into the
folder's Word/ subfolder instead: open it in WPS Office (the app, not its
command line) or Word, save as PDF, then run fix_bookmarks.py on it.

Files land in one snapshot folder per release and quarterly 3GPP drop,
inside the destination folder:
  <dest>/Release 19 - Sep'26/38211-j50_Physical channels and modulation.pdf
Destination: --dest, else $SPEC_LIB, else ~/3GPP Specifications.

usage: python3 get_spec.py 38.211 [24.229 ...] [--dest DIR] [--release 19] [--folder NAME] [--dry-run]
Needs Python 3 (standard library only) and pdftotext from poppler
(macOS: brew install poppler; Debian/Ubuntu: apt install poppler-utils;
Windows: scoop install poppler or choco install poppler, then run with py).
"""
import argparse
import datetime
import io
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

LIB = None  # set in main() from --dest / $SPEC_LIB
UA = {"User-Agent": "3gpp-spec-pdfs/1.0 (+https://github.com/bluechallenge/3gpp-spec-pdfs)"}
PAUSE = 0.5  # seconds between requests, to go easy on etsi.org and 3gpp.org
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
# whole-part system labels ("5G", "NR", "NG-RAN") or boilerplate openings; not titles like "5G System (5GS) ..."
PREFIX = r"^((5G|NR|LTE|NG-RAN|E-UTRA|GSM|UMTS)$|Universal Mobile|Digital cellular|Evolved Universal|Technical Specification|Technical Report|3rd Generation Partnership)"


def get(url):
    time.sleep(PAUSE)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def code(dotted):
    """19.5.0 -> j50 (3GPP file-name version code)."""
    return "".join(str(int(x)) if int(x) < 10 else chr(ord("a") + int(x) - 10) for x in dotted.split("."))


def rank(c):
    return [int(ch, 36) for ch in c]


def snapshot_folder(release, today=None):
    """Latest quarterly 3GPP drop (Mar, Jun, Sep, Dec) on or before today."""
    d = today or datetime.date.today()
    m = max(x for x in (3, 6, 9, 12) if x <= d.month) if d.month >= 3 else 12
    y = d.year if d.month >= 3 else d.year - 1
    return f"Release {release} - {MONTHS[m - 1]}'{str(y)[2:]}"


def clean_title(text):
    parts = [" ".join(p.split()) for p in text.split(";") if p.strip()]
    while len(parts) > 1 and re.match(PREFIX, parts[0]):
        parts.pop(0)
    return re.sub(r"[/:\\]", "-", "; ".join(parts))


def etsi(spec, release):
    """(dotted version, pdf bytes, title) of the newest ETSI copy, or None."""
    num = "1" + spec.replace(".", "")  # 38.211 -> 138211
    kinds = ["tr", "ts"] if int(spec.split(".")[1]) >= 800 else ["ts", "tr"]  # x.8xx/x.9xx are reports
    for k in kinds:
        base = f"https://www.etsi.org/deliver/etsi_{k}/{num[:-2]}00_{num[:-2]}99/{num}/"
        try:
            html = get(base).decode("utf-8", "replace")
        except Exception:
            continue
        vers = sorted({v for v in re.findall(r"(\d\d\.\d\d\.\d\d)_60", html) if int(v[:2]) == release})
        if not vers:
            return None
        folder = base + f"{vers[-1]}_60/"
        name = re.search(r"([a-z]{2}_\d+v\d+p\.pdf)", get(folder).decode("utf-8", "replace")).group(1)
        data = get(folder + name)
        # delete=False and close before reading: Windows can't open a file that is still open
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as t:
            t.write(data)
        try:
            cover = subprocess.run(["pdftotext", "-l", "1", t.name, "-"], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace").stdout
        finally:
            os.unlink(t.name)
        block = cover[:cover.index("(3GPP")]
        title = clean_title(block.split("\n\n")[-1])
        return ".".join(str(int(x)) for x in vers[-1].split(".")), data, title
    return None


def threegpp(spec, release):
    """(version code, docx bytes, title) of the newest 3GPP version, or None."""
    series = spec.split(".")[0]
    base = f"https://www.3gpp.org/ftp/Specs/archive/{series}_series/{spec}/"
    html = get(base).decode("utf-8", "replace")
    first = code(f"{release}.0.0")[0]
    found = set(re.findall(rf"{spec.replace('.', '')}-({first}[0-9a-z]{{2}})\.zip", html))
    if not found:
        return None
    ver = max(found, key=rank)
    z = zipfile.ZipFile(io.BytesIO(get(f"{base}{spec.replace('.', '')}-{ver}.zip")))
    doc_name = next(n for n in z.namelist() if n.lower().endswith((".docx", ".doc")))
    doc = z.read(doc_name)
    title = ""
    if doc_name.lower().endswith(".docx"):
        xml = zipfile.ZipFile(io.BytesIO(doc)).read("word/document.xml").decode("utf-8", "replace")
        paras = [re.sub(r"<[^>]+>", "", p) for p in re.findall(r"<w:p[ >].*?</w:p>", xml[:400000], re.S)]
        paras = [p.strip() for p in paras if p.strip()]
        rel = next((i for i, p in enumerate(paras) if re.match(r"^\(Release \d+\)", p)), None)
        if rel is not None:
            start = max(i for i in range(rel) if re.match(r"^3GPP T[SR] ", paras[i]) or i == 0)
            title = clean_title(" ".join(paras[start + 1:rel]))
    return ver, doc, title, doc_name


def fetch(spec, release, folder, dry):
    out_dir = LIB / folder
    stem = spec.replace(".", "")
    e = etsi(spec, release)
    g = threegpp(spec, release)
    tag = " [dry run]" if dry else ""
    if e and (not g or rank(code(e[0])) >= rank(g[0])):
        dotted, data, title = e
        out = out_dir / f"{stem}-{code(dotted)}_{title}.pdf"
        if not dry:
            out_dir.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        return f"{spec}: ETSI PDF {dotted} -> {out.relative_to(LIB)}{tag}"
    if not g:
        return f"{spec}: no Release {release} version on ETSI or 3GPP"
    ver, doc, title, doc_name = g
    ext = Path(doc_name).suffix.lower()
    out = out_dir / "Word" / (f"{stem}-{ver}_{title}{ext}" if title else f"{stem}-{ver}{ext}")
    if not dry:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(doc)
    why = f"ETSI has only {e[0]}" if e else "not on ETSI"
    return (f"{spec}: {why}; 3GPP {ver} Word file -> {out.relative_to(LIB)}{tag}\n"
            f"  -> open it in the WPS app, save as PDF into '{folder}', then run fix_bookmarks.py on the PDF")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--dest", help="library folder (default: $SPEC_LIB, else ~/3GPP Specifications)")
    ap.add_argument("--release", type=int, default=19, help="release to take versions from (default 19)")
    ap.add_argument("--folder", help="library subfolder (default: Release 19 - <latest quarterly drop>)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    global LIB
    LIB = Path(a.dest or os.environ.get("SPEC_LIB") or Path.home() / "3GPP Specifications").expanduser()
    folder = a.folder or snapshot_folder(a.release)
    ok = True
    for s in a.specs:
        try:
            print(fetch(s, a.release, folder, a.dry_run))
        except Exception as ex:  # keep going with the rest
            ok = False
            print(f"{s}: failed ({ex})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
