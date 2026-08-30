# TV Sitter parent panel

## What it is

A page of TV Sitter's own, in the Home Assistant sidebar: one card per television, showing what
the set is doing now and what it has watched today, with the rules on the same page as the
figures that made you want to change them.

It is a second interface onto the TV Sitter integration and never a second way to reach the
televisions. The integration enforces nothing on its own either — the decision to block is made
on the set — so a household that never installs the panel loses some convenience and no
enforcement. That is deliberate; the reasoning is D34 in
[`docs/architecture.md`](https://github.com/TomaszSyc/tvsitter/blob/main/docs/architecture.md).

## It talks to Home Assistant, never to your broker

Every read and every write goes through Home Assistant's own API. The panel has no MQTT
credentials, does not want them, and would not use them if it had them, which is why there is
nothing to fill in when you install it.

The reason is not tidiness. A rule change carries a revision number, and the television ignores
any change whose revision is not higher than the one it holds. That guard works because one
piece of software counts it. Two writers cannot see each other's counter, so a panel publishing
to the broker itself would be a second writer on the one contract whose safety rests on there
being only one.

## What it needs

- **Home Assistant OS or Supervised.** Apps (formerly add-ons) do not exist on Home Assistant
  Container or Core. The integration does, and it is the half that matters.
- **The TV Sitter integration**, installed and paired with at least one television. The panel
  shows the televisions Home Assistant already knows about; it cannot find one on its own.

## Installing

Add this repository under **Settings > Apps > App store**, three-dot menu, **Repositories**:

```
https://github.com/TomaszSyc/tvsitter
```

Then install **TV Sitter parent panel** and start it. It appears in the sidebar as **TV Sitter**.
There is nothing to configure — no options, no ports, no credentials.

The same repository URL is also the one HACS wants for the integration. Adding it in both places
is expected: HACS reads `custom_components/`, the Supervisor reads the App beside it.

## What is on the page

One card per television, in these sections.

**Now.** Whether the set is reporting to Home Assistant at all, whether the screen is on, what is
playing, whether the lock is up, and whether a parent PIN has been set. When something is wrong
with a television, the card says so in a line of its own rather than leaving you to work it out
from a missing figure.

**Today.** Watched so far, the limit in force today, what is left of it, any bonus minutes granted
from a "more time" request, and yesterday's total for comparison. The time the set last reported,
so you can tell a quiet television from a stale figure. Durations are shown as hours and minutes
rather than as the number the sensor happens to hold.

**Buttons that act now.** Lock the television or lift the lock. Block the Settings app or allow
it. Clear the limit, which removes the daily limit outright and leaves every other rule alone —
zero cannot stand in for it, because zero minutes means no viewing today and that is a real thing
a parent may mean.

**The rules.** The daily limit, the sleep timer, and how long before the end of the allowance the
television warns the child. That last one is a single warning; a ladder of several, which only an
automation can write, is collapsed to one by changing it here.

**The week.** A limit for each day, each of which overrides the daily limit on that day. Clearing
one hands the day back to the daily limit; setting it to zero means no viewing that day.

**Apps.** What the television has spent time in today, longest first, with a budget you can set
per app. A budget of zero blocks the app. Beside the budgets is the allow-list: tick the apps the
child may open at all, and every other app is refused. An empty allow-list allows everything,
which reads backwards until you ask which way it should fail — a rule that fails towards nothing
enforced is one a parent can recover from, and one that fails towards a television nobody can use
locks them out of the thing they would fix it with.

The two live side by side because they answer different questions: a budget says how long, an
allow-list says which apps exist. An app has to pass both.

**The hours viewing is allowed.** Shown, not edited. Home Assistant already has a weekly grid with
a proper editor — the Schedule helper — and TV Sitter reads it rather than shipping a second one.
[`docs/setup.md`](https://github.com/TomaszSyc/tvsitter/blob/main/docs/setup.md) has the three
steps.

**The rules revision.** One number, on every card. It is what the television says it is
enforcing, so it is the honest answer to "has my change actually arrived".

## What it does not do

It is the youngest part of the project, and worth saying plainly:

- **No profiles yet.** A named bundle of rules you can write to a television in one go is
  designed (D36) and not built.
- **The parent PIN is shown, not set.** The card says whether there is one. Setting or clearing
  it stays on the television's device page, which is where the hashing lives.
- **Today and yesterday are the whole of the history.** Anything longer is a graph, and graphs
  belong on the dashboard, which draws them from the same sensors.
- **English only.** The integration and the television's own screens are translatable; these
  pages are not, yet.
- **Nothing here enforces anything.** Close the panel, stop it, uninstall it: the television goes
  on counting and locking exactly as before.

## If something looks wrong

- **"No televisions yet"** — the integration is not installed, or no television has paired with
  it. The panel reports what Home Assistant already knows and has no other source.
- **"Home Assistant did not answer"** — usually a restart still in progress. The App's log has
  the reason.
- **"No Supervisor token"** — the container is running outside the Supervisor, which is not a
  supported way to run it.
- **A change is refused because the television is not listening** — this is on purpose. A rule
  sent to a set that is not there would go nowhere and the panel would have lied about it. Wake
  the television, or check that it is still reporting, and try again.
- **An app you know is installed is not in the list** — the list is what the television has spent
  time in today, not what it has installed. An app appears once it has been opened. To budget one
  before that, use the `tvsitter.set_app_limit` action with the package name.
- **The App does not appear after adding the repository** — only `aarch64` and `amd64` are built,
  and the Supervisor hides an App whose architecture is not claimed. That is a better failure
  than an image that installs and will not run.
- **A figure disagrees with the television** — compare the time the set last reported. The panel
  never computes a total of its own; it shows what the television sent.

## Licence

AGPL-3.0-only, like the rest of TV Sitter.
