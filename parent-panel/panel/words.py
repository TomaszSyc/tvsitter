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
    "{took} The television is asleep, so it is waiting rather than in force, and goes "
    "the moment the set is back.": (
        "{took} Telewizor śpi, więc zmiana czeka, zamiast obowiązywać, i pójdzie w "
        "chwili, gdy odbiornik wróci."
    ),
    "Home Assistant did not answer. This is what was last read.": (
        "Home Assistant nie odpowiedział. To jest ostatni odczyt."
    ),
    "No televisions yet. The panel reads them from the TV Sitter integration, so add "
    "that first — this page is a second way to see what it already knows, not a way "
    "round it.": (
        "Jeszcze żadnego telewizora. Panel odczytuje je z integracji TV Sitter, więc "
        "najpierw dodaj integrację — ta strona to drugi sposób, żeby zobaczyć to, co "
        "ona już wie, a nie sposób, żeby ją ominąć."
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
    "Nothing": "Nic",
    "Lift the lock": "Zdejmij blokadę",
    "Lock the television": "Zablokuj telewizor",
    # The PIN.
    "The parent PIN": "PIN rodzica",
    "Home Assistant hashes it and sends the hash, so the television is never told the "
    "digits typed here.": (
        "Home Assistant liczy z niego skrót i wysyła skrót, więc telewizor nigdy nie "
        "pozna cyfr wpisanych tutaj."
    ),
    "New PIN": "Nowy PIN",
    "Set the PIN": "Ustaw PIN",
    "Remove the PIN": "Usuń PIN",
    "Yes, remove it": "Tak, usuń",
    "Keep it": "Zostaw",
    "Without a PIN a lock cannot be lifted at the television at all, only from Home "
    "Assistant.": (
        "Bez PIN-u blokady nie da się zdjąć na samym telewizorze — wyłącznie z Home "
        "Assistanta."
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
    "Nothing recorded yet. These seven days come from Home Assistant's own history "
    "rather than from the television, and it has nothing for this set so far — which "
    "is not the same as a week with nothing watched in it.": (
        "Jeszcze nic nie zapisano. Te siedem dni pochodzi z własnej historii Home "
        "Assistanta, a nie z telewizora, i na razie nie ma w niej nic dla tego "
        "odbiornika — co nie jest tym samym co tydzień bez oglądania."
    ),
    "Where Home Assistant has no name for an app any more, its package id stands in.": (
        "Tam, gdzie Home Assistant nie zna już nazwy aplikacji, stoi jej identyfikator "
        "pakietu."
    ),
    "Bonus today {much}.": "Bonus dziś: {much}.",
    "Yesterday {much}.": "Wczoraj: {much}.",
    "of {much}": "z {much}",
    # Rules.
    "Every day": "Codziennie",
    "Daily limit": "Limit dzienny",
    "Sleep timer": "Wyłącznik czasowy",
    "How long from now until the television puts itself to bed.": (
        "Za ile od teraz telewizor sam się położy spać."
    ),
    "Warn before the end": "Ostrzeż przed końcem",
    "One warning, this long before the allowance runs out.": (
        "Jedno ostrzeżenie, tyle przed końcem przydziału."
    ),
    "Block the Settings app": "Zablokuj aplikację Ustawienia",
    "So the rules cannot be turned off from the television itself.": (
        "Żeby reguł nie dało się wyłączyć z samego telewizora."
    ),
    "The week": "Tydzień",
    # The change the television has not had yet.
    "Throw the change away": "Wyrzuć zmianę",
    "For a television that is not coming back. What goes is only what has not reached "
    "it: the set keeps enforcing exactly what it is enforcing now.": (
        "Dla telewizora, który już nie wróci. Znika wyłącznie to, co do niego nie "
        "dotarło: odbiornik dalej egzekwuje dokładnie to, co egzekwuje teraz."
    ),
    "Thrown away. The television keeps the rules it already had.": (
        "Wyrzucone. Telewizor zachowuje reguły, które już miał."
    ),
    "Waiting for {name} rather than in force: {what}. The set was asleep when it was "
    "changed, so everything below is what it is still enforcing until it is back.": (
        "Czeka na {name}, zamiast obowiązywać: {what}. Telewizor spał, gdy to "
        "zmieniono, więc wszystko poniżej to, co nadal egzekwuje, dopóki nie wróci."
    ),
    "a change": "zmiana",
    "{most} and {last}": "{most} i {last}",
    # The numbers a parent types.
    "That wants a number of minutes.": "Tu trzeba podać liczbę minut.",
    "Remove": "Usuń",
    "Removing it leaves the day uncapped. Zero is not the same thing: zero minutes "
    "means no viewing today, which is a real thing a parent may mean.": (
        "Usunięcie zostawia dzień bez limitu. Zero to nie to samo: zero minut znaczy "
        "żadnego oglądania dzisiaj, a to bywa dokładnie tym, o co rodzicowi chodzi."
    ),
    "Limit removed": "Limit usunięty",
    "Minutes a day for {day}": "Minuty dziennie: {day}",
    "{day} wants a number of minutes, or nothing.": (
        "{day}: podaj liczbę minut albo zostaw puste."
    ),
    "{day} saved": "Zapisano: {day}",
    "which is not set either": "który też nie jest ustawiony",
    "Minutes a day. A day left empty takes the daily limit, {takes}; a day set to zero "
    "is no viewing at all.": (
        "Minuty dziennie. Dzień zostawiony pusty bierze limit dzienny, {takes}; dzień "
        "ustawiony na zero to żadnego oglądania."
    ),
    # Apps.
    "Only the ticked apps may be opened; every other one is refused. A budget of zero "
    "blocks an app whether or not it is ticked.": (
        "Otworzyć można wyłącznie zaznaczone aplikacje; każda inna zostanie odrzucona. "
        "Budżet zero blokuje aplikację niezależnie od zaznaczenia."
    ),
    "The allow-list is empty, so every app is allowed. Untick one to start a list: "
    "everything left ticked stays allowed and the rest are refused. A budget of zero "
    "blocks an app on its own.": (
        "Lista dozwolonych jest pusta, więc każda aplikacja jest dozwolona. Odznacz "
        "którąś, żeby zacząć listę: wszystko, co zostanie zaznaczone, pozostaje "
        "dozwolone, a reszta jest odrzucana. Budżet zero blokuje aplikację sam z "
        "siebie."
    ),
    "Allowed": "Dozwolona",
    "That wants a number of minutes, or nothing.": (
        "Tu trzeba podać liczbę minut albo zostawić puste."
    ),
    "Saved. An empty list is no restriction: every app is allowed again.": (
        "Zapisano. Pusta lista to brak ograniczenia: każda aplikacja jest znowu "
        "dozwolona."
    ),
    "Minutes a day for {app}": "Minuty dziennie: {app}",
    # The hours.
    "The hours": "Godziny",
    "Keep these hours and edit here": "Zatrzymaj te godziny i edytuj tutaj",
    "The hours stay exactly as they are; only the following stops, and the helper is "
    "left alone.": (
        "Godziny zostają dokładnie takie, jakie są; kończy się wyłącznie podążanie za "
        "pomocnikiem, a sam pomocnik zostaje nietknięty."
    ),
    "A green box is half an hour the television may be watched in. Drag across the "
    "boxes to allow viewing in them, or out of a marked box to clear; the hours you "
    "are drawing are named above the pointer as you go. A day name takes the whole "
    "day. From the keyboard: arrows move, space marks, shift and an arrow paints.": (
        "Zielone pole to pół godziny, w których wolno oglądać telewizor. Przeciągnij "
        "po polach, żeby zezwolić na oglądanie, albo z zaznaczonego pola, żeby "
        "wyczyścić; rysowane godziny są nazywane nad wskaźnikiem na bieżąco. Nazwa "
        "dnia bierze cały dzień. Z klawiatury: strzałki przesuwają, spacja zaznacza, "
        "shift ze strzałką maluje."
    ),
    "No half hour is marked, so the hours are not restricted at all: the television "
    "may be watched at any time of day, within whatever the limits above allow.": (
        "Żadna półgodzina nie jest zaznaczona, więc godziny nie są w ogóle "
        "ograniczone: telewizor można oglądać o dowolnej porze dnia, w granicach tego, "
        "na co pozwalają limity powyżej."
    ),
    "The half hours viewing is allowed in": "Półgodziny, w których wolno oglądać",
    "Every half hour of {day}": "Cały dzień: {day}",
    "{day} {from} to {to}": "{day} {from} do {to}",
    "These hours are drawn here and waiting: the television is asleep, and they go to "
    "it the moment it is back.": (
        "Te godziny są tu narysowane i czekają: telewizor śpi, a pójdą do niego w "
        "chwili, gdy wróci."
    ),
    "The television is enforcing hours other than the ones drawn here, so the grid has "
    "gone back to showing its own.": (
        "Telewizor egzekwuje inne godziny niż narysowane tutaj, więc siatka wróciła do "
        "pokazywania jego własnych."
    ),
    "Allow": "Zezwól",
    "Clear": "Wyczyść",
    "Saved. A week with nothing refused is no restriction, so it clears.": (
        "Zapisano. Tydzień, w którym nic nie jest odrzucone, to brak ograniczenia, "
        "więc znika."
    ),
    "Hours saved": "Godziny zapisane",
    "The hours are yours to draw on, and not one of them has changed.": (
        "Godziny są twoje do rysowania i żadna z nich się nie zmieniła."
    ),
    "Read from {helper} whenever it changes, so the grid below is read-only.": (
        "Odczytywane z {helper} przy każdej zmianie, więc siatka poniżej jest tylko do "
        "odczytu."
    ),
    # Asking for more time.
    "Asking for more time": "Prośba o więcej czasu",
    "When the child asks for more time, Home Assistant sends the question to a phone "
    "with buttons to answer it.": (
        "Gdy dziecko poprosi o więcej czasu, Home Assistant wyśle pytanie na telefon, "
        "z przyciskami do odpowiedzi."
    ),
    "Ask": "Zapytaj",
    "And also": "A także",
    "Save": "Zapisz",
    "Nobody": "Nikogo",
    "Nobody else": "Nikogo więcej",
    "This television has no time request to answer. It was set up by an older version "
    "of the integration, which had none.": (
        "Ten telewizor nie ma prośby o czas, na którą można by odpowiedzieć. Został "
        "dodany starszą wersją integracji, która jej nie miała."
    ),
    "No phone with the Home Assistant app on it was found, and only a phone can carry "
    "buttons to answer with.": (
        "Nie znaleziono telefonu z aplikacją Home Assistant, a tylko telefon uniesie "
        "przyciski do odpowiedzi."
    ),
    # The page itself.
    "Everything here comes from Home Assistant, which is the only thing that talks to "
    "the televisions.": (
        "Wszystko tutaj pochodzi z Home Assistanta, który jako jedyny rozmawia z "
        "telewizorami."
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
