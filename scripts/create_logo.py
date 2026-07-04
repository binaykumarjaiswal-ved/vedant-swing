#!/usr/bin/env python3
"""Create Vedant Swing logo PNG."""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets" / "vedant-swing-logo.png"


def main() -> None:
    size = 256
    img = Image.new("RGBA", (size, size), (11, 18, 32, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((8, 8, size - 8, size - 8), radius=36, outline=(59, 130, 246), width=6)
    draw.polygon([(60, 170), (95, 95), (130, 130), (165, 70), (196, 170)], fill=(34, 197, 94))
    draw.rectangle((60, 170, 196, 185), fill=(59, 130, 246))
    draw.text((72, 198), "VEDANT", fill=(255, 255, 255))
    draw.text((92, 218), "SWING", fill=(148, 163, 184))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()