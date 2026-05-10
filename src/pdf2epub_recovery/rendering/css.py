"""Minimal reader-friendly EPUB CSS."""

from __future__ import annotations

DEFAULT_CSS = """
html {
  widows: 2;
  orphans: 2;
}

body {
  font-family: serif;
  line-height: 1.55;
  margin: 0;
  padding: 0 1em;
  hyphens: auto;
  text-align: start;
}

.book {
  max-width: 42em;
  margin: 0 auto;
}

h1 {
  font-size: 1.4em;
  line-height: 1.2;
  margin: 0 0 1.4em 0;
  text-align: center;
}

p {
  margin: 0;
}

p + p {
  margin-top: 0.25em;
  text-indent: 1.4em;
}

p.short {
  margin: 1.2em 0 0.7em;
  text-indent: 0;
  font-weight: bold;
  text-align: start;
}

h1 + p,
p.short + p {
  text-indent: 0;
}

ul.bullet-list {
  margin: 0.65em 0 0.65em 1.35em;
  padding: 0;
}

ul.bullet-list li {
  margin: 0.2em 0;
  padding-left: 0.15em;
  text-indent: 0;
}

aside.callout {
  margin: 1em 0;
  padding: 0.85em 1em;
  background-color: #eef5fb;
  border: 1px solid #d5e0ec;
}

aside.callout p {
  margin: 0;
  text-indent: 0;
}

aside.callout p + p {
  margin-top: 0.55em;
}

aside.callout p.callout-title {
  font-weight: bold;
  color: #123b63;
}

nav.pdf-toc {
  margin: 1em 0 1.5em;
}

nav.pdf-toc h2 {
  font-size: 1.25em;
  margin: 0 0 0.8em;
}

nav.pdf-toc ol {
  list-style: none;
  margin: 0;
  padding: 0;
}

nav.pdf-toc li {
  margin: 0.45em 0;
  text-indent: 0;
}

nav.pdf-toc .toc-level-2 {
  margin-left: 1.2em;
}

nav.pdf-toc .toc-level-3,
nav.pdf-toc .toc-level-4,
nav.pdf-toc .toc-level-5,
nav.pdf-toc .toc-level-6 {
  margin-left: 2.2em;
}

nav.pdf-toc .toc-page {
  float: right;
  margin-left: 1em;
}

figure.image {
  margin: 1.2em 0;
  text-align: center;
}

figure.image img {
  max-width: 100%;
  height: auto;
}

figure.table-fallback {
  margin: 1em 0;
  overflow-x: auto;
}

figure.table {
  margin: 1em 0;
  overflow-x: auto;
}

figure.table table {
  border-collapse: collapse;
  width: 100%;
}

figure.table-fallback table {
  border-collapse: collapse;
  width: 100%;
}

figure.table th,
figure.table td,
figure.table-fallback th,
figure.table-fallback td {
  border: 1px solid #d5e0ec;
  padding: 0.45em 0.6em;
  text-align: start;
  vertical-align: top;
}

figure.table th,
figure.table-fallback th {
  background-color: #1f4e79;
  color: #fff;
  font-weight: bold;
}

figure.table tbody tr:nth-child(even),
figure.table-fallback tbody tr:nth-child(even) {
  background-color: #f5f8fb;
}

figure.table-fallback pre {
  margin: 0;
  font-family: ui-monospace, "Courier New", monospace;
  line-height: 1.35;
  white-space: pre;
}
""".strip()
