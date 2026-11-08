"""Needs pypdf (pip install pypdf). Put the space back between section number and title in PDF bookmarks
(WPS drops the tab: '4.2Numerologies' -> '4.2 Numerologies'). usage: in.pdf out.pdf"""
import re, sys
from pypdf import PdfWriter
from pypdf.generic import NameObject, TextStringObject
w = PdfWriter(clone_from=sys.argv[1])
n = 0
def walk(node):
    global n
    while node is not None:
        node = node.get_object()
        t = str(node.get("/Title", ""))
        m = re.match(r"^(\d+(?:\.\d+)*|[A-Z](?:\.\d+)+)(?=[^\s.\d])(.*)$", t)
        if m:
            node[NameObject("/Title")] = TextStringObject(m.group(1) + " " + m.group(2)); n += 1
        if "/First" in node:
            walk(node["/First"])
        node = node.get("/Next")
root = w._root_object
if "/Outlines" in root and "/First" in root["/Outlines"].get_object():
    walk(root["/Outlines"].get_object()["/First"])
w.write(sys.argv[2]); print("titles fixed:", n)
