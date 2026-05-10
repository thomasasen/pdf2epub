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

figure.table-fallback pre {
  margin: 0;
  font-family: ui-monospace, "Courier New", monospace;
  line-height: 1.35;
  white-space: pre;
}
""".strip()
