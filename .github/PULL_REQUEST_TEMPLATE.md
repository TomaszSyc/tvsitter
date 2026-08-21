## What this changes

<!-- One or two sentences. The "why" matters more than the "what" — the diff already says what. -->

## Checklist

- [ ] Decision logic lives in `:rules` and has unit tests (`./gradlew :rules:test`)
- [ ] `./gradlew :app:assembleDebug` passes
- [ ] If the MQTT payloads changed: `docs/mqtt-contract.md` updated, `schema` bumped, and
      both halves changed in this pull request
- [ ] User-facing strings went into resource files, not inline literals
- [ ] Architectural choices worth remembering added to `docs/architecture.md`

## Tested on

<!-- Device, Android version, Home Assistant version. "Only unit tests" is a valid answer. -->
