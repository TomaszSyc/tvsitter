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
    # The Apps screen.
    "Only chosen apps": "Tylko wybrane aplikacje",
    "Only the apps allowed below open. New apps stay blocked until you allow them.": (
        "Otwierają się tylko dozwolone poniżej aplikacje. Nowe są zablokowane, dopóki "
        "ich nie dopuścisz."
    ),
    "Every app can be opened. Turn this on to allow only the ones you choose.": (
        "Można otworzyć każdą aplikację. Włącz, by dopuścić tylko wybrane."
    ),
    "No apps to list yet.": "Brak aplikacji do pokazania.",
    "Blocked": "Zablokowana",
    "{time} a day": "{time} dziennie",
    "today {time}": "dziś {time}",
    "Not used today": "Dziś nie używana",
    "today {today} · this week {week}": "dziś {today} · tydzień {week}",
    "Access": "Dostęp",
    "No limit means only the television's own limit applies.": (
        "Bez limitu obowiązuje tylko limit całego telewizora."
    ),
    "Remove limit": "Usuń limit",
    "Keep at least one app allowed, or turn the switch off.": (
        "Zostaw co najmniej jedną dozwoloną aplikację albo wyłącz przełącznik."
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
    # The Now screen. The header's status line says the same things in fewer words.
    "{app} · {time} today": "{app} · dziś {time}",
    "Not reachable since {when}": "Nie odpowiada od {when}",
    "No limit": "Bez limitu",
    "of {time}": "z {time}",
    "allowed until {clock}": "wolno do {clock}",
    "+15 min": "+15 min",
    "+30 min": "+30 min",
    # Buttons: what they do, said as an order, unlike "Locked" above.
    "Lock": "Zablokuj",
    "Unlock": "Odblokuj",
    "No limit today": "Bez limitu dziś",
    # Why the screen is covered. Short, because each also stands as the status line.
    "Today's time is used up": "Dzisiejszy czas się skończył",
    "Outside the allowed hours": "Poza dozwolonymi godzinami",
    "The sleep timer ran out": "Zadziałał wyłącznik czasowy",
    "Locked by a parent": "Zablokowany przez rodzica",
    "This app's time is used up": "Czas tej aplikacji się skończył",
    "This app is not allowed": "Ta aplikacja nie jest dozwolona",
    "Allowed again at {clock}": "Znowu wolno o {clock}",
    "Allowed again tomorrow at {clock}": "Znowu wolno jutro o {clock}",
    "Allowed again tomorrow": "Znowu wolno jutro",
    "Other apps can still be watched": "Inne aplikacje nadal są dostępne",
    "{time} watched today": "dziś obejrzane {time}",
    # A television that does not answer.
    "Last seen": "Ostatnio widziany",
    "Switched off or without a network.": "Wyłączony albo bez sieci.",
    "Its rules keep working on the television.": (
        "Reguły działają na telewizorze dalej."
    ),
    "Changes will wait until it is back.": "Zmiany poczekają, aż wróci.",
    "These need the television to be on and connected.": (
        "To wymaga włączonego telewizora z dostępem do sieci."
    ),
    # A request for more time, and its answers.
    "{minutes} min more, in {app}": "Jeszcze {minutes} min, w {app}",
    "{minutes} min more": "Jeszcze {minutes} min",
    "just now": "przed chwilą",
    "{count} min ago": "{count} min temu",
    "at {clock}": "o {clock}",
    "Give 15": "Daj 15",
    "Give 30": "Daj 30",
    "Not now": "Nie teraz",
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
    # The Rules screen: one day, how much and when.
    "Day": "Dzień",
    "How much": "Ile",
    "When": "Kiedy",
    "As daily": "Jak limit dzienny",
    "The daily limit: {time}": "Limit dzienny: {time}",
    "No daily limit is set": "Limit dzienny nie jest ustawiony",
    "15 minutes less": "15 minut mniej",
    "15 minutes more": "15 minut więcej",
    "Use the daily limit": "Użyj limitu dziennego",
    "To be spent within the marked hours (window: {time}).": (
        "Do wykorzystania w zaznaczonych godzinach (okno: {time})."
    ),
    "No hours are marked on any day, so it can be spent at any time.": (
        "Żaden dzień nie ma zaznaczonych godzin, więc można go wykorzystać o każdej "
        "porze."
    ),
    "No hours on this day: the television stays locked.": (
        "Ten dzień nie ma godzin: telewizor pozostaje zablokowany."
    ),
    "The hours come to only {time}, so no more than that can be watched.": (
        "Godzin jest tylko {time} — więcej nie da się obejrzeć."
    ),
    "Add hours": "Dodaj godziny",
    "Edit the hours from {from} to {to}": "Edytuj godziny od {from} do {to}",
    "Copy these hours to": "Skopiuj te godziny na",
    # After "Copy these hours to", so lower case.
    "weekdays": "dni robocze",
    "the weekend": "weekend",
    "the whole week": "cały tydzień",
    "Copied": "Skopiowano",
    "The television is enforcing other hours, so these are its own.": (
        "Telewizor egzekwuje inne godziny, więc pokazane są jego własne."
    ),
    "The television is asleep. The change goes when it wakes.": (
        "Telewizor śpi. Zmiana trafi do niego, gdy się obudzi."
    ),
    "Undo": "Cofnij",
    "The other days will be locked unless they get hours too.": (
        "Pozostałe dni będą zablokowane, jeśli też nie dostaną godzin."
    ),
    "No hours on {days}, so the television stays locked on them.": (
        "Brak godzin: {days} — w te dni telewizor pozostaje zablokowany."
    ),
    "{day} · hours": "{day} · godziny",
    "From": "Od",
    "To": "Do",
    "Delete": "Usuń",
    "Cancel": "Anuluj",
    "The end has to be after the start.": "Koniec musi być po początku.",
    "For days without their own.": "Dla dni bez własnego limitu.",
    "Remove the limit": "Usuń limit",
    "Start": "Włącz",
    "Cancel the timer": "Anuluj wyłącznik",
    "The television turns off at {clock}.": "Telewizor wyłączy się o {clock}.",
    "The sleep timer is off.": "Wyłącznik czasowy jest wyłączony.",
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
    # The Settings screen.
    "Parent": "Rodzic",
    "Parent PIN": "PIN rodzica",
    "Set": "Ustawiony",
    "Not set": "Nie ustawiony",
    "Send time requests to": "Wysyłaj prośby o czas do",
    "Second device": "Drugie urządzenie",
    "Warning before the end": "Ostrzeżenie przed końcem",
    "Block Settings on the television": "Blokuj Ustawienia na telewizorze",
    "Hours from a Home Assistant schedule": "Godziny z harmonogramu Home Assistanta",
    "Off": "Wyłączone",
    "Stop following": "Przestań śledzić",
    "To take the hours from a schedule, choose one in Home Assistant.": (
        "Aby brać godziny z harmonogramu, wybierz go w Home Assistancie."
    ),
    "Status": "Stan",
    "Version on the television": "Wersja na telewizorze",
    "Last report": "Ostatni raport",
    "Back": "Wstecz",
    # The page itself.
    "Everything here comes from Home Assistant.": (
        "Wszystko tutaj pochodzi z Home Assistanta."
    ),
    "Television": "Telewizor",
    "Sections": "Sekcje",
    "Now": "Teraz",
    "Today": "Dziś",
    "Last seven days": "Ostatnie siedem dni",
    "Yesterday {time}": "Wczoraj {time}",
    "Nothing watched in the last seven days.": (
        "W ostatnich siedmiu dniach nic nie oglądano."
    ),
    "The last seven days are not available from this television yet.": (
        "Ten telewizor nie podaje jeszcze danych z ostatnich siedmiu dni."
    ),
    "Rules": "Reguły",
    "Apps": "Aplikacje",
    "History": "Historia",
    "Settings": "Ustawienia",
    "No connection to Home Assistant": "Brak połączenia z Home Assistantem",
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
