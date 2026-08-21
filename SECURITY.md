# Security policy

## Supported versions

Pre-alpha. Only the current `main` branch is supported and there are no backports — if a
fix is needed, it lands on `main` and in the next release.

## Reporting a vulnerability

Please report privately rather than opening a public issue.

Use **Report a vulnerability** on the repository's Security tab (GitHub private
vulnerability reporting). If that is unavailable to you, open a regular issue asking for a
private channel and **leave the details out of it** — a maintainer will follow up.

Expect an acknowledgement within a week. This is a hobby project maintained in spare time:
there is no bounty programme and no service level agreement, but reports are taken
seriously and credited in the release notes unless you prefer otherwise.

## In scope

- Anything that lets a party on the local network unlock the TV, grant screen time or
  change the rules without the parent's PIN.
- Leakage of the MQTT broker credentials or the parent PIN — in logs, in `adb bugreport`,
  in a crash report or over the network.
- A payload on any MQTT topic in `docs/mqtt-contract.md` that crashes the app, the
  integration or Home Assistant, or that gets one of them to execute something unintended.
- The debug-only ADB command receiver appearing in a **release** build. It is declared in
  `app/src/debug/AndroidManifest.xml` and must never ship; if you find it in a release
  artifact, that is a valid report.
- Privilege escalation using the accessibility service beyond what the app needs.

## Out of scope

These are documented limitations rather than vulnerabilities. The project currently targets
a "medium" anti-tamper level: it resists a curious child, not an adult with physical access
and a laptop.

- Unplugging the TV, pulling the network cable, or factory-resetting the device.
- Turning the accessibility service off in Settings, or uninstalling the app. Milestone M5
  makes this noisy rather than impossible, by alarming in Home Assistant when the app stops
  reporting while the TV is powered on.
- Anyone with ADB access to the TV, or physical access to the Home Assistant host, can
  disable enforcement. That is inherent to the platform, not a flaw in this app.
- Reading files from the app's private storage on a rooted device or over ADB.

## Hardening notes for operators

- Give TV Sitter its own MQTT account, with an ACL restricted to its own topic prefix.
  Any client able to publish to `<prefix>/cmd` can unlock the TV.
- Local MQTT is commonly unencrypted. On a shared or untrusted network, enable TLS on the
  broker — the topic payloads carry no credentials, but they do carry the commands.
- Do not commit broker credentials. `secrets.properties` and `ha/secrets.yaml` are already
  in `.gitignore`.
