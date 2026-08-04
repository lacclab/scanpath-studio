"""Generate the desktop app icons (ENG-15).

Draws a scanpath motif — four fixation dots joined across compact word blocks,
including a return sweep — on a rounded dark tile, then writes the
committed icon files:

    desktop/icons/icon.png    512x512 master (also the Linux icon)
    desktop/icons/icon.ico    Windows (multi-resolution)
    desktop/icons/icon.icns   macOS
    docs/assets/icon.png      docs-site logo/favicon (same master)

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
LINE = "#4a5572"  # muted word blocks: stimulus context, not the main silhouette
SACCADE = APP_THEME_DARK["primaryColor"]
FIXATION = CURRENT_FIX_OUTLINE
FIXATION_RING = APP_THEME_DARK["textColor"]

# VIZ-29: four bold targets form a simple reading/return-sweep silhouette. The
# previous eight-point path crossed itself and collapsed into noise at 16 px.
FIXATIONS = (
    (120, 142, 36),
    (382, 142, 42),
    (176, 264, 46),
    (340, 374, 38),
)

# Short blocks read as words rather than a generic hamburger/menu icon. Gaps
# stay visible at 16–32 px and keep the scanpath unmistakably in the foreground.
WORD_BLOCKS = (
    (70, 130, 180, 154),
    (208, 130, 318, 154),
    (344, 130, 442, 154),
    (70, 252, 144, 276),
    (170, 252, 282, 276),
    (308, 252, 442, 276),
    (70, 362, 198, 386),
    (226, 362, 310, 386),
    (336, 362, 442, 386),
)


def draw_icon(size: int = SIZE) -> Image.Image:
    scale = size / SIZE
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def s(value: float) -> float:
        return value * scale

    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=s(96), fill=BG)

    # Word blocks (the reading stimulus), intentionally subordinate.
    for x0, y0, x1, y1 in WORD_BLOCKS:
        draw.rounded_rectangle((s(x0), s(y0), s(x1), s(y1)), radius=s(12), fill=LINE)

    # Saccades under the fixation dots.
    points = [(s(x), s(y)) for x, y, _ in FIXATIONS]
    draw.line(points, fill=SACCADE, width=max(1, round(s(20))), joint="curve")

    # Pale ring survives both the dark tile and light OS icon treatments.
    for x, y, r in FIXATIONS:
        draw.ellipse(
            (s(x - r), s(y - r), s(x + r), s(y + r)),
            fill=FIXATION_RING,
        )
        inset = max(2, r * 0.22)
        draw.ellipse(
            (s(x - r + inset), s(y - r + inset), s(x + r - inset), s(y + r - inset)),
            fill=FIXATION,
        )
    return img


def main() -> None:
    out_dir = Path(__file__).resolve().parent / "icons"
    out_dir.mkdir(exist_ok=True)

    master = draw_icon()
    master.save(out_dir / "icon.png")

    # The docs site uses the same master as logo/favicon — regenerate it here
    # so a redesign can't leave the published site on the old icon.
    docs_icon = Path(__file__).resolve().parent.parent / "docs" / "assets" / "icon.png"
    master.save(docs_icon)

    ico_sizes = [(n, n) for n in (16, 24, 32, 48, 64, 128, 256)]
    master.save(out_dir / "icon.ico", sizes=ico_sizes)

    # Pillow writes .icns cross-platform; macOS reads the embedded sizes.
    master.save(out_dir / "icon.icns")

    print(
        f"Wrote icon.png / icon.ico / icon.icns to {out_dir} (+ docs/assets/icon.png)"
    )


if __name__ == "__main__":
    main()
