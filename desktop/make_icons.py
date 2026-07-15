"""Generate the desktop app icons (ENG-15).

Draws a scanpath motif — text lines with fixation dots joined by saccade
segments, including one regression — on a rounded dark tile, then writes the
committed icon files:

    desktop/icons/icon.png    512x512 master (also the Linux icon)
    desktop/icons/icon.ico    Windows (multi-resolution)
    desktop/icons/icon.icns   macOS

Run once (or after tweaking the design) from the repo root:
    python desktop/make_icons.py
Regenerated icons are committed; builds never run this script.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from scanpath_studio.constants import APP_THEME_DARK, CURRENT_FIX_OUTLINE

SIZE = 512
BG = APP_THEME_DARK["backgroundColor"]
LINE = "#3a4154"  # muted text-line bars (icon-only shade)
SACCADE = APP_THEME_DARK["primaryColor"]
FIXATION = CURRENT_FIX_OUTLINE

# Fixation centers (x, y, radius) along three "text lines", with a regression
# from the 5th fixation back up to the 6th.
TEXT_LINES_Y = (150, 256, 362)
FIXATIONS = (
    (110, 150, 30),
    (250, 150, 42),
    (400, 150, 26),
    (170, 256, 36),
    (360, 256, 48),
    (250, 150, 0),  # regression target: revisit line 1 (no extra dot)
    (120, 362, 28),
    (330, 362, 38),
)


def draw_icon(size: int = SIZE) -> Image.Image:
    scale = size / SIZE
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def s(value: float) -> float:
        return value * scale

    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=s(96), fill=BG)

    # Text lines (the reading stimulus).
    for y in TEXT_LINES_Y:
        draw.rounded_rectangle(
            (s(64), s(y - 16), s(448), s(y + 16)), radius=s(16), fill=LINE
        )

    # Saccades under the fixation dots.
    points = [(s(x), s(y)) for x, y, _ in FIXATIONS]
    draw.line(points, fill=SACCADE, width=max(1, round(s(14))), joint="curve")

    # Fixation dots, sized like duration-scaled markers.
    for x, y, r in FIXATIONS:
        if r == 0:
            continue
        draw.ellipse(
            (s(x - r), s(y - r), s(x + r), s(y + r)),
            fill=FIXATION,
            outline=BG,
            width=max(1, round(s(6))),
        )
    return img


def main() -> None:
    out_dir = Path(__file__).resolve().parent / "icons"
    out_dir.mkdir(exist_ok=True)

    master = draw_icon()
    master.save(out_dir / "icon.png")

    ico_sizes = [(n, n) for n in (16, 24, 32, 48, 64, 128, 256)]
    master.save(out_dir / "icon.ico", sizes=ico_sizes)

    # Pillow writes .icns cross-platform; macOS reads the embedded sizes.
    master.save(out_dir / "icon.icns")

    print(f"Wrote icon.png / icon.ico / icon.icns to {out_dir}")


if __name__ == "__main__":
    main()
