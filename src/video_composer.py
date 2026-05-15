"""Compõe o vídeo final.

Layouts disponíveis:

* ``overlay``      – avatar sobreposto sobre o slide (canto). PODE COBRIR conteúdo.
* ``side-by-side`` – canvas dividido: slide à esquerda, avatar à direita. SEM sobreposição.
* ``slide-top``    – slide na parte de cima ocupando toda a largura, avatar embaixo.

Para todos os layouts, a duração de cada segmento é a duração do MP4 do avatar.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

# Compatibilidade Pillow >= 10 com moviepy 1.x (que ainda usa Image.ANTIALIAS)
from PIL import Image as _PILImage  # noqa: E402

if not hasattr(_PILImage, "ANTIALIAS"):
    _PILImage.ANTIALIAS = _PILImage.Resampling.LANCZOS  # type: ignore[attr-defined]

from moviepy.editor import (  # noqa: E402
    ColorClip,
    ImageClip,
    VideoFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
)

VIDEO_W, VIDEO_H = 1920, 1080
BG_COLOR = (15, 32, 64)  # mesmo azul escuro usado nos slides


def _fit_inside(src_w: int, src_h: int, max_w: int, max_h: int) -> Tuple[int, int]:
    """Retorna (w, h) que mantém aspect ratio cabendo dentro do retângulo."""
    ratio = min(max_w / src_w, max_h / src_h)
    return max(1, int(src_w * ratio)), max(1, int(src_h * ratio))


def _build_overlay(slide_img: Path, avatar: VideoFileClip,
                   avatar_position: str) -> CompositeVideoClip:
    duration = avatar.duration
    slide = ImageClip(str(slide_img)).set_duration(duration).resize((VIDEO_W, VIDEO_H))

    avatar_resized = avatar.resize(height=520)
    margin = 40
    if avatar_position == "bottom-right":
        pos = (VIDEO_W - avatar_resized.w - margin, VIDEO_H - avatar_resized.h - margin)
    elif avatar_position == "bottom-left":
        pos = (margin, VIDEO_H - avatar_resized.h - margin)
    else:
        pos = ("center", "bottom")
    avatar_resized = avatar_resized.set_position(pos)
    return CompositeVideoClip([slide, avatar_resized], size=(VIDEO_W, VIDEO_H))


def _build_side_by_side(slide_img: Path, avatar: VideoFileClip,
                         slide_ratio: float = 0.72) -> CompositeVideoClip:
    duration = avatar.duration
    bg = ColorClip(size=(VIDEO_W, VIDEO_H), color=BG_COLOR).set_duration(duration)

    slide_area_w = int(VIDEO_W * slide_ratio)
    avatar_area_w = VIDEO_W - slide_area_w
    pad = 30

    # Slide à esquerda (letterbox dentro da área)
    slide = ImageClip(str(slide_img)).set_duration(duration)
    sw, sh = _fit_inside(slide.w, slide.h, slide_area_w - 2 * pad, VIDEO_H - 2 * pad)
    slide = slide.resize((sw, sh))
    slide_pos = ((slide_area_w - sw) // 2, (VIDEO_H - sh) // 2)
    slide = slide.set_position(slide_pos)

    # Avatar à direita (letterbox dentro da área)
    aw, ah = _fit_inside(avatar.w, avatar.h, avatar_area_w - 2 * pad, VIDEO_H - 2 * pad)
    avatar_resized = avatar.resize((aw, ah))
    avatar_pos = (slide_area_w + (avatar_area_w - aw) // 2, (VIDEO_H - ah) // 2)
    avatar_resized = avatar_resized.set_position(avatar_pos)

    return CompositeVideoClip([bg, slide, avatar_resized], size=(VIDEO_W, VIDEO_H))


def _build_slide_top(slide_img: Path, avatar: VideoFileClip,
                      avatar_height: int = 380) -> CompositeVideoClip:
    duration = avatar.duration
    bg = ColorClip(size=(VIDEO_W, VIDEO_H), color=BG_COLOR).set_duration(duration)

    pad = 20
    slide_area_h = VIDEO_H - avatar_height - 2 * pad
    slide = ImageClip(str(slide_img)).set_duration(duration)
    sw, sh = _fit_inside(slide.w, slide.h, VIDEO_W - 2 * pad, slide_area_h)
    slide = slide.resize((sw, sh)).set_position(((VIDEO_W - sw) // 2, pad))

    avatar_resized = avatar.resize(height=avatar_height)
    ax = (VIDEO_W - avatar_resized.w) // 2
    ay = VIDEO_H - avatar_height - pad // 2
    avatar_resized = avatar_resized.set_position((ax, ay))

    return CompositeVideoClip([bg, slide, avatar_resized], size=(VIDEO_W, VIDEO_H))


def build_training_video(
    slide_images: List[Path],
    avatar_videos: List[Path],
    output_path: Path,
    fps: int = 25,
    layout: str = "side-by-side",
    avatar_position: str = "bottom-right",
) -> Path:
    if len(slide_images) != len(avatar_videos):
        raise ValueError(
            f"Número de slides ({len(slide_images)}) difere de vídeos do avatar ({len(avatar_videos)})."
        )

    segments = []
    for img_path, vid_path in zip(slide_images, avatar_videos):
        avatar = VideoFileClip(str(vid_path))
        duration = avatar.duration

        if layout == "overlay":
            comp = _build_overlay(img_path, avatar, avatar_position)
        elif layout == "side-by-side":
            comp = _build_side_by_side(img_path, avatar)
        elif layout == "slide-top":
            comp = _build_slide_top(img_path, avatar)
        else:
            raise ValueError(f"Layout desconhecido: {layout}")

        comp = comp.set_audio(avatar.audio).set_duration(duration)
        segments.append(comp)

    final = concatenate_videoclips(segments, method="compose")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        threads=4,
    )
    return output_path
