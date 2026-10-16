"""Build the homepage's concise task montages from the app recordings.

Run with Python from the repo root; ffmpeg must be on PATH. The PDF scenes
were captured from the running app; the final scene follows a verified PDF
download. Source clips remain intact for use in the individual feature guides.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEOS = ROOT / "docs/assets/workflows"
STILLS = ROOT / "assets/workflow-sources"
FONT = "Arial"
# (source, start, duration, caption); time ranges omit the extra trial steps,
# replay-speed adjustment, and the original click-count closing cards.
EDITS = {
    "home-replay": [
        ("replay", 0, 4.8, "Replay the reading"),
        ("replay", 9, 4, "Follow the fixation sequence"),
    ],
    "home-filter-annotate": [
        ("trial-filtering", 5.1, 7.6, "Filter by condition and reader"),
        ("favorites", 0.5, 5.9, "Star and tag readings for follow-up"),
    ],
    "home-compare": [
        ("compare", 0, 12.5, "Overlay readings or place them side by side"),
        ("subtabs", 7.2, 2.5, "Comparisons - find matching trials"),
    ],
    "home-customize": [
        ("design-presets", 0, 10.8, "Start with a design preset"),
        ("plot-controls", 0.7, 14.8, "Adjust layers, properties and palette"),
    ],
    "home-export-share": [
        ("pdf-format.png", 0, 1.5, "Choose a download format"),
        ("pdf-selected.png", 0, 2, "Choose PDF"),
        ("pdf-downloaded.png", 0, 1.5, "Download the PDF figure"),
        ("share-link", 2.5, 8.5, "Share the view as code or a link"),
    ],
}


def run(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="docs-video-edit-") as temp:
        folder = Path(temp)
        for name, scenes in EDITS.items():
            parts = []
            for index, (source, start, duration, caption) in enumerate(scenes):
                output = folder / f"{name}-{index}.mp4"
                is_still = source.endswith(".png")
                path = STILLS / source if is_still else VIDEOS / f"{source}.mp4"
                inputs = ["-loop", "1"] if is_still else ["-ss", str(start)]
                filters = (
                    "scale=1280:800:force_original_aspect_ratio=decrease,"
                    "pad=1280:800:(ow-iw)/2:(oh-ih)/2:white,setsar=1,fps=20,"
                    # Replace the old counts rather than imply a new count.
                    "drawbox=x=600:y=0:w=680:h=50:color=white:t=fill,"
                    f"drawtext=font='{FONT}':text='{caption}':"
                    "fontsize=17:fontcolor=0x1c65a3:x=w-tw-18:y=10"
                )
                run(
                    *inputs,
                    "-i",
                    str(path),
                    "-t",
                    str(duration),
                    "-vf",
                    filters,
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "slow",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    str(output),
                )
                parts.append(output)
            listing = folder / "parts.txt"
            listing.write_text("".join(f"file '{part}'\n" for part in parts))
            output = VIDEOS / f"{name}.mp4"
            run(
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(output),
            )
            run(
                "-ss",
                "1",
                "-i",
                str(output),
                "-frames:v",
                "1",
                "-c:v",
                "libwebp",
                "-quality",
                "85",
                str(VIDEOS / f"{name}_poster.webp"),
            )
            print(name, flush=True)


if __name__ == "__main__":
    main()
