"""Where the panel's package lives, since its folder is not an importable name.

The add-on sits in `parent-panel/`, which a hyphen keeps out of an import statement. The
package inside it is `panel`, so the folder goes on the path and the package imports
normally — rather than renaming a directory the Supervisor documentation names.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "parent-panel"))
