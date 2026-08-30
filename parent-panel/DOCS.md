# TV Sitter parent panel

## What it is

A second interface onto the TV Sitter integration, with room for the things a dashboard card
cannot hold: the week per app, setup that is otherwise manual, and the shapes Home Assistant
configuration does not have.

It reads and writes through Home Assistant's own API. Your broker credentials are not asked
for and would not be used — the integration is the only thing that publishes to a television,
which is what keeps the revision guard on a rule change working (D34 in `docs/architecture.md`).

## What it needs

- Home Assistant OS or Supervised. Apps do not exist on Container or Core.
- The TV Sitter integration, installed and paired with at least one television.

## Installing

Add this repository under **Settings > Apps > App store**, three-dot menu, **Repositories**:

```
https://github.com/TomaszSyc/tvsitter
```

Then install **TV Sitter parent panel** and start it. It appears in the sidebar; there is
nothing to configure.

## What it shows today

One page, listing every television the integration knows about and what each is doing. That is
the skeleton (#100) — the editor, the daily view and the setup pages follow.

## If the page says it cannot see anything

- **"No televisions yet"** — the integration is not installed, or no television has paired
  with it. The panel only ever reports what Home Assistant already knows.
- **"Home Assistant did not answer"** — usually a restart still in progress. The App log has
  the reason.
- **"No Supervisor token"** — the container is running outside the Supervisor, which is not a
  supported way to run it.

## Licence

AGPL-3.0-only, like the rest of TV Sitter.
