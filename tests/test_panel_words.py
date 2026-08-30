"""The catalogue and the page have to be talking about the same sentences.

The whole scheme rests on the English sentence being the key, which buys readable source
at the price of one silent failure: change a word in the page and its translation stops
matching, with nothing to say so — the sentence simply comes out in English on a Polish
Home Assistant, on one screen, for whoever happens to open it.

So the sentences are read back out of the page itself and compared both ways. Every
sentence the page can say has to be in the catalogue, and every entry in the catalogue
has to be one the page can say.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

import re

from panel.page import _SCRIPT, render_shell
from panel.server import NO_TOKEN, NOT_A_REQUEST, REFUSED, SILENT, UNKEPT, UNMADE
from panel.words import LANGUAGES, POLISH, words
import pytest

PLACEHOLDER = re.compile(r"\{(\w+)\}")

# The sentences the panel writes rather than the page, listed by hand because they are
# raised from a dozen places and reach the parent through one. Only the ones that are
# the same every time — a sentence built around a television's name is not in the
# catalogue at all, and neither is it in here.
SERVER = [
    NO_TOKEN,
    REFUSED,
    SILENT,
    NOT_A_REQUEST,
    UNKEPT,
    UNMADE,
    "That television is not here any more.",
    "This needs an action.",
]


def _argument(source: str, at: int) -> str:
    """Return the first argument of a `phrase(`, with parentheses balanced."""
    depth = 0
    quote = ""
    start = at
    for here in range(at, len(source)):
        one = source[here]
        if quote:
            if one == "\\":
                continue
            if one == quote:
                quote = ""
            continue
        if one in "\"'":
            quote = one
        elif one in "([{":
            depth += 1
            if depth == 1:
                start = here + 1
        elif one in ")]}":
            depth -= 1
            if depth == 0:
                return source[start:here]
        elif one == "," and depth == 1:
            return source[start:here]
    raise AssertionError("a phrase( is not closed")


def _branches(argument: str) -> list[str]:
    """One argument split on a top-level ternary, so both answers are kept.

    `phrase(tv.locked ? "Lift the lock" : "Lock the television")` is two sentences the
    page can say, and a reading that took only the first would leave the other
    untranslated with nothing to notice it.
    """
    parts: list[str] = []
    held: list[str] = []
    depth = 0
    quote = ""
    for one in argument:
        if quote:
            held.append(one)
            if one == quote and held[-2:-1] != ["\\"]:
                quote = ""
            continue
        if one in "\"'":
            quote = one
            held.append(one)
        elif one in "([{":
            depth += 1
            held.append(one)
        elif one in ")]}":
            depth -= 1
            held.append(one)
        elif one in "?:" and depth == 0:
            parts.append("".join(held))
            held = []
        else:
            held.append(one)
    parts.append("".join(held))
    return parts


def _joined(part: str) -> str:
    """Join one branch's quoted pieces the way the page joins them."""
    said: list[str] = []
    held: list[str] = []
    quote = ""
    for one in part:
        if quote:
            if one == quote and held[-1:] != ["\\"]:
                said.append("".join(held))
                held, quote = [], ""
            else:
                held.append(one)
        elif one == '"':
            quote = one
            held = []
    # The escapes are what a browser has already turned back into characters by the time
    # a lookup happens, so the key is the sentence and not the way it is spelled.
    #
    # Through latin-1 rather than utf-8, because the source spells the same character
    # both ways: `\u2026` in one line and a literal … in the next, depending on which
    # hand wrote it. Encoding to utf-8 first would hand `unicode_escape` three bytes of
    # a character it reads one byte at a time, and the sentence would come back as
    # mojibake that matches nothing.
    return "".join(said).encode("latin-1", "backslashreplace").decode("unicode_escape")


def asked() -> list[str]:
    """Every sentence the page can ask for, in the order it first asks."""
    found: list[str] = []
    at = _SCRIPT.find("phrase(")
    while at >= 0:
        for branch in _branches(_argument(_SCRIPT, at + len("phrase"))):
            one = _joined(branch)
            if one and one not in found:
                found.append(one)
        at = _SCRIPT.find("phrase(", at + 1)
    return found


def everything() -> list[str]:
    """Every sentence a parent can read, from the page and from the panel alike."""
    return asked() + [one for one in SERVER if one not in asked()]


def test_the_page_asks_for_something() -> None:
    """A reading that finds nothing would make every check below vacuously true."""
    assert len(asked()) > 100


@pytest.mark.parametrize("language", sorted(LANGUAGES))
def test_every_sentence_the_page_says_has_been_translated(language: str) -> None:
    """A missing one comes out in English, on one screen, with nothing to say so."""
    missing = [one for one in everything() if one not in LANGUAGES[language]]

    assert not missing, f"{language} has no words for: {missing}"


@pytest.mark.parametrize("language", sorted(LANGUAGES))
def test_the_catalogue_holds_nothing_the_page_cannot_say(language: str) -> None:
    """An entry nothing asks for is a sentence that was reworded and left behind.

    Which is the same failure as a missing one, seen from the other side: the English
    changed, the translation did not, and the page has been speaking English there ever
    since.
    """
    orphans = [one for one in LANGUAGES[language] if one not in everything()]

    assert not orphans, f"{language} translates what nothing says: {orphans}"


@pytest.mark.parametrize("language", sorted(LANGUAGES))
def test_a_translation_carries_the_same_values_as_its_sentence(language: str) -> None:
    """A dropped `{name}` is a sentence with a hole where the television's name was."""
    for english, said in LANGUAGES[language].items():
        assert set(PLACEHOLDER.findall(english)) == set(PLACEHOLDER.findall(said)), (
            f"{language}: {english!r} and {said!r} do not carry the same values"
        )


def test_a_language_nobody_wrote_words_for_falls_back_rather_than_failing() -> None:
    """English is a page a parent can use; an exception is not."""
    assert words("de") == {}
    assert words(None) == {}
    assert words("") == {}


def test_a_regional_language_takes_the_words_of_its_language() -> None:
    """`pl-PL` and `pl` are the same words, and Home Assistant may say either."""
    assert words("pl-PL") is POLISH
    assert words("PL") is POLISH


def test_the_words_reach_the_page_and_the_document_says_which_language() -> None:
    """Both halves: the catalogue is in the document, and so is the language tag."""
    page = render_shell(words("pl"), "pl")

    assert '<html lang="pl">' in page
    assert "const SAID = {" in page
    # A tag ending the script early would take the rest of the page with it.
    assert "</script" not in page[: page.index("const SAID")] + "".join(POLISH.values())


def test_no_translation_can_end_the_script_it_is_written_into() -> None:
    """The browser looks for the characters, not for a string, wherever they are."""
    page = render_shell(words("pl"), "pl")

    assert page.lower().count("</script>") == 2
