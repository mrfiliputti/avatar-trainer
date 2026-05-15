"""CLI: usa slides já existentes + notas → gera vídeos de avatar e vídeo final.

Uso:
    python -m src.main --slides-dir slides --notes notes.txt --out output

Opções:
    --skip-avatar     não chama Azure (apenas valida pareamento)
    --skip-video      gera os vídeos do avatar mas não compõe o vídeo final
    --avatar-position bottom-right | bottom-left | center

Estrutura esperada do arquivo de notas:

    SLIDE 1
    Speaker Notes
    Texto narrado para o slide 1...

    SLIDE 2
    Speaker Notes
    Texto narrado para o slide 2...
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from .notes_parser import parse_notes
from .slides_loader import load_slides
from .avatar_synthesizer import from_env, synthesize_for_slides
from .video_composer import build_training_video


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera vídeo de treinamento a partir de slides existentes + notas (Azure Avatar)"
    )
    parser.add_argument("--slides-dir", required=True, help="Diretório com as imagens dos slides")
    parser.add_argument("--notes", required=True, help="Arquivo .txt com as Speaker Notes")
    parser.add_argument("--out", default="output", help="Pasta de saída (default: output)")
    parser.add_argument("--skip-avatar", action="store_true", help="Não chamar Azure Avatar")
    parser.add_argument("--skip-video", action="store_true", help="Não montar vídeo final")
    parser.add_argument(
        "--layout",
        default="side-by-side",
        choices=["side-by-side", "overlay", "slide-top"],
        help="Composição do vídeo final (side-by-side não cobre o slide). Default: side-by-side",
    )
    parser.add_argument(
        "--avatar-position",
        default="bottom-right",
        choices=["bottom-right", "bottom-left", "center"],
        help="Posição do avatar (apenas em layout=overlay)",
    )
    parser.add_argument(
        "--name",
        default="treinamento",
        help="Nome base do vídeo final (default: treinamento)",
    )
    args = parser.parse_args(argv)

    load_dotenv()

    slides_dir = Path(args.slides_dir)
    notes_path = Path(args.notes)
    out_dir = Path(args.out)
    avatar_dir = out_dir / "avatar"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Carregando slides de {slides_dir} e notas de {notes_path}…")
    slides = load_slides(slides_dir)
    notes = parse_notes(notes_path)
    print(f"      {len(slides)} slides, {len(notes)} blocos de notas")

    # Pareamento por índice 1..N
    narrations: list[str] = []
    missing: list[int] = []
    for i, _slide in enumerate(slides, start=1):
        text = notes.get(i, "").strip()
        if not text:
            missing.append(i)
        narrations.append(text)

    if missing:
        print(f"⚠ Slides sem notas correspondentes: {missing}", file=sys.stderr)
        print("  (Esses slides serão pulados no avatar — adicione blocos SLIDE N no arquivo de notas.)",
              file=sys.stderr)

    if args.skip_avatar:
        print("[2/3] (pulado) Avatar")
        print("[3/3] (pulado) Vídeo final")
        return 0

    print("[2/3] Sintetizando avatar para cada slide com notas…")
    synth = from_env()

    pairs = [(slide, text) for slide, text in zip(slides, narrations) if text]
    pair_slides = [s for s, _ in pairs]
    pair_texts = [t for _, t in pairs]

    avatar_videos = synthesize_for_slides(pair_texts, avatar_dir, synth)
    print(f"      {len(avatar_videos)} vídeos em {avatar_dir}")

    if args.skip_video:
        print("[3/3] (pulado) Vídeo final")
        return 0

    print("[3/3] Compondo vídeo final…")
    final_path = out_dir / f"{args.name}.mp4"
    build_training_video(
        pair_slides,
        avatar_videos,
        final_path,
        layout=args.layout,
        avatar_position=args.avatar_position,
    )
    print(f"\n✔ Treinamento gerado em: {final_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
