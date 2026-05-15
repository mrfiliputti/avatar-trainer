"""Carrega slides já existentes (imagens) de um diretório, com ordenação natural."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def _natural_key(p: Path):
    parts = re.split(r"(\d+)", p.stem)
    return [int(s) if s.isdigit() else s.lower() for s in parts]


def load_slides(slides_dir: str | Path) -> List[Path]:
    d = Path(slides_dir)
    if not d.is_dir():
        raise FileNotFoundError(f"Diretório de slides não encontrado: {d}")
    files = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    if not files:
        raise FileNotFoundError(
            f"Nenhuma imagem encontrada em {d} (extensões aceitas: {sorted(SUPPORTED_EXTS)})"
        )
    files.sort(key=_natural_key)
    return files
