"""Putting the blueprints where Home Assistant reads them, and keeping one copy honest.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from pathlib import Path

from panel.blueprints import WITHIN, configuration_directory, install

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "blueprints" / "automation" / "tvsitter"
CARRIED = ROOT / "parent-panel" / "blueprints" / "automation" / "tvsitter"


def test_the_image_carries_exactly_what_the_repository_holds() -> None:
    """Two copies of one file, because a Docker build cannot reach outside its context.

    Which is a drift waiting to happen, so it is a test rather than a note: an image
    shipping last month's blueprint installs it over the top of the right one, on
    every start.
    """
    assert {path.name for path in SOURCE.glob("*.yaml")} == {
        path.name for path in CARRIED.glob("*.yaml")
    }
    for path in SOURCE.glob("*.yaml"):
        assert path.read_bytes() == (CARRIED / path.name).read_bytes(), path.name


def test_the_configuration_directory_is_the_one_with_the_configuration_in_it(
    tmp_path: Path,
) -> None:
    """`/config` exists when an App maps its own, and writing there does nothing."""
    wrong = tmp_path / "wrong"
    right = tmp_path / "right"
    wrong.mkdir()
    right.mkdir()
    (right / "configuration.yaml").write_text("")

    assert configuration_directory((wrong, right)) == right
    assert configuration_directory((wrong,)) is None


def test_nothing_is_written_when_no_directory_is_mapped(tmp_path: Path) -> None:
    """A panel that cannot write a blueprint still has a page to serve.

    `into=None` probes the real mount points, none of which exist outside the
    container — so this also checks that a missing directory is answered, not raised.
    """
    assert install(carried=ROOT / "parent-panel" / "blueprints", into=None) == []


def test_every_blueprint_lands_where_home_assistant_looks(tmp_path: Path) -> None:
    """The path is Home Assistant's, so it is spelled out rather than derived."""
    written = install(carried=ROOT / "parent-panel" / "blueprints", into=tmp_path)

    assert set(written) == {path.name for path in SOURCE.glob("*.yaml")}
    for name in written:
        assert (tmp_path / WITHIN / name).is_file()


def test_installing_twice_leaves_the_current_one_in_place(tmp_path: Path) -> None:
    """An update carries a new blueprint, and the copy in the config is the one read.

    #117 was six days of a request-for-time flow that fired for nobody, because the
    trigger in the installed copy was the old one. Overwriting is the point.
    """
    target = tmp_path / WITHIN
    target.mkdir(parents=True)
    (target / "more_time_request.yaml").write_text("stale: yes\n")

    install(carried=ROOT / "parent-panel" / "blueprints", into=tmp_path)

    landed = (target / "more_time_request.yaml").read_bytes()
    assert landed == (SOURCE / "more_time_request.yaml").read_bytes()
