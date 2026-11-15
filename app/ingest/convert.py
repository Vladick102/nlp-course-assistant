"""[DP] Convert .pptx/.docx course files to PDF with LibreOffice so one parser handles everything.

Raw folders are read-only; output goes to data/converted/<course>/<stem>.pdf. Idempotent.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import ROOT, cfg, path

CONVERTIBLE = {".pptx", ".ppt", ".docx", ".doc"}


def converted_path(src: Path, course: str) -> Path:
    return path("converted") / course / f"{src.stem}.pdf"


def convert_one(src: Path, course: str) -> Path:
    out = converted_path(src, course)
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    # separate LibreOffice profile so a running desktop instance doesn't block headless mode
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run(
            ["soffice", f"-env:UserInstallation=file://{prof}", "--headless", "--convert-to", "pdf",
             "--outdir", str(out.parent), str(src)],
            check=True, capture_output=True, timeout=600,
        )  # fmt: skip
    return out


def run() -> list[Path]:
    done = []
    for course, rel in cfg()["paths"]["raw_dirs"].items():
        for src in sorted((ROOT / rel).iterdir()):
            if src.suffix.lower() in CONVERTIBLE:
                print(f"convert {src.relative_to(ROOT)}", file=sys.stderr)
                done.append(convert_one(src, course))
    return done


if __name__ == "__main__":
    run()
