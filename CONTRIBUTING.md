# Contributing

The project is currently private and a one-person effort. This file describes the rules
that will apply once the repository is opened up.

## License and CLA

The code is licensed under **AGPL-3.0-only**. Every source file carries an
`SPDX-License-Identifier: AGPL-3.0-only` header.

A **CLA** will be introduced with the first external pull request, assigning copyright in
the contribution to the project owner. Without it the code could never be released under
different terms, nor licensed commercially to anyone. By opening a pull request before
that, you agree to your contribution being covered by the same terms.

## Building

```bash
./gradlew :rules:test          # rules logic tests, plain JVM, no emulator needed
./gradlew :app:assembleDebug   # APK for the TV
```

## Tooling

```bash
pre-commit install                       # one-time; runs the fast checks on every commit
./gradlew spotlessApply                  # format Kotlin, Gradle scripts, YAML, JSON, XML
./gradlew spotlessCheck detekt :app:lintDebug   # what CI runs
pip install -r requirements-dev.txt      # Ruff, for the integration
ruff check . && ruff format .
```

Kotlin formatting is deliberately absent from the pre-commit hooks: Spotless and detekt
need a Gradle daemon, which turns every commit into a multi-second wait. They run in CI and
in the IDE instead. The hooks cover the fast things — whitespace, YAML and JSON validity,
Ruff, and a private-key check.

ktlint runs in its `intellij_idea` style rather than the default `ktlint_official`, which
rewrites code instead of formatting it: it splits two-parameter signatures across lines and
wraps every `when` branch in braces. The style is passed through Spotless because Spotless
does not forward `.editorconfig` to ktlint.

Spotless also enforces the AGPL header on every Kotlin file. That is a licence
requirement, not a tidiness preference, so it is checked rather than trusted to reviewers.

Decision logic ("should this be blocked, how much time is left") belongs in the `:rules`
module and must come with unit tests. The `:app` module owns Android concerns only:
accessibility events, the lock window, MQTT. Rule of thumb: if something cannot be tested
without a TV, it is probably in the wrong module.

## The MQTT contract

[`docs/mqtt-contract.md`](docs/mqtt-contract.md) is binding for both halves of the
project. Changing a field means bumping `schema` and changing both sides in one commit.

## Style

- Kotlin: see `.editorconfig`, 120 column limit.
- Python (the Home Assistant integration): Home Assistant conventions —
  `from __future__ import annotations`, type hints, async throughout the integration layer.
- Comments explain **why**, they do not restate the code.
- Code, comments and documentation are in English. User-facing strings live in resource
  files (`app/src/main/res/values*/strings.xml`, `custom_components/tvsitter/translations/`)
  so they can be translated; `strings.json` and the default `values/` are English.
