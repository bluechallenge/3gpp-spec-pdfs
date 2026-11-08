"""Add PDF bookmarks built from a document's printed Contents pages, for PDFs
that have none (e.g. GSMA NG.114). Assumes the printed page numbers equal the
PDF page numbers ("Page N of M" footers).

Finds the Contents pages by itself: the first page within the first 15 that
reads like a contents list, and every page after it that still does. Pass a
page number to override where the contents end.

usage: add_bookmarks.py in.pdf out.pdf [last_contents_page]
Needs pypdf (pip install pypdf) and pdftotext (poppler)."""
import re
import subprocess
import sys
from pypdf import PdfWriter

src, dst = sys.argv[1], sys.argv[2]
w = PdfWriter(clone_from=src)
n_pages = len(w.pages)
line_re = re.compile(r"^\s*((?:\d+(?:\.\d+)*\.?)|(?:Annex [A-Z])|(?:[A-Z]\.\d+(?:\.\d+)*))\s+(.+?)\s{2,}(\d+)\s*$")


def page_text(first, last):
    return subprocess.run(["pdftotext", "-layout", "-f", str(first), "-l", str(last), src, "-"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def is_contents(page):
    """At least 5 entry lines, and nearly all point at later pages."""
    targets = [int(m.group(3)) for m in map(line_re.match, page_text(page, page).splitlines()) if m]
    later = [t for t in targets if page < t <= n_pages]
    return len(targets) >= 5 and len(later) >= 0.8 * len(targets)


if len(sys.argv) > 3:
    first, last = 1, int(sys.argv[3])
else:
    first = next((p for p in range(1, min(15, n_pages) + 1) if is_contents(p)), None)
    if first is None:
        sys.exit("no contents pages found in the first 15 pages; pass the last contents page as a third argument")
    last = first
    while last < n_pages and is_contents(last + 1):
        last += 1
print(f"contents pages: {first}-{last}")
text = page_text(first, last)
parents = {}
count = 0
for line in text.splitlines():
    m = line_re.match(line)
    if not m:
        u = re.match(r"^\s*([A-Z][A-Za-z ]+?)\s{2,}(\d+)\s*$", line)  # unnumbered, e.g. "Document History"
        if u and not re.match(r"^(Version|Page)\b", u.group(1)) and 1 <= int(u.group(2)) <= n_pages:
            w.add_outline_item(u.group(1).strip(), int(u.group(2)) - 1)
            parents.clear()
            count += 1
        continue
    num, title, page = m.group(1).rstrip("."), m.group(2).strip(), int(m.group(3))
    if not 1 <= page <= n_pages:
        continue
    level = 1 if num.startswith("Annex") else num.count(".") + (1 if re.match(r"^[A-Z]\.", num) else 0) + 1
    parent = next((parents[l] for l in range(level - 1, 0, -1) if l in parents), None)
    item = w.add_outline_item(f"{num} {title}", page - 1, parent=parent)
    parents[level] = item
    for l in [k for k in parents if k > level]:
        del parents[l]
    count += 1
w.page_mode = "/UseOutlines"
w.write(dst)
print("bookmarks added:", count)
