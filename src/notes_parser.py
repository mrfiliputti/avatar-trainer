"""Parser do arquivo de notas com a estrutura:

    SLIDE 1
    Speaker Notes
    Texto da narração do slide 1
    pode ter várias linhas e parágrafos.

    SLIDE 2
    Speaker Notes
    Texto da narração do slide 2 ...

A linha "Speaker Notes" é apenas um cabeçalho e é ignorada.
Linhas em branco dentro de um bloco são preservadas como parágrafos.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

SLIDE_HEADER_RE = re.compile(r"^\s*SLIDE\s+(\d+)\s*[:\-]?\s*$", re.IGNORECASE)
NOTES_HEADER_RE = re.compile(r"^\s*Speaker\s+Notes\s*[:\-]?\s*$", re.IGNORECASE)


@dataclass
class SlideNote:
    index: int
    text: str


def parse_notes(path: str | Path) -> Dict[int, str]:
    """Lê o arquivo e devolve um dict {slide_index: narration_text}."""
    raw = Path(path).read_text(encoding="utf-8")
    lines = raw.splitlines()

    notes: Dict[int, List[str]] = {}
    current_idx: int | None = None
    skip_next_header = False

    for line in lines:
        m = SLIDE_HEADER_RE.match(line)
        if m:
            current_idx = int(m.group(1))
            notes.setdefault(current_idx, [])
            skip_next_header = True  # próxima linha "Speaker Notes" será descartada
            continue
        if current_idx is None:
            continue
        if skip_next_header:
            # Permite linhas em branco entre "SLIDE N" e "Speaker Notes".
            if not line.strip():
                continue
            if NOTES_HEADER_RE.match(line):
                skip_next_header = False
                continue
            skip_next_header = False
        notes[current_idx].append(line)

    result: Dict[int, str] = {}
    for idx, buf in notes.items():
        # Remove linhas em branco do começo/fim, mantém parágrafos internos
        text = "\n".join(buf).strip()
        # Compacta espaços/quebras múltiplas em parágrafos limpos
        paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
        paragraphs = [p for p in paragraphs if p]
        result[idx] = "\n\n".join(paragraphs)

    return result
