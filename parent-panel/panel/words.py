"""What the panel says, in the languages it can say it in.

Keyed by the English sentence rather than by an invented name, which is the one decision
here worth explaining. A hundred names would have to be invented, kept in step with a
hundred sentences, and read back by whoever next edits the page — and a name is not the
sentence, so the page would stop saying what it says. This way the source stays the
prose it already was, a sentence with no translation falls back to itself rather than to
`rules.hours.empty`, and adding a language is one dictionary and nothing else.

The cost is that changing an English word breaks its translation silently. That is what
`tests/test_panel_words.py` is for: every sentence the page asks for has to be in here,
and every sentence in here has to be one the page asks for.

Values arrive as `{name}` rather than by adding strings end to end, because the order
the pieces of a sentence go in is not the same in every language.

A value that runs past one line is written inside brackets. Without them the formatter
pulls its first piece up onto the key's line, and a key that is itself a sentence leaves
nowhere for it to go.

TV Sitter — parental control for Android TV / Google TV.
Copyright (C) 2026 Tomasz Syc
SPDX-License-Identifier: AGPL-3.0-only
"""

from __future__ import annotations

POLISH: dict[str, str] = {
    # What is waiting, named the way it is said inside a longer sentence.
    "the daily limit": "limit dzienny",
    "the warning before the end": "ostrzeżenie przed końcem",
    "the Settings block": "blokada Ustawień",
    "the app budgets": "budżety aplikacji",
    "the week's allowances": "przydziały tygodnia",
    "the hours": "godziny",
    "the allowed apps": "dozwolone aplikacje",
    # The week, long and short. The short ones head the columns of the grid, so they
    # have to stay short: three letters at most, and two where Polish has two.
    "Monday": "Poniedziałek",
    "Mon": "Pon",
    "Tuesday": "Wtorek",
    "Tue": "Wt",
    "Wednesday": "Środa",
    "Wed": "Śr",
    "Thursday": "Czwartek",
    "Thu": "Czw",
    "Friday": "Piątek",
    "Fri": "Pt",
    "Saturday": "Sobota",
    "Sat": "Sob",
    "Sunday": "Niedziela",
    "Sun": "Nd",
    # What a change came to.
    "Dismiss": "Zamknij",
    "Saving…": "Zapisywanie…",
    "The panel could not reach the add-on.": "Panel nie dosięgnął dodatku.",
    "Home Assistant refused it.": "Home Assistant to odrzucił.",
    "Saved": "Zapisano",
    "{took} It reaches the television when the set wakes up.": (
        "{took} Trafi do telewizora, gdy ten się obudzi."
    ),
    "Home Assistant did not answer. This is what was last read.": (
        "Home Assistant nie odpowiedział. To jest ostatni odczyt."
    ),
    "No televisions yet: add the TV Sitter integration first.": (
        "Jeszcze żadnego telewizora: najpierw dodaj integrację TV Sitter."
    ),
    # Now.
    "Playing": "Odtwarzane",
    "Left today": "Zostało dziś",
    "Screen on": "Ekran włączony",
    "Screen off": "Ekran wyłączony",
    "Reporting": "Zgłasza się",
    "Not reporting": "Nie zgłasza się",
    "PIN set": "PIN ustawiony",
    "No PIN": "Brak PIN-u",
    # A state of the set, not the button that causes it: the television is locked.
    "Locked": "Zablokowany",
    "Nothing": "Nic",
    "Lift the lock": "Zdejmij blokadę",
    "Lock the television": "Zablokuj telewizor",
    # The PIN.
    "The parent PIN": "PIN rodzica",
    "The television only ever receives a hash of it.": (
        "Telewizor dostaje tylko jego skrót."
    ),
    "New PIN": "Nowy PIN",
    "Set the PIN": "Ustaw PIN",
    "Remove the PIN": "Usuń PIN",
    "Yes, remove it": "Tak, usuń",
    "Keep it": "Zostaw",
    "Without a PIN, a lock can only be lifted from Home Assistant.": (
        "Bez PIN-u blokadę zdejmiesz tylko z Home Assistanta."
    ),
    "A PIN is four digits.": "PIN to cztery cyfry.",
    "PIN removed": "PIN usunięty",
    # When the television last said anything.
    "Never reported.": "Nigdy się nie zgłosił.",
    "Last reported {when}.": "Ostatnie zgłoszenie: {when}.",
    "Last reported at {clock}.": "Ostatnie zgłoszenie o {clock}.",
    "Rules revision {count}.": "Wersja reguł: {count}.",
    # Today.
    "Watched": "Obejrzane",
    "Limit today": "Limit na dziś",
    "Left": "Zostało",
    "Today, by app": "Dziś, według aplikacji",
    "The last seven days, by app": "Ostatnie siedem dni, według aplikacji",
    "Nothing watched yet today.": "Dziś jeszcze nic nie oglądano.",
    "Home Assistant's history has nothing for this set yet.": (
        "Historia Home Assistanta nie ma jeszcze nic dla tego telewizora."
    ),
    "An app with no name left shows its package id.": (
        "Aplikacja bez nazwy pokazuje identyfikator pakietu."
    ),
    "Bonus today {much}.": "Bonus dziś: {much}.",
    "Yesterday {much}.": "Wczoraj: {much}.",
    "of {much}": "z {much}",
    # Rules.
    "Every day": "Codziennie",
    "Daily limit": "Limit dzienny",
    "Sleep timer": "Wyłącznik czasowy",
    "Turns the television off after this long.": "Wyłącza telewizor po tym czasie.",
    "Warn before the end": "Ostrzeż przed końcem",
    "Block the Settings app": "Zablokuj aplikację Ustawienia",
    "So the rules cannot be turned off from the television itself.": (
        "Żeby reguł nie dało się wyłączyć z samego telewizora."
    ),
    "The week": "Tydzień",
    # The change the television has not had yet.
    "Throw the change away": "Wyrzuć zmianę",
    "Only the waiting change goes; the set keeps the rules it has.": (
        "Znika tylko oczekująca zmiana; telewizor zachowuje obecne reguły."
    ),
    "Thrown away. The television keeps the rules it already had.": (
        "Wyrzucone. Telewizor zachowuje reguły, które już miał."
    ),
    "{name} is asleep; waiting until it is back: {what}.": (
        "{name} śpi; do jego powrotu czeka: {what}."
    ),
    "a change": "zmiana",
    "{most} and {last}": "{most} i {last}",
    # The numbers a parent types.
    "That wants a number of minutes.": "Tu trzeba podać liczbę minut.",
    "Remove": "Usuń",
    "Remove leaves the day uncapped; zero means no viewing.": (
        "Usunięcie znosi limit; zero oznacza brak oglądania."
    ),
    "Limit removed": "Limit usunięty",
    "Minutes a day for {day}": "Minuty dziennie: {day}",
    "{day} wants a number of minutes, or nothing.": (
        "{day}: podaj liczbę minut albo zostaw puste."
    ),
    "{day} saved": "Zapisano: {day}",
    "not set": "nieustawiony",
    "Minutes; empty takes the daily limit ({takes}), zero means no viewing.": (
        "Minuty; puste pole bierze limit dzienny ({takes}), zero to brak oglądania."
    ),
    # Apps.
    "Only ticked apps open; a budget of zero blocks an app.": (
        "Otwierają się tylko zaznaczone aplikacje; budżet zero blokuje aplikację."
    ),
    "Every app is allowed; untick one to start an allow-list.": (
        "Każda aplikacja jest dozwolona; odznacz jedną, by zacząć listę dozwolonych."
    ),
    "Allowed": "Dozwolona",
    "That wants a number of minutes, or nothing.": (
        "Tu trzeba podać liczbę minut albo zostawić puste."
    ),
    "Saved: with none ticked, every app is allowed.": (
        "Zapisano: bez zaznaczeń każda aplikacja jest dozwolona."
    ),
    "Minutes a day for {app}": "Minuty dziennie: {app}",
    # The hours.
    "The hours": "Godziny",
    "Keep these hours and edit here": "Zatrzymaj te godziny i edytuj tutaj",
    "The hours stay as they are, and the helper is left alone.": (
        "Godziny zostają bez zmian, a pomocnik nietknięty."
    ),
    "Drag across the boxes to allow those hours; start on a marked box to clear.": (
        "Przeciągnij po polach, by zezwolić na te godziny; zacznij od zaznaczonego, "
        "by je wyczyścić."
    ),
    "No half hour is marked, so viewing is allowed at any time.": (
        "Żadna półgodzina nie jest zaznaczona, więc oglądać można o każdej porze."
    ),
    "The half hours viewing is allowed in": "Półgodziny, w których wolno oglądać",
    "Every half hour of {day}": "Cały dzień: {day}",
    "{day} {from} to {to}": "{day} {from} do {to}",
    "Waiting: the television is asleep.": "Czeka: telewizor śpi.",
    "The television is enforcing hours other than the ones drawn here, so the grid has "
    "gone back to showing its own.": (
        "Telewizor egzekwuje inne godziny niż narysowane tutaj, więc siatka wróciła do "
        "pokazywania jego własnych."
    ),
    "Allow": "Zezwól",
    "Clear": "Wyczyść",
    "Saved: a full week is no restriction.": (
        "Zapisano: pełny tydzień to brak ograniczeń."
    ),
    "Hours saved": "Godziny zapisane",
    "Unchanged, and yours to draw on here.": "Bez zmian, i do rysowania tutaj.",
    "Read-only: the hours come from {helper}.": (
        "Tylko do odczytu: godziny pochodzą z {helper}."
    ),
    # Asking for more time.
    "Asking for more time": "Prośba o więcej czasu",
    "Ask": "Zapytaj",
    "And also": "A także",
    "Save": "Zapisz",
    "Nobody": "Nikogo",
    "Nobody else": "Nikogo więcej",
    "This television, added by an older integration, has no time request to answer.": (
        "Ten telewizor, dodany starszą wersją integracji, nie ma prośby o czas."
    ),
    "No phone with the Home Assistant app was found.": (
        "Nie znaleziono telefonu z aplikacją Home Assistant."
    ),
    # The page itself.
    "Everything here comes from Home Assistant.": (
        "Wszystko tutaj pochodzi z Home Assistanta."
    ),
    "Television": "Telewizor",
    "Sections": "Sekcje",
    "Now": "Teraz",
    "Today": "Dziś",
    "Rules": "Reguły",
    "Apps": "Aplikacje",
    # What the panel itself says when a change cannot be made. Only the sentences that
    # are the same every time: the ones carrying a television's name are built where
    # the name is known and stay in English until they are made into templates.
    "No Supervisor token. This runs as a Home Assistant App, and started outside one "
    "it has nobody to ask.": (
        "Brak tokenu Supervisora. To działa jako aplikacja Home Assistanta, a "
        "uruchomione poza nią nie ma kogo zapytać."
    ),
    "Home Assistant refused the token this App was given.": (
        "Home Assistant odrzucił token, który dostała ta aplikacja."
    ),
    "Home Assistant did not answer. It may still be starting.": (
        "Home Assistant nie odpowiedział. Możliwe, że jeszcze się uruchamia."
    ),
    "That was not a request.": "To nie było żądanie.",
    "Home Assistant would not keep that automation.": (
        "Home Assistant nie przyjął tej automatyzacji."
    ),
    "Home Assistant would not make that change.": (
        "Home Assistant nie wprowadził tej zmiany."
    ),
    "That television is not here any more.": "Tego telewizora już tu nie ma.",
    "This needs an action.": "To wymaga akcji.",
}

LANGUAGES: dict[str, dict[str, str]] = {"pl": POLISH}


def phrase(said: str, language: str | None) -> str:
    """Say one sentence in a language, or leave it in the English it was written in.

    For the sentences the panel writes rather than the page: a refusal is read by the
    same parent on the same screen, so it has no business being the one English line
    among them. Sentences that carry a television's name are not in here — they are
    built where the name is known, and putting them back together in another language
    is a bigger job than this one line.
    """
    return words(language).get(said, said)


def words(language: str | None) -> dict[str, str]:
    """Return the catalogue for a language, or an empty one where there is none.

    A language is matched on the part before the dash, so `pl-PL` and `pl` are the same
    catalogue. An empty answer is not a failure: the page falls back to the English it
    is written in, which is a page a parent can use rather than an error.
    """
    named = (language or "").split("-")[0].strip().lower()
    return LANGUAGES.get(named, {})
