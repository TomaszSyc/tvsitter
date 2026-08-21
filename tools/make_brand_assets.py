#!/usr/bin/env python3
"""Generates brand/icon.png for HACS and the home-assistant/brands repository.

The assets are generated rather than committed as opaque binaries so they can be
reproduced and reviewed in a diff. The clock deliberately reads 4:00 — the hour the
budget day resets (see rules/BudgetClock.kt).

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import math
import pathlib

from PIL import Image, ImageDraw

SCALE = 4  # draw oversized and downscale to get smooth edges
BACKDROP = (22, 35, 46, 255)
ACCENT = (76, 194, 165, 255)
DIAL = (242, 247, 245, 255)


def draw_icon(size: int) -> Image.Image:
    """Draw the icon at the given edge length, in pixels."""
    canvas = size * SCALE
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    unit = canvas / 1024  # the coordinates below are expressed in a 1024 grid

    def px(value: float) -> float:
        return value * unit

    draw.rounded_rectangle(
        (0, 0, canvas - 1, canvas - 1), radius=px(224), fill=BACKDROP
    )

    # TV screen.
    draw.rounded_rectangle(
        (px(140), px(236), px(884), px(700)),
        radius=px(48),
        outline=ACCENT,
        width=int(px(32)),
    )
    # Stand.
    draw.line((px(512), px(700), px(512), px(792)), fill=ACCENT, width=int(px(32)))
    draw.line((px(392), px(806), px(632), px(806)), fill=ACCENT, width=int(px(32)))

    # Clock face in the middle of the screen.
    center_x, center_y, radius = px(512), px(468), px(122)
    draw.ellipse(
        (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
        outline=DIAL,
        width=int(px(26)),
    )
    hand_length = radius * 0.66
    for degrees in (0, 120):  # 12:00 and 4:00
        angle = math.radians(degrees)
        draw.line(
            (
                center_x,
                center_y,
                center_x + hand_length * math.sin(angle),
                center_y - hand_length * math.cos(angle),
            ),
            fill=DIAL,
            width=int(px(24)),
        )

    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    """Write every icon size into the brand directory."""
    target = pathlib.Path(__file__).resolve().parent.parent / "brand"
    target.mkdir(exist_ok=True)
    for size, name in ((256, "icon.png"), (512, "icon@2x.png")):
        path = target / name
        draw_icon(size).save(path, optimize=True)
        print(f"wrote {path.relative_to(target.parent)} ({size}x{size})")


if __name__ == "__main__":
    main()
