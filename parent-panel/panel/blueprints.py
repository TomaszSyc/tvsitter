"""Putting the blueprints where Home Assistant reads them.

`docs/setup.md` has asked a person to copy a file into
`config/blueprints/automation/tvsitter/` since M3. An App has the configuration
directory mapped, so it can do that — and do it again on every update, which is the
half nobody does by hand (#104).

Writing a file is the whole of it. Creating the automation from the blueprint needs
to know which phone to notify, which is a question for a page rather than a guess.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import logging
from pathlib import Path
import shutil

_LOGGER = logging.getLogger("panel")

# What the image carries, put there at build time so the blueprint installed is the one
# this version was built with.
CARRIED = Path("/opt/blueprints")

# Where the Supervisor mounts the configuration directory. Probed rather than picked:
# the mount point has been `/config` and `/homeassistant` at different times and the
# documentation now says `/homeassistant_config`. A panel that writes one into a
# directory nothing reads is worse than one that says it could not.
CANDIDATES = (
    Path("/homeassistant_config"),
    Path("/homeassistant"),
    Path("/config"),
)

WITHIN = Path("blueprints/automation/tvsitter")


def configuration_directory(candidates: tuple[Path, ...] = CANDIDATES) -> Path | None:
    """Find the configuration directory, or nothing when none is mapped.

    A directory holding `configuration.yaml` is the one Home Assistant runs from. The
    file rather than the directory, because `/config` also exists when an App maps its
    own configuration there — and blueprints written into that are silent and useless.
    """
    for candidate in candidates:
        if (candidate / "configuration.yaml").is_file():
            return candidate
    return None


def install(carried: Path = CARRIED, into: Path | None = None) -> list[str]:
    """Copy every blueprint this version carries, and say which ones landed.

    Overwrites on purpose. A blueprint is this project's file in this project's
    directory, and an update leaving the last version's trigger in place is how the
    request-for-time flow ends up quietly broken — which it was, for six days (#117).

    Nothing here reloads automations. Home Assistant re-reads a blueprint when the
    automation using it is reloaded or on the next restart, and reaching over the API
    to force that is a bigger claim on somebody's house than writing a file.
    """
    if into is None:
        into = configuration_directory()
    if into is None:
        _LOGGER.warning("no configuration directory mapped; blueprints not written")
        return []

    target = into / WITHIN
    target.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for source in sorted(carried.glob("automation/tvsitter/*.yaml")):
        try:
            shutil.copyfile(source, target / source.name)
        except OSError as failure:
            # Said out loud and survived: a blueprint that cannot be written is a
            # manual copy — where this started — not a reason for the panel not to run.
            _LOGGER.warning("could not write %s: %s", source.name, failure)
            continue
        written.append(source.name)

    if written:
        _LOGGER.info("blueprints written to %s: %s", target, ", ".join(written))
    return written
