"""Optional EPUB validation wrapper."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def validate_epub(path: Path) -> tuple[int, str]:
    """Run EPUBCheck if configured, otherwise fail clearly."""

    if not path.exists():
        return 1, f"EPUB file does not exist: {path}"

    executable = shutil.which("epubcheck")
    if executable is None:
        return (
            2,
            "EPUBCheck is not configured. Install an `epubcheck` executable on PATH to validate.",
        )

    completed = subprocess.run(
        [executable, str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(part for part in [completed.stdout, completed.stderr] if part).strip()
    return completed.returncode, output
