#!/usr/bin/env python3
"""Erzeugt aus README.md eine druckfertige PDF (A4) über Chromium im Headless-Modus.

Aufruf:  python3 scripts/build_pdf.py
Benötigt: pip install markdown · Chromium (Pfad über CHROME oder Standardpfad unten)
"""
import os
import re
import subprocess
import sys
import tempfile

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "README.md")
OUT = os.path.join(ROOT, "Cannabis-Anbau-Anleitung.pdf")
CHROME = os.environ.get("CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")


def slugify(value, separator="-"):
    """GitHub-kompatible Anker (Umlaute bleiben erhalten), damit interne Links funktionieren."""
    s = value.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", separator)


LIST_ITEM = re.compile(r"^(\s*)([-*]|\d+\.) ")


def preprocess(md_text):
    """Passt GitHub-Markdown an Python-Markdown an (Listen-Einrückung, Leerzeile vor Listen)."""
    # Aufgabenlisten "- [ ]" in Kästchen umwandeln
    md_text = re.sub(r"^(\s*)- \[ \] ", r"\1- ☐ ", md_text, flags=re.M)
    out = []
    prev = ""
    for line in md_text.split("\n"):
        m = LIST_ITEM.match(line)
        if m:
            indent = len(m.group(1))
            if indent:
                # GitHub erlaubt 2–3 Leerzeichen Einrückung, Python-Markdown braucht 4 je Ebene
                line = " " * (4 * -(-indent // 4)) + line[indent:]
            # Vor einer Liste muss eine Leerzeile stehen, wenn davor normaler Text kommt
            if prev.strip() and not LIST_ITEM.match(prev):
                out.append("")
        out.append(line)
        prev = line
    text = "\n".join(out)
    # Zahl und Einheit nicht trennen (geschütztes Leerzeichen), außer in Links
    text = re.sub(r"(?<![/\w])(\d+(?:,\d+)?) (g|ml|L|cm|mm|°C|%|kPa|W|m³|m²)(?=[\s,.;:)|/–]|$)", "\\1\u00a0\\2", text, flags=re.M)
    return text


CSS = r"""
@page {
  size: A4;
  margin: 16mm 14mm 18mm 14mm;
  @bottom-center { content: "Seite " counter(page) " von " counter(pages); font: 8pt "DejaVu Sans", sans-serif; color: #666; }
  @top-right { content: "Cannabis-Anbau für Einsteiger · Stand 28.09.2026"; font: 7.5pt "DejaVu Sans", sans-serif; color: #888; }
}
@page :first { @top-right { content: none; } }
html { font-family: "DejaVu Sans", "Liberation Sans", "Noto Color Emoji", sans-serif; font-size: 9.6pt; line-height: 1.45; color: #1d1d1d; }
body { margin: 0; }
h1 { font-size: 21pt; color: #1f5f2e; margin: 0 0 8pt; line-height: 1.2; }
h2 { font-size: 15pt; color: #1f5f2e; border-bottom: 2px solid #1f5f2e; padding-bottom: 3pt; margin: 18pt 0 8pt; break-after: avoid; }
h2.chapter { break-before: page; margin-top: 0; }
h3 { font-size: 11.5pt; color: #2d6b3a; margin: 13pt 0 5pt; break-after: avoid; }
h4 { font-size: 10pt; margin: 10pt 0 4pt; break-after: avoid; }
p { margin: 4pt 0 6pt; orphans: 3; widows: 3; }
ul, ol { margin: 3pt 0 6pt; padding-left: 16pt; }
li { margin: 1.5pt 0; }
li > ul, li > ol { margin: 1pt 0 2pt; }
blockquote { margin: 6pt 0 10pt; padding: 7pt 10pt; background: #eef6ef; border-left: 4px solid #1f5f2e; border-radius: 3px; }
blockquote p { margin: 0; }
hr { border: none; border-top: 1px solid #cfd8cf; margin: 10pt 0; }
a { color: #1a5aa6; text-decoration: none; word-break: break-word; }
strong { color: #111; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.5pt; background: #f2f2f2; padding: 0 2px; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0 9pt; font-size: 8.2pt; line-height: 1.35; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { background: #1f5f2e; color: #fff; text-align: left; font-weight: bold; padding: 3.5pt 4pt; border: 1px solid #1f5f2e; vertical-align: top; }
td { padding: 3pt 4pt; border: 1px solid #c9d3c9; vertical-align: top; }
tbody tr:nth-child(even) td { background: #f6f9f6; }
table.wide { font-size: 7.3pt; }
table.wide th, table.wide td { padding: 2.5pt 3pt; }
/* Im Zubehör-Kapitel die Adresse der Links sichtbar machen (für den Ausdruck) */
section.zubehoer td a[href^="http"]::after { content: " – " attr(href); color: #555; font-size: 6.6pt; word-break: break-all; }
.titelblock { border: 1px solid #cfe3d2; background: #f4faf5; padding: 10pt 12pt; border-radius: 5px; margin-bottom: 10pt; }
.fussnote { font-size: 8pt; color: #555; }
"""


def build_html(md_text):
    md = markdown.Markdown(
        extensions=["tables", "toc", "sane_lists"],
        extension_configs={"toc": {"slugify": slugify, "permalink": False}},
    )
    html = md.convert(preprocess(md_text))

    # Nummerierte Kapitel (## 1. …) auf neuer Seite beginnen
    html = re.sub(r'<h2 id="(\d+[^"]*)">', r'<h2 class="chapter" id="\1">', html)
    # Trennlinien direkt vor einem neuen Kapitel entfernen (sonst entstehen leere Seiten)
    html = re.sub(r'<hr\s*/?>\s*(?=<h2 class="chapter")', "", html)

    # Breite Tabellen (ab 7 Spalten) kleiner setzen
    def mark_wide(m):
        table = m.group(0)
        head = re.search(r"<thead>.*?</thead>", table, re.S)
        cols = head.group(0).count("<th") if head else 0
        return table.replace("<table>", '<table class="wide">', 1) if cols >= 7 else table

    html = re.sub(r"<table>.*?</table>", mark_wide, html, flags=re.S)

    # Zubehör-Kapitel in eine Section packen (für sichtbare URLs im Druck)
    html = re.sub(
        r'(<h2 class="chapter" id="17-zubehör-mit-links">.*?)(?=<h2 class="chapter")',
        r'<section class="zubehoer">\1</section>',
        html,
        flags=re.S,
    )

    # Titelblock: H1 + erstes Zitat + Einleitungsabsatz hervorheben
    html = re.sub(r"(<h1[^>]*>.*?</h1>\s*<blockquote>.*?</blockquote>)", r'<div class="titelblock">\1</div>', html, count=1, flags=re.S)

    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<title>Cannabis-Anbau für Einsteiger – Schritt-für-Schritt-Anleitung</title>
<style>{CSS}</style></head>
<body>{html}</body></html>"""


def main():
    with open(SRC, encoding="utf-8") as f:
        md_text = f.read()
    html = build_html(md_text)
    with tempfile.TemporaryDirectory() as tmp:
        html_path = os.path.join(tmp, "anleitung.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        cmd = [
            CHROME, "--headless", "--no-sandbox", "--disable-gpu",
            "--no-pdf-header-footer", f"--print-to-pdf={OUT}",
            "file://" + html_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not os.path.exists(OUT):
            sys.stderr.write(res.stdout + res.stderr)
            sys.exit(1)
    print("PDF erzeugt:", OUT)


if __name__ == "__main__":
    main()
