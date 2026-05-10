# Codex Prompts

Use these prompts as starting points. Keep each task small.

## Phase 0 bootstrap review

```text
Read AGENTS.md, README.md, pyproject.toml, and tests.

Goal:
Review the current bootstrap structure for correctness and minimalism.

Constraints:
- Do not implement PDF conversion yet.
- Do not add heavy dependencies.
- Only fix real bootstrap issues.
- Keep changes small.

Done when:
- pytest passes
- CLI --help works
- summary states changed / validated / unverified
```

## Phase 1 profiler

```text
Read AGENTS.md, docs/roadmap.md, src/pdf2epub_recovery/profiling/profiler.py, and tests.

Goal:
Improve the profile command without implementing full extraction.

Constraints:
- Smallest safe change.
- Use only stdlib unless a dependency is justified.
- Keep output stable and tested.
- Include warnings for approximate values.

Done when:
- profile command writes JSON
- tests cover valid-looking PDF and non-PDF input
- summary states limitations
```

## Add PyMuPDF extraction adapter

```text
Read AGENTS.md, docs/architecture/pipeline.md, docs/architecture/document-ir.md, and current extraction files.

Goal:
Add the first real low-level extraction adapter using PyMuPDF.

Constraints:
- Add dependency only if needed in pyproject.toml.
- Keep raw extraction separate from normalization.
- Preserve page index, block id, bbox, text, and source engine.
- Add tests with small fixtures or mocked structures.
- Do not implement EPUB rendering.

Done when:
- adapter returns deterministic raw block data
- provenance is preserved
- tests pass
- limitations are documented
```

## Page artifact detection

```text
Read AGENTS.md, docs/roadmap.md, docs/quality-report.md, and existing extraction/cleaning code.

Goal:
Detect page number/header/footer candidates without removing them yet.

Constraints:
- Detection only, no destructive removal.
- Use multiple signals, not position alone.
- Include confidence and reason.
- Add tests for repeated headers and body text near margins.

Done when:
- artifact candidates appear in report/debug output
- false-positive cases are tested
- summary states risks
```
