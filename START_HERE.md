# START HERE

Use this order.

## 1. Create repository

```bash
mkdir pdf2epub-recovery
cd pdf2epub-recovery
git init
```

Copy all files from this package into the repository root.

## 2. Create development environment

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## 3. Validate bootstrap

```bash
python -m pytest
pdf2epub-recovery --help
```

## 4. First Codex task

Give Codex this:

```text
Read AGENTS.md, README.md, docs/roadmap.md, and the current source/tests.

Goal:
Review the bootstrap for correctness and minimalism.

Constraints:
- Do not implement conversion yet.
- Do not add heavy dependencies.
- Fix only real bootstrap issues.
- Keep changes small and tested.

Done when:
- pytest passes
- CLI --help works
- summary states changed / validated / unverified
```

## 5. Second Codex task

After bootstrap is clean, start Phase 1 from `docs/roadmap.md`.
