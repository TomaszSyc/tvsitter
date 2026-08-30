#!/usr/bin/env bash
# Renders every bitmap the app ships from the SVG sources in brand/.
#
# The sources are SVG so they can be edited and reviewed in a diff; the bitmaps are generated so
# nobody has to redraw one by hand at five densities. Needs `rsvg-convert` (brew install librsvg).
#
# TV Sitter — parental control for Android TV / Google TV.
# Copyright (C) 2026 Tomasz Syc
# SPDX-License-Identifier: AGPL-3.0-only
set -euo pipefail
cd "$(dirname "$0")/.."
res=app/src/main/res

# The launcher tile on the Android TV home row. 320×180 is the xhdpi size the platform asks for.
for spec in mdpi:160:90 hdpi:240:135 xhdpi:320:180 xxhdpi:480:270; do
  IFS=: read -r density width height <<<"$spec"
  rsvg-convert -w "$width" -h "$height" brand/banner.svg -o "$res/drawable-$density/banner.png"
done

# The adaptive icon's two layers. The monochrome one is what a themed launcher tints, so it must
# be the same shape in one colour rather than a greyscale copy of the other.
for spec in mdpi:108 hdpi:162 xhdpi:216 xxhdpi:324 xxxhdpi:432; do
  IFS=: read -r density size <<<"$spec"
  rsvg-convert -w "$size" -h "$size" brand/foreground.svg -o "$res/mipmap-$density/ic_launcher_foreground.png"
  rsvg-convert -w "$size" -h "$size" brand/foreground-mono.svg -o "$res/mipmap-$density/ic_launcher_monochrome.png"
done

# HACS and home-assistant/brands want 256 and 512.
rsvg-convert -w 256 -h 256 brand/mark.svg -o brand/icon.png
rsvg-convert -w 512 -h 512 brand/mark.svg -o brand/icon@2x.png

# The Supervisor's app store: a square icon at 128, and a logo it lays out at 250x100. The
# logo is the banner, which already carries the name — the store shows no label under it
# either, so the same reasoning applies.
rsvg-convert -w 128 -h 128 brand/mark.svg -o parent-panel/icon.png
rsvg-convert -w 250 -h 100 brand/banner.svg -o parent-panel/logo.png

echo "brand assets rendered"
