"""Hashing the parent PIN, so that the PIN itself never reaches the broker.

The TV verifies against the hash and never sees the PIN a parent typed here. The
parameters travel with the digest, which is what lets the iteration count be raised
later without invalidating the PIN somebody is already using.

Kept in step with ParentPin.kt on the other side. There is a pinned test vector on
both halves — nothing else checks that two languages derive the same bytes, and a PIN
set here that does not verify there is a parent locked out of their own television.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Any, Final

ALGORITHM: Final = "sha256"
ITERATIONS: Final = 120_000
SALT_BYTES: Final = 16
KEY_BYTES: Final = 32

# Exactly four, matching ParentPin.LENGTH on the TV. Entry there submits itself on the
# last digit the way the platform's own PIN screens do, which is only possible when the
# length is known — and on the screen that sets a PIN it never would be with a range.
LENGTH: Final = 4


def is_plausible(pin: str) -> bool:
    """Whether this could be a PIN at all.

    ASCII digits only. `str.isdigit()` alone is true of Arabic-Indic and other numerals,
    which no television remote produces and which would be a surprising thing to have
    silently accepted as a PIN.
    """
    return len(pin) == LENGTH and pin.isascii() and pin.isdigit()


def hash_pin(
    pin: str, salt_hex: str | None = None, iterations: int = ITERATIONS
) -> dict[str, Any]:
    """Derive the payload the TV stores: parameters, salt and digest.

    The salt is a parameter only so a test can pin the result; in use it is generated
    here, per PIN, so that two households with the same PIN do not share a hash.
    """
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        ALGORITHM, pin.encode(), salt, iterations, dklen=KEY_BYTES
    )
    return {
        "iterations": iterations,
        "salt": salt.hex(),
        "hash": derived.hex(),
    }
